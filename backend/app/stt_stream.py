"""브라우저 마이크 오디오(PCM16 LE mono 24kHz) → 서버 VAD → STT 제공자 중계 → commit 순서대로 감지기에 전달.

- 브라우저는 AudioWorklet 에서 24kHz 로 리샘플링한 PCM16 을 보낸다. 서버는 mic_start 의 형식 선언을 검증하고
  다르면 거부한다(지원하지 않는 형식을 STT 로 보내지 않음).
- 클라이언트 측 VAD (gpt-live-transcribe 는 server_vad / semantic_vad 미지원 → turn_detection=null, 우리가 commit):
  · 20ms 프레임 RMS. 유성 프레임이 시작되면 '후보' 구간으로 오디오를 서버에 보관만 한다(아직 STT 로 보내지 않음).
  · 후보 구간의 유성 누적이 VAD_MIN_SPEECH_MS 이상이 되어야 '발화'로 확정하고 보관분(프리롤 포함)을 STT 로 보낸다.
    그 전에 침묵이 VAD_SILENCE_MS 이어지면 버린다 → 짧은 잡음은 STT 로 전송·commit 되지 않는다.
  · 발화 중 침묵이 VAD_SILENCE_MS 이상이거나 구간이 VAD_MAX_SEGMENT_MS 에 도달하면 commit.
- 전사 완료 이벤트는 순서가 보장되지 않는다(문서). commit 순서대로 보관했다가 앞 구간부터 감지기에 전달한다.
  · 앞 구간이 실패하면 건너뛴다.
  · 뒤 구간이 이미 도착했는데 앞 구간이 STT_REORDER_TIMEOUT_MS 넘게 오지 않으면 앞 구간을 건너뛴다.
  · 어떤 결과도 STT_RESULT_TIMEOUT_MS 넘게 오지 않으면 건너뛴다.
  · 건너뛴 구간의 결과가 나중에 오면 자막·기록에는 남기되 요청 감지에는 넣지 않는다(순서가 깨진 입력 방지).
- 발화 종료 '추정' 시각 = 마지막 유성 프레임이 서버에 도착한 단조 시각(브라우저→서버 전송 지연 미포함).
"""
from __future__ import annotations

import asyncio
import collections
import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

import numpy as np

from .config import Settings
from .providers.base import SttEvent, SttProvider, Usage

if TYPE_CHECKING:
    from .runtime import SessionRuntime

log = logging.getLogger("nextslide.stt")
FRAME_MS = 20


class AudioFormatError(ValueError):
    pass


def validate_mic_start(msg: dict, s: Settings) -> None:
    sr = msg.get("sample_rate")
    enc = msg.get("encoding")
    ch = msg.get("channels")
    if sr != s.stt_sample_rate or enc != "pcm_s16le" or ch != 1:
        raise AudioFormatError(
            f"지원하지 않는 오디오 형식: sample_rate={sr}, encoding={enc}, channels={ch}. "
            f"필요: {s.stt_sample_rate}Hz pcm_s16le mono")


@dataclass
class _Pending:
    seg: str
    committed_at: float
    status: str = "waiting"  # waiting | done | failed
    event: Optional[SttEvent] = None
    received_at: Optional[float] = None


class SttStream:
    def __init__(self, rt: "SessionRuntime", provider: SttProvider, s: Settings):
        self.rt = rt
        self.p = provider
        self.s = s
        self.active = False
        self.frame_bytes = s.stt_sample_rate * FRAME_MS // 1000 * 2
        self._carry = b""
        self._preroll: collections.deque[bytes] = collections.deque(maxlen=max(1, s.vad_preroll_ms // FRAME_MS))
        self._state = "idle"  # idle | candidate | speech
        self._held: list[bytes] = []  # 후보 구간 오디오 (아직 STT 로 보내지 않음)
        self._voiced_ms = 0
        self._silence_ms = 0
        self._seg_ms = 0
        self._seg_no = 0
        self._local_seg: Optional[str] = None
        self._last_voice_mono: Optional[float] = None
        self.local_speech_end: dict[str, float] = {}
        self.started_mono: Optional[float] = None
        self.frames_in = 0
        self.discarded_short = 0
        self.committed = 0
        # commit 순서 보정
        self._order: collections.deque[_Pending] = collections.deque()
        self._by_seg: dict[str, _Pending] = {}
        self._skipped: set[str] = set()
        self._order_lock = asyncio.Lock()
        self._reorder_task: Optional[asyncio.Task] = None

    # ------------------------------------------------------------ 시작/종료
    async def start(self) -> None:
        self.active = True
        self.started_mono = time.monotonic()
        try:
            await self.p.start(self._on_event)  # 제공자는 설정 승인(session.updated) 후에 반환
        except Exception:
            self.active = False
            raise
        self._reorder_task = asyncio.create_task(self._reorder_loop())

    async def stop(self) -> None:
        if not self.active:
            return
        self.active = False
        if self._state == "speech":
            await self._commit()
        elif self._state == "candidate":
            self._discard_candidate()
        # 남은 구간의 확정 결과를 잠시 기다린다
        deadline = time.monotonic() + 3.0
        while self._order and time.monotonic() < deadline:
            await asyncio.sleep(0.1)
        if self._reorder_task:
            self._reorder_task.cancel()
        async with self._order_lock:
            while self._order:
                head = self._order.popleft()
                if head.status == "done" and head.event:
                    await self._deliver(head, feed_detector=True)
                else:
                    self._skipped.add(head.seg)
        await self.p.close()
        secs = getattr(self.p, "audio_seconds_sent", None)
        if secs:
            self.rt._log_usage(None, Usage(provider=self.p.name, model=self.p.model, kind="stt", audio_seconds=secs),
                               "used")

    # ------------------------------------------------------------ 제공자 이벤트
    async def _on_event(self, ev: SttEvent) -> None:
        sid = self.rt.sid
        if ev.type == "partial":
            await self.rt.handle_partial(ev.segment_id, ev.text or "")
        elif ev.type == "final":
            await self._on_final(ev)
        elif ev.type == "segment_failed":
            async with self._order_lock:
                ent = self._by_seg.get(ev.local_segment or "")
                if ent and ent.status == "waiting":
                    ent.status = "failed"
                await self._flush()
            if ev.message:
                await self.rt.hub.broadcast(sid, "stt.notice", {"level": "error", "message": ev.message})
        elif ev.type == "status":
            await self.rt.hub.broadcast(sid, "stt.status", {"state": ev.state, "message": ev.message})
        elif ev.type in ("error", "notice"):
            await self.rt.hub.broadcast(sid, "stt.notice", {"level": ev.type, "message": ev.message})

    async def _on_final(self, ev: SttEvent) -> None:
        now = time.monotonic()
        async with self._order_lock:
            ls = ev.local_segment
            ent = self._by_seg.get(ls) if ls else None
            if ent is not None and ent.status == "waiting":
                ent.status, ent.event, ent.received_at = "done", ev, now
                await self._flush()
                return
            if ls and ls in self._skipped:
                # 건너뛴 뒤 늦게 도착: 기록은 남기되 감지에는 넣지 않음
                self._skipped.discard(ls)
                await self._deliver(_Pending(ls, now, "done", ev, now), feed_detector=False)
                if (ev.text or "").strip():
                    await self.rt.hub.broadcast(self.rt.sid, "stt.notice", {
                        "level": "notice", "message": "늦게 도착한 앞 구간 전사는 자막에만 반영하고 요청 감지에는 쓰지 않았습니다."})
                return
        # 구간 매핑을 알 수 없는 결과(제공자가 commit 과 연결하지 못함): 순서 보정 없이 전달
        await self._deliver(_Pending(ls or "?", now, "done", ev, now), feed_detector=True)

    async def _deliver(self, ent: _Pending, feed_detector: bool) -> None:
        ev = ent.event
        assert ev is not None
        end = self.local_speech_end.pop(ent.seg, None)
        await self.rt.handle_final(ev.segment_id or f"stt-{ent.seg}-{time.time()}", ev.text or "", "stt",
                                   speech_end_mono=end, received_mono=ent.received_at, feed_detector=feed_detector)

    async def _flush(self) -> None:
        """앞에서부터 완료된 구간을 순서대로 전달. 호출자는 _order_lock 을 잡고 있어야 한다."""
        while self._order:
            head = self._order[0]
            if head.status == "done":
                self._order.popleft()
                self._by_seg.pop(head.seg, None)
                await self._deliver(head, feed_detector=True)
            elif head.status == "failed":
                self._order.popleft()
                self._by_seg.pop(head.seg, None)
                self.local_speech_end.pop(head.seg, None)
            else:
                break

    async def _reorder_loop(self) -> None:
        reorder_s = self.s.stt_reorder_timeout_ms / 1000
        hard_s = self.s.stt_result_timeout_ms / 1000
        while True:
            await asyncio.sleep(0.2)
            async with self._order_lock:
                if not self._order or self._order[0].status != "waiting":
                    continue
                head = self._order[0]
                age = time.monotonic() - head.committed_at
                later_ready = any(e.status == "done" for e in list(self._order)[1:])
                if (later_ready and age >= reorder_s) or age >= hard_s:
                    self._order.popleft()
                    self._by_seg.pop(head.seg, None)
                    self._skipped.add(head.seg)
                    await self.rt.hub.broadcast(self.rt.sid, "stt.notice", {
                        "level": "error",
                        "message": f"앞 음성 구간의 전사 결과가 {age:.1f}초 동안 오지 않아 건너뛰었습니다."})
                    await self._flush()

    # ------------------------------------------------------------ 오디오 / VAD
    async def on_audio(self, chunk: bytes) -> None:
        if not self.active:
            return
        if len(chunk) % 2 != 0:
            raise AudioFormatError("PCM16 프레임 길이가 홀수입니다")
        arrival = time.monotonic()
        data = self._carry + chunk
        n_frames = len(data) // self.frame_bytes
        self._carry = data[n_frames * self.frame_bytes:]
        for i in range(n_frames):
            frame = data[i * self.frame_bytes:(i + 1) * self.frame_bytes]
            # 청크 안 프레임별 도착 시각 추정 (마지막 프레임 = 청크 도착 시각)
            t_frame = arrival - (n_frames - 1 - i) * FRAME_MS / 1000
            await self._process_frame(frame, t_frame)

    def _discard_candidate(self) -> None:
        self._held = []
        self._state = "idle"
        self._local_seg = None
        self.discarded_short += 1

    async def _process_frame(self, frame: bytes, t: float) -> None:
        self.frames_in += 1
        x = np.frombuffer(frame, dtype="<i2").astype(np.float32)
        rms = float(np.sqrt(np.mean(x * x))) if x.size else 0.0
        voiced = rms >= self.s.vad_rms_threshold

        if self._state == "idle":
            self._preroll.append(frame)
            if voiced:
                self._state = "candidate"
                self._held = list(self._preroll)
                self._preroll.clear()
                self._voiced_ms = FRAME_MS
                self._silence_ms = 0
                self._seg_ms = len(self._held) * FRAME_MS
                self._last_voice_mono = t
            return

        self._seg_ms += FRAME_MS
        if voiced:
            self._voiced_ms += FRAME_MS
            self._silence_ms = 0
            self._last_voice_mono = t
            self.rt.detector.feed_partial(t)  # 말하는 중 → 요청 침묵 타이머 연장
        else:
            self._silence_ms += FRAME_MS

        if self._state == "candidate":
            self._held.append(frame)
            if self._voiced_ms >= self.s.vad_min_speech_ms:
                # 발화로 확정 → 보관분을 STT 로 전송
                self._state = "speech"
                self._seg_no += 1
                self._local_seg = f"v{self._seg_no}"
                for f in self._held:
                    await self.p.send_audio(f)
                self._held = []
                await self.rt.hub.broadcast(self.rt.sid, "stt.vad", {"speaking": True})
            elif self._silence_ms >= self.s.vad_silence_ms:
                self._discard_candidate()  # 최소 발화 길이 미만 → STT 로 보내지 않음
            return

        # speech
        await self.p.send_audio(frame)
        if self._silence_ms >= self.s.vad_silence_ms or self._seg_ms >= self.s.vad_max_segment_ms:
            await self._commit()

    async def _commit(self) -> None:
        if self._state != "speech" or self._local_seg is None:
            return
        seg = self._local_seg
        if self._last_voice_mono is not None:
            self.local_speech_end[seg] = self._last_voice_mono
        self._state = "idle"
        self._local_seg = None
        self.committed += 1
        ent = _Pending(seg, time.monotonic())
        async with self._order_lock:
            self._order.append(ent)
            self._by_seg[seg] = ent
        await self.p.commit(seg)
        await self.rt.hub.broadcast(self.rt.sid, "stt.vad", {"speaking": False})
