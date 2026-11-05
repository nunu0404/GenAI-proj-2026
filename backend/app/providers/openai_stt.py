"""OpenAI Realtime 전사(transcription) 어댑터 — 서버에서 WebSocket 으로 중계한다(키는 서버에만 존재).

공식 문서 기준 (developers.openai.com, 2026-11-05 확인):
- 연결: wss://api.openai.com/v1/realtime?intent=transcription, 헤더 Authorization: Bearer <key>
  (헤더 형식은 Realtime/WebSocket 문서 기준. 실제 계정으로 연결해 본 적은 아직 없음)
- session.update: session.type="transcription", audio.input.format={type:"audio/pcm", rate:24000} (PCM16 mono)
- gpt-live-transcribe: server_vad / semantic_vad 미지원 → turn_detection=null. 클라이언트 측 VAD 로 발화 끝을
  감지해 input_audio_buffer.commit 을 보낸다. 언어는 'languages' 배열(단수 language 와 함께 보내지 말 것), 지연은 'delay'.
- 서버는 session.update 가 적용되면 실제 반영된 설정 전체를 담은 session.updated 를 보내고, 문제가 있으면 error 를 보낸다
  → session.updated 를 받은 뒤에만 'ready' 로 알린다.
- 이벤트: input_audio_buffer.committed(item_id), conversation.item.input_audio_transcription.delta/completed/failed(item_id)
- 서로 다른 구간의 completed 순서는 보장되지 않음 → item_id 로 매칭하고, 순서 보정은 상위(SttStream)에서 한다.
"""
from __future__ import annotations

import asyncio
import base64
import collections
import json
import logging
import os
from typing import Optional

import websockets
from websockets.asyncio.client import ClientConnection, connect

from .base import SttCallback, SttEvent

log = logging.getLogger("nextslide.stt")
URL = "wss://api.openai.com/v1/realtime?intent=transcription"
ACK_EVENTS = {"session.updated", "transcription_session.updated"}


class SttSessionError(RuntimeError):
    """설정 거부·승인 시간 초과·인증 실패 등 연결 단계 실패. 메시지는 사용자에게 보여도 되는 내용만 담는다."""


class OpenAISttProvider:
    name = "openai"
    is_mock = False

    def __init__(self, model: str, languages: list[str], delay: str, sample_rate: int, max_reconnects: int = 3,
                 ack_timeout_s: float = 10.0):
        self.model = model
        self.languages = languages
        self.delay = delay
        self.sample_rate = sample_rate
        self.max_reconnects = max_reconnects
        self.ack_timeout_s = ack_timeout_s
        self._ws: Optional[ClientConnection] = None
        self._reader: Optional[asyncio.Task] = None
        self._on_event: Optional[SttCallback] = None
        self._conn_no = 0
        self._closing = False
        self._ready = False
        self._ack: Optional[asyncio.Future] = None
        self._pending_commits: collections.deque[str] = collections.deque()
        self._item_to_local: dict[str, str] = {}
        self._partials: dict[str, str] = {}
        self._completed: set[str] = set()
        self._send_lock = asyncio.Lock()
        self.audio_seconds_sent = 0.0
        self.effective_session: Optional[dict] = None

    def _session_update(self) -> dict:
        transcription: dict = {"model": self.model}
        if self.model == "gpt-live-transcribe":
            transcription["languages"] = self.languages
            if self.delay:
                transcription["delay"] = self.delay
        else:
            transcription["language"] = self.languages[0] if self.languages else "ko"
        return {
            "type": "session.update",
            "session": {
                "type": "transcription",
                "audio": {
                    "input": {
                        "format": {"type": "audio/pcm", "rate": self.sample_rate},
                        "transcription": transcription,
                        "turn_detection": None,  # gpt-live-transcribe: server_vad/semantic_vad 미지원
                    }
                },
            },
        }

    async def _emit(self, ev: SttEvent) -> None:
        if self._on_event:
            await self._on_event(ev)

    async def start(self, on_event: SttCallback) -> None:
        self._on_event = on_event
        try:
            await self._connect()
        except SttSessionError as e:
            await self._emit(SttEvent("status", state="error", message=str(e)))
            raise

    async def _connect(self) -> None:
        key = os.environ.get("OPENAI_API_KEY")
        if not key:
            raise SttSessionError("OPENAI_API_KEY 가 설정되지 않았습니다")
        self._conn_no += 1
        self._ready = False
        await self._emit(SttEvent("status", state="connecting", message="STT 서버 연결 중 (설정 승인 대기)"))
        try:
            ws = await connect(URL, additional_headers={"Authorization": f"Bearer {key}"},
                               max_size=8 * 1024 * 1024, open_timeout=10)
        except websockets.InvalidStatus as e:
            code = e.response.status_code
            raise SttSessionError(f"STT 연결 거부 (HTTP {code}{', 인증 실패: API 키 확인' if code in (401, 403) else ''})") from e
        except (OSError, asyncio.TimeoutError, websockets.WebSocketException) as e:
            raise SttSessionError(f"STT 서버에 연결할 수 없습니다 ({type(e).__name__})") from e
        self._ack = asyncio.get_running_loop().create_future()
        self._ws = ws
        self._reader = asyncio.create_task(self._read_loop(ws, self._conn_no))
        await ws.send(json.dumps(self._session_update()))
        try:
            session = await asyncio.wait_for(asyncio.shield(self._ack), timeout=self.ack_timeout_s)
        except asyncio.TimeoutError as e:
            self._ack.cancel()
            await self._abort(ws)
            raise SttSessionError(f"STT 설정 승인 응답(session.updated)이 {self.ack_timeout_s:.0f}초 안에 오지 않았습니다") from e
        except SttSessionError:
            await self._abort(ws)
            raise
        problem = self._check_effective(session)
        if problem:
            await self._abort(ws)
            raise SttSessionError(problem)
        self.effective_session = session
        self._ready = True
        await self._emit(SttEvent("status", state="ready", message=f"STT 설정 승인됨 ({self.model})"))

    def _check_effective(self, session: dict) -> Optional[str]:
        """서버가 돌려준 실제 반영 설정이 요청과 다르면 문제로 본다(필드가 없으면 판단하지 않음)."""
        inp = ((session or {}).get("audio") or {}).get("input") or {}
        model = (inp.get("transcription") or {}).get("model")
        if model and model != self.model:
            return f"STT 모델이 요청({self.model})과 다르게 설정됨: {model}"
        fmt = inp.get("format") or {}
        if fmt.get("rate") and fmt.get("rate") != self.sample_rate:
            return f"STT 오디오 샘플레이트가 요청({self.sample_rate})과 다름: {fmt.get('rate')}"
        if inp.get("turn_detection") not in (None, {}):
            return "STT 서버가 turn_detection 을 활성화했습니다 (gpt-live-transcribe 는 null 이어야 함)"
        return None

    async def _abort(self, ws: ClientConnection) -> None:
        if self._ws is ws:
            self._ws = None
        try:
            await ws.close()
        except Exception:  # noqa: BLE001
            pass

    async def _fail_pending(self, reason: str) -> None:
        """연결이 끊겨 결과를 받을 수 없게 된 구간을 상위에 실패로 알린다(순서 보정 대기 해제)."""
        lost = list(self._pending_commits) + list(self._item_to_local.values())
        self._pending_commits.clear()
        self._item_to_local.clear()
        self._partials.clear()
        for loc in lost:
            await self._emit(SttEvent("segment_failed", local_segment=loc))
        if lost:
            await self._emit(SttEvent("error", message=f"{reason}: 전사 중이던 음성 구간 {len(lost)}개를 잃었습니다"))

    async def _reconnect(self) -> None:
        await self._fail_pending("STT 연결 끊김")
        for attempt in range(1, self.max_reconnects + 1):
            if self._closing:
                return
            await self._emit(SttEvent("status", state="reconnecting",
                                      message=f"STT 연결 끊김 — 재연결 시도 {attempt}/{self.max_reconnects}"))
            await asyncio.sleep(min(0.5 * 2 ** (attempt - 1), 4.0))
            try:
                await self._connect()
                return
            except SttSessionError as e:
                log.warning("STT reconnect failed: %s", e)
        await self._emit(SttEvent("status", state="error",
                                  message="STT 재연결 실패. 마이크를 다시 시작하거나 텍스트 입력을 사용하세요."))

    async def _read_loop(self, ws: ClientConnection, conn_no: int) -> None:
        try:
            async for raw in ws:
                try:
                    ev = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                await self._handle(ev, conn_no)
        except websockets.ConnectionClosed:
            pass
        except Exception as e:  # noqa: BLE001
            log.warning("STT read loop error: %s", type(e).__name__)
        if self._ack is not None and not self._ack.done():
            self._ack.set_exception(SttSessionError("STT 서버가 설정 승인 전에 연결을 닫았습니다"))
            return
        if not self._closing and ws is self._ws and self._ready:
            self._ws = None
            self._ready = False
            asyncio.create_task(self._reconnect())

    async def _handle(self, ev: dict, conn_no: int) -> None:
        t = ev.get("type", "")
        item = ev.get("item_id")
        seg = f"c{conn_no}:{item}" if item else None
        if t in ACK_EVENTS:
            if self._ack is not None and not self._ack.done():
                self._ack.set_result(ev.get("session") or {})
            return
        if t == "error":
            err = ev.get("error") or {}
            msg = str(err.get("message") or "STT 오류")[:200]
            code = str(err.get("code") or "")
            if self._ack is not None and not self._ack.done():
                self._ack.set_exception(SttSessionError(f"STT 설정이 거부되었습니다: {msg}"))
                return
            if "empty" in code or "buffer too small" in msg.lower():
                # 오디오가 부족한 commit 거부 → 해당 구간은 결과가 오지 않으므로 실패 처리
                if self._pending_commits:
                    await self._emit(SttEvent("segment_failed", local_segment=self._pending_commits.popleft()))
                return
            await self._emit(SttEvent("status", state="degraded", message=f"STT 오류: {msg}"))
            return
        if t == "input_audio_buffer.committed" and item:
            if self._pending_commits:
                self._item_to_local[item] = self._pending_commits.popleft()
        elif t == "conversation.item.input_audio_transcription.delta" and item:
            self._partials[item] = self._partials.get(item, "") + (ev.get("delta") or "")
            await self._emit(SttEvent("partial", segment_id=seg, text=self._partials[item],
                                      local_segment=self._item_to_local.get(item)))
        elif t == "conversation.item.input_audio_transcription.completed" and item:
            if seg in self._completed:
                return  # 중복 완료 이벤트
            self._completed.add(seg)  # type: ignore[arg-type]
            self._partials.pop(item, None)
            await self._emit(SttEvent("final", segment_id=seg, text=ev.get("transcript") or "",
                                      local_segment=self._item_to_local.pop(item, None)))
        elif t == "conversation.item.input_audio_transcription.failed" and item:
            self._partials.pop(item, None)
            await self._emit(SttEvent("segment_failed", segment_id=seg, local_segment=self._item_to_local.pop(item, None),
                                      message="한 음성 구간의 전사에 실패했습니다"))

    async def send_audio(self, pcm16: bytes) -> None:
        ws = self._ws
        if ws is None or not self._ready:
            return  # 재연결 중: 이 오디오는 전사되지 않음(상태 이벤트로 이미 알림)
        msg = json.dumps({"type": "input_audio_buffer.append", "audio": base64.b64encode(pcm16).decode("ascii")})
        try:
            async with self._send_lock:
                await ws.send(msg)
            self.audio_seconds_sent += len(pcm16) / 2 / self.sample_rate
        except websockets.ConnectionClosed:
            pass

    async def commit(self, local_segment: str) -> None:
        ws = self._ws
        if ws is None or not self._ready:
            await self._emit(SttEvent("segment_failed", local_segment=local_segment))
            return
        self._pending_commits.append(local_segment)
        try:
            async with self._send_lock:
                await ws.send(json.dumps({"type": "input_audio_buffer.commit"}))
        except websockets.ConnectionClosed:
            pass  # 읽기 루프가 끊김을 감지해 대기 구간을 실패 처리하고 재연결한다

    async def close(self) -> None:
        self._closing = True
        ws, self._ws = self._ws, None
        if ws is not None:
            try:
                await ws.close()
            except Exception:  # noqa: BLE001
                pass
        if self._reader:
            self._reader.cancel()
        await self._emit(SttEvent("status", state="stopped", message="STT 중지"))
