"""브라우저 마이크 오디오(PCM16 LE mono 24kHz) → 서버 VAD → STT 제공자 중계.

- 브라우저는 AudioWorklet 에서 24kHz 로 리샘플링한 PCM16 을 보낸다. 서버는 mic_start 의 형식 선언을 검증하고
  다르면 거부한다(지원하지 않는 형식을 STT 로 보내지 않음).
- VAD: 20ms 프레임 RMS 기반. 침묵이 VAD_SILENCE_MS 이상 이어지면 구간을 commit 한다.
- 발화 종료 '추정' 시각 = 마지막 유성 프레임이 서버에 도착한 단조 시각(브라우저→서버 전송 지연 미포함).
"""
from __future__ import annotations

import asyncio
import collections
import logging
import time
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


class SttStream:
    def __init__(self, rt: "SessionRuntime", provider: SttProvider, s: Settings):
        self.rt = rt
        self.p = provider
        self.s = s
        self.active = False
        self.frame_bytes = s.stt_sample_rate * FRAME_MS // 1000 * 2
        self._carry = b""
        self._preroll: collections.deque[bytes] = collections.deque(maxlen=max(1, s.vad_preroll_ms // FRAME_MS))
        self._in_speech = False
        self._speech_ms = 0
        self._silence_ms = 0
        self._seg_ms = 0
        self._seg_no = 0
        self._local_seg: Optional[str] = None
        self._last_voice_mono: Optional[float] = None
        self.local_speech_end: dict[str, float] = {}
        self.started_mono: Optional[float] = None
        self.frames_in = 0

    async def start(self) -> None:
        self.active = True
        self.started_mono = time.monotonic()
        await self.p.start(self._on_event)

    async def _on_event(self, ev: SttEvent) -> None:
        sid = self.rt.sid
        if ev.type == "partial":
            await self.rt.handle_partial(ev.segment_id, ev.text or "")
        elif ev.type == "final":
            end = self.local_speech_end.pop(ev.local_segment, None) if ev.local_segment else None
            await self.rt.handle_final(ev.segment_id or f"stt-{time.time()}", ev.text or "", "stt", speech_end_mono=end)
        elif ev.type == "status":
            await self.rt.hub.broadcast(sid, "stt.status", {"state": ev.state, "message": ev.message})
        elif ev.type in ("error", "notice"):
            await self.rt.hub.broadcast(sid, "stt.notice", {"level": ev.type, "message": ev.message})

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

    async def _process_frame(self, frame: bytes, t: float) -> None:
        self.frames_in += 1
        x = np.frombuffer(frame, dtype="<i2").astype(np.float32)
        rms = float(np.sqrt(np.mean(x * x))) if x.size else 0.0
        voiced = rms >= self.s.vad_rms_threshold
        if not self._in_speech:
            self._preroll.append(frame)
            if voiced:
                self._in_speech = True
                self._seg_no += 1
                self._local_seg = f"v{self._seg_no}"
                self._speech_ms = self._silence_ms = self._seg_ms = 0
                for f in self._preroll:
                    await self.p.send_audio(f)
                self._seg_ms = len(self._preroll) * FRAME_MS
                self._preroll.clear()
                self._last_voice_mono = t
                await self.rt.hub.broadcast(self.rt.sid, "stt.vad", {"speaking": True})
            return
        await self.p.send_audio(frame)
        self._seg_ms += FRAME_MS
        if voiced:
            self._speech_ms += FRAME_MS
            self._silence_ms = 0
            self._last_voice_mono = t
            self.rt.detector.feed_partial(t)  # 말하는 중 → 요청 침묵 타이머 연장
        else:
            self._silence_ms += FRAME_MS
        if self._silence_ms >= self.s.vad_silence_ms or self._seg_ms >= self.s.vad_max_segment_ms:
            await self._commit()

    async def _commit(self) -> None:
        if not self._in_speech or self._local_seg is None:
            return
        seg = self._local_seg
        if self._last_voice_mono is not None:
            self.local_speech_end[seg] = self._last_voice_mono
        self._in_speech = False
        self._local_seg = None
        await self.p.commit(seg)
        await self.rt.hub.broadcast(self.rt.sid, "stt.vad", {"speaking": False})

    async def stop(self) -> None:
        if not self.active:
            return
        self.active = False
        if self._in_speech:
            await self._commit()
            await asyncio.sleep(1.5)  # 마지막 구간 확정 결과를 잠시 기다림
        await self.p.close()
        secs = getattr(self.p, "audio_seconds_sent", None)
        if secs:
            self.rt._log_usage(None, Usage(provider=self.p.name, model=self.p.model, kind="stt", audio_seconds=secs),
                               "used")
