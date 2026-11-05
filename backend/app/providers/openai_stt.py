"""OpenAI Realtime 전사(transcription) 어댑터 — 서버에서 WebSocket 으로 중계한다(키는 서버에만 존재).

공식 문서(developers.openai.com/api/docs/guides/realtime-transcription, 2026-11-05 확인) 기준:
- URL: wss://api.openai.com/v1/realtime?intent=transcription, 헤더 Authorization: Bearer <key>
- session.update: session.type="transcription", audio.input.format={type:"audio/pcm", rate:24000} (PCM16 mono)
- gpt-live-transcribe: turn_detection 은 null (server_vad 미지원) → 클라이언트 측 VAD 로 구간 끝에서
  input_audio_buffer.commit 을 보낸다. 언어는 'languages' 배열, 지연은 'delay'.
- 이벤트: input_audio_buffer.committed(item_id), conversation.item.input_audio_transcription.delta(item_id, delta),
  ...completed(item_id, transcript), ...failed(item_id), error
- 서로 다른 구간의 completed 순서는 보장되지 않음 → item_id 로 매칭.
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


class OpenAISttProvider:
    name = "openai"
    is_mock = False

    def __init__(self, model: str, languages: list[str], delay: str, sample_rate: int, max_reconnects: int = 3):
        self.model = model
        self.languages = languages
        self.delay = delay
        self.sample_rate = sample_rate
        self.max_reconnects = max_reconnects
        self._ws: Optional[ClientConnection] = None
        self._reader: Optional[asyncio.Task] = None
        self._on_event: Optional[SttCallback] = None
        self._conn_no = 0
        self._closing = False
        self._pending_commits: collections.deque[str] = collections.deque()
        self._item_to_local: dict[str, str] = {}
        self._partials: dict[str, str] = {}
        self._completed: set[str] = set()
        self._send_lock = asyncio.Lock()
        self.audio_seconds_sent = 0.0

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
                        "turn_detection": None,
                    }
                },
            },
        }

    async def _emit(self, ev: SttEvent) -> None:
        if self._on_event:
            await self._on_event(ev)

    async def start(self, on_event: SttCallback) -> None:
        self._on_event = on_event
        await self._connect()

    async def _connect(self) -> None:
        key = os.environ.get("OPENAI_API_KEY")
        if not key:
            await self._emit(SttEvent("status", state="error", message="OPENAI_API_KEY 가 설정되지 않았습니다"))
            raise RuntimeError("missing OPENAI_API_KEY")
        self._conn_no += 1
        await self._emit(SttEvent("status", state="connecting", message="STT 서버 연결 중"))
        self._ws = await connect(URL, additional_headers={"Authorization": f"Bearer {key}"}, max_size=8 * 1024 * 1024,
                                 open_timeout=10)
        await self._ws.send(json.dumps(self._session_update()))
        self._reader = asyncio.create_task(self._read_loop(self._ws, self._conn_no))
        await self._emit(SttEvent("status", state="ready", message=f"STT 연결됨 ({self.model})"))

    async def _reconnect(self) -> None:
        for attempt in range(1, self.max_reconnects + 1):
            if self._closing:
                return
            await self._emit(SttEvent("status", state="reconnecting",
                                      message=f"STT 연결 끊김 — 재연결 시도 {attempt}/{self.max_reconnects}"))
            await asyncio.sleep(min(0.5 * 2 ** (attempt - 1), 4.0))
            try:
                # 끊긴 연결에서 커밋 대기 중이던 구간은 결과를 받을 수 없으므로 정리
                self._pending_commits.clear()
                await self._connect()
                return
            except Exception as e:  # noqa: BLE001
                log.warning("STT reconnect failed: %s", type(e).__name__)
        await self._emit(SttEvent("status", state="error", message="STT 재연결 실패. 마이크를 다시 시작하거나 텍스트 입력을 사용하세요."))

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
        if not self._closing and ws is self._ws:
            self._ws = None
            asyncio.create_task(self._reconnect())

    async def _handle(self, ev: dict, conn_no: int) -> None:
        t = ev.get("type", "")
        item = ev.get("item_id")
        seg = f"c{conn_no}:{item}" if item else None
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
        elif t == "conversation.item.input_audio_transcription.failed":
            await self._emit(SttEvent("notice", segment_id=seg, message="한 구간의 음성 인식에 실패했습니다"))
        elif t == "error":
            err = ev.get("error") or {}
            msg = str(err.get("message") or "STT 오류")[:200]
            code = str(err.get("code") or "")
            if "empty" in code or "buffer too small" in msg.lower():
                return  # 빈 커밋은 무시
            await self._emit(SttEvent("error", message=msg))

    async def send_audio(self, pcm16: bytes) -> None:
        ws = self._ws
        if ws is None:
            return  # 재연결 중: 이 구간 오디오는 전사되지 않음(상태 이벤트로 이미 알림)
        self.audio_seconds_sent += len(pcm16) / 2 / self.sample_rate
        msg = json.dumps({"type": "input_audio_buffer.append", "audio": base64.b64encode(pcm16).decode("ascii")})
        try:
            async with self._send_lock:
                await ws.send(msg)
        except websockets.ConnectionClosed:
            pass

    async def commit(self, local_segment: str) -> None:
        ws = self._ws
        if ws is None:
            return
        self._pending_commits.append(local_segment)
        try:
            async with self._send_lock:
                await ws.send(json.dumps({"type": "input_audio_buffer.commit"}))
        except websockets.ConnectionClosed:
            pass

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
