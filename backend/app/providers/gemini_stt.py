"""Gemini Live 전사 어댑터 (gemini-3.5-transcribe-live) — 서버에서 WebSocket 으로 중계한다(키는 서버에만 존재).

공식 문서 기준 (Live transcription 가이드, Live API reference, 2026-11-05 확인):
- 연결: wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent?key=<API 키>
  → URL 에 키가 들어가므로 URL 을 로그·오류 메시지에 절대 넣지 않는다.
- setup: model "models/<모델>", generationConfig.responseModalities ["TEXT"], inputAudioTranscription.languageCodes
  (한국어 ko-KR 지원), realtimeInputConfig.automaticActivityDetection.disabled=true (수동 활동 감지)
- 서버는 setup 이 끝나면 setupComplete({}) 를 보낸다 → 그 뒤에만 ready.
  OpenAI 와 달리 실제 반영된 설정을 돌려주지 않으므로 모델·언어·형식 반영 여부는 프로토콜상 확인할 수 없다.
- 오디오: realtimeInput.audio {data: base64 PCM16 LE mono, mimeType: "audio/pcm;rate=16000"}, 약 100ms 청크
- 수동 활동 감지: 구간 시작 activityStart {}, 끝 activityEnd {} (우리 서버 VAD 가 구간 경계를 정함)
- 결과: serverContent.interimInputTranscription.text (임시), serverContent.inputTranscription.text (구간 확정).
  구간 ID 가 없으므로 한 연결 안에서는 순서대로 온다고 보고(ordered_finals) 구간 매핑은 지표용으로만 쓴다.
- 서버의 goAway(timeLeft) 는 곧 연결이 끊긴다는 뜻. 라이브 전사 세션은 최대 10분 → 그 전에 쉬는 구간에서 새 세션으로 교체.
"""
from __future__ import annotations

import asyncio
import base64
import collections
import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Optional

import websockets
from websockets.asyncio.client import ClientConnection, connect

from .base import SttCallback, SttEvent, SttSessionError

log = logging.getLogger("nextslide.stt.gemini")
ENDPOINT = "wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent"


@dataclass
class _Conn:
    no: int
    ws: ClientConnection
    started: float
    ready: asyncio.Future
    reader: Optional[asyncio.Task] = None
    audio_s: float = 0.0
    pending: collections.deque = field(default_factory=collections.deque)  # 확정 결과를 기다리는 로컬 구간
    goaway: bool = False
    final_no: int = 0


class GeminiSttProvider:
    name = "gemini"
    is_mock = False
    ordered_finals = True

    def __init__(self, model: str, languages: list[str], mode: str = "VERBATIM", vocabulary: Optional[list[str]] = None,
                 sample_rate: int = 16000, max_reconnects: int = 3, ack_timeout_s: float = 10.0,
                 rotate_s: float = 480.0):
        self.model = model
        self.languages = languages
        self.mode = mode
        self.vocabulary = vocabulary or []
        self.sample_rate = sample_rate
        self.max_reconnects = max_reconnects
        self.ack_timeout_s = ack_timeout_s
        self.rotate_s = rotate_s
        self._on: Optional[SttCallback] = None
        self._conn: Optional[_Conn] = None
        self._conn_no = 0
        self._closing = False
        self._in_activity = False
        self._activity_conn: Optional[_Conn] = None
        self._rotating = False
        self._send_lock = asyncio.Lock()
        self.audio_seconds_sent = 0.0
        self.effective_session: Optional[dict] = None
        self.session_check: dict = {}
        self.rotations = 0

    # ------------------------------------------------------------ 연결
    def _setup_msg(self) -> dict:
        transcription: dict = {"languageCodes": self.languages}
        if self.mode and self.mode.upper() != "VERBATIM":  # VERBATIM 은 문서상 기본값 → 보내지 않음
            transcription["mode"] = self.mode.upper()
        if self.vocabulary:
            transcription["customVocabulary"] = self.vocabulary  # 요소 형식은 실제 API 로 미검증
        return {
            "setup": {
                "model": f"models/{self.model}",
                "generationConfig": {"responseModalities": ["TEXT"]},
                "inputAudioTranscription": transcription,
                "realtimeInputConfig": {"automaticActivityDetection": {"disabled": True}},
            }
        }

    async def _emit(self, ev: SttEvent) -> None:
        if self._on:
            await self._on(ev)

    async def start(self, on_event: SttCallback) -> None:
        self._on = on_event
        try:
            self._conn = await self._open()
        except SttSessionError as e:
            await self._emit(SttEvent("status", state="error", message=str(e)))
            raise
        await self._emit(SttEvent("status", state="ready",
                                  message=f"STT 연결됨 ({self.model}, setupComplete 수신 — 실제 반영 설정은 프로토콜상 확인 불가)"))

    async def _open(self) -> _Conn:
        key = os.environ.get("GEMINI_API_KEY")
        if not key:
            raise SttSessionError("GEMINI_API_KEY 가 설정되지 않았습니다", "config")
        self._conn_no += 1
        await self._emit(SttEvent("status", state="connecting", message="STT 서버 연결 중 (setupComplete 대기)"))
        try:
            ws = await connect(f"{ENDPOINT}?key={key}", max_size=8 * 1024 * 1024, open_timeout=10)
        except websockets.InvalidStatus as e:
            code = e.response.status_code
            raise SttSessionError(f"STT 연결 거부 (HTTP {code}{', 인증 실패: API 키 확인' if code in (401, 403) else ''})",
                                  "http_rejected", code) from None
        except (OSError, asyncio.TimeoutError, websockets.WebSocketException) as e:
            raise SttSessionError(f"STT 서버에 연결할 수 없습니다 ({type(e).__name__})", "connect_failed") from None
        conn = _Conn(no=self._conn_no, ws=ws, started=time.monotonic(),
                     ready=asyncio.get_running_loop().create_future())
        conn.reader = asyncio.create_task(self._read_loop(conn))
        await ws.send(json.dumps(self._setup_msg()))
        try:
            await asyncio.wait_for(asyncio.shield(conn.ready), timeout=self.ack_timeout_s)
        except asyncio.TimeoutError:
            conn.ready.cancel()
            await self._close_conn(conn)
            raise SttSessionError(f"STT 설정 완료 응답(setupComplete)이 {self.ack_timeout_s:.0f}초 안에 오지 않았습니다",
                                  "ack_timeout") from None
        except SttSessionError:
            await self._close_conn(conn)
            raise
        self.effective_session = {"setupComplete": True}
        self.session_check = {"verified": ["setupComplete"], "missing": [],
                              "not_verifiable_by_protocol": ["model", "languageCodes", "audio format"],
                              "strict": False}
        return conn

    async def _close_conn(self, conn: _Conn) -> None:
        try:
            await conn.ws.close()
        except Exception:  # noqa: BLE001
            pass
        if conn.reader:
            conn.reader.cancel()

    # ------------------------------------------------------------ 수신
    async def _read_loop(self, conn: _Conn) -> None:
        close_info = ""
        try:
            async for raw in conn.ws:
                try:
                    msg = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    continue
                await self._handle(conn, msg)
        except websockets.ConnectionClosed as e:
            rcvd = getattr(e, "rcvd", None)
            if rcvd is not None:
                close_info = f"code {rcvd.code}: {(rcvd.reason or '')[:200]}"
        except Exception as e:  # noqa: BLE001
            log.warning("Gemini STT read loop error: %s", type(e).__name__)
        if not close_info and conn.ws.close_code is not None:
            close_info = f"code {conn.ws.close_code}: {(conn.ws.close_reason or '')[:200]}"
        if not conn.ready.done():
            stage = "rejected" if close_info and not close_info.startswith("code 1000") else "closed_before_ack"
            conn.ready.set_exception(SttSessionError(f"STT 서버가 설정 완료 전에 연결을 닫았습니다 ({close_info or '사유 없음'})",
                                                     stage))
            return
        if self._closing or conn is not self._conn:
            return  # 정상 종료 또는 교체된 이전 연결
        self._conn = None
        lost = list(conn.pending)
        conn.pending.clear()
        if self._in_activity and self._activity_conn is conn:
            self._in_activity = False
            lost.append("(진행 중 구간)")
        if lost:
            await self._emit(SttEvent("error", message=f"STT 연결 끊김 ({close_info or '사유 없음'}): 전사 중이던 음성 구간 {len(lost)}개를 잃었습니다"))
        asyncio.create_task(self._reconnect())

    async def _handle(self, conn: _Conn, msg: dict) -> None:
        if "setupComplete" in msg:
            if not conn.ready.done():
                conn.ready.set_result(True)
            return
        if "goAway" in msg:
            conn.goaway = True
            asyncio.create_task(self._maybe_rotate())
            return
        sc = msg.get("serverContent") or {}
        interim = sc.get("interimInputTranscription")
        if isinstance(interim, dict) and interim.get("text") is not None:
            await self._emit(SttEvent("partial", segment_id=f"g{conn.no}:live", text=interim.get("text") or ""))
        fin = sc.get("inputTranscription")
        if isinstance(fin, dict) and fin.get("text") is not None:
            conn.final_no += 1
            local = conn.pending.popleft() if conn.pending else None
            await self._emit(SttEvent("final", segment_id=f"g{conn.no}:{conn.final_no}", text=fin.get("text") or "",
                                      local_segment=local))
            asyncio.create_task(self._maybe_rotate())

    async def _reconnect(self) -> None:
        for attempt in range(1, self.max_reconnects + 1):
            if self._closing:
                return
            await self._emit(SttEvent("status", state="reconnecting",
                                      message=f"STT 연결 끊김 — 재연결 시도 {attempt}/{self.max_reconnects}"))
            await asyncio.sleep(min(0.5 * 2 ** (attempt - 1), 4.0))
            try:
                self._conn = await self._open()
                await self._emit(SttEvent("status", state="ready", message=f"STT 재연결됨 ({self.model})"))
                return
            except SttSessionError as e:
                log.warning("Gemini STT reconnect failed: %s", e)
        await self._emit(SttEvent("status", state="error",
                                  message="STT 재연결 실패. 마이크를 다시 시작하거나 텍스트 입력을 사용하세요."))

    # ------------------------------------------------------------ 세션 교체 (10분 제한 대비)
    async def _maybe_rotate(self) -> None:
        c = self._conn
        if self._rotating or c is None or self._closing:
            return
        if not (c.goaway or time.monotonic() - c.started >= self.rotate_s or c.audio_s >= self.rotate_s):
            return
        self._rotating = True
        try:
            new = await self._open()  # 새 세션을 먼저 연다 (make-before-break)
        except SttSessionError as e:
            self._rotating = False
            await self._emit(SttEvent("status", state="degraded", message=f"STT 세션 교체 실패: {e}"))
            return
        # 진행 중 구간이 끝나고 이전 세션의 확정 결과가 모두 올 때까지 잠시 기다린 뒤 전환
        deadline = time.monotonic() + 5.0
        while (self._in_activity and self._activity_conn is c or c.pending) and time.monotonic() < deadline:
            await asyncio.sleep(0.05)
        self._conn = new
        self.rotations += 1
        if c.pending:
            await self._emit(SttEvent("error", message=f"STT 세션 교체 중 확정 결과를 받지 못한 구간 {len(c.pending)}개"))
        await self._close_conn(c)
        self._rotating = False
        await self._emit(SttEvent("status", state="ready", message=f"STT 세션 교체 완료 ({self.model})"))

    # ------------------------------------------------------------ 송신
    async def _send(self, conn: _Conn, obj: dict) -> bool:
        try:
            async with self._send_lock:
                await conn.ws.send(json.dumps(obj))
            return True
        except websockets.ConnectionClosed:
            return False

    async def send_audio(self, pcm16: bytes) -> None:
        conn = self._activity_conn if self._in_activity else self._conn
        if conn is None:
            return  # 재연결 중: 이 오디오는 전사되지 않음(상태 이벤트로 이미 알림)
        if not self._in_activity:
            if not await self._send(conn, {"realtimeInput": {"activityStart": {}}}):
                return
            self._in_activity = True
            self._activity_conn = conn
        ok = await self._send(conn, {"realtimeInput": {"audio": {
            "data": base64.b64encode(pcm16).decode("ascii"), "mimeType": f"audio/pcm;rate={self.sample_rate}"}}})
        if ok:
            secs = len(pcm16) / 2 / self.sample_rate
            conn.audio_s += secs
            self.audio_seconds_sent += secs

    async def commit(self, local_segment: str) -> None:
        conn = self._activity_conn
        if not self._in_activity or conn is None:
            return
        self._in_activity = False
        self._activity_conn = None
        conn.pending.append(local_segment)
        await self._send(conn, {"realtimeInput": {"activityEnd": {}}})
        asyncio.create_task(self._maybe_rotate())

    async def close(self) -> None:
        self._closing = True
        conn, self._conn = self._conn, None
        if conn is not None:
            await self._close_conn(conn)
        await self._emit(SttEvent("status", state="stopped", message="STT 중지"))
