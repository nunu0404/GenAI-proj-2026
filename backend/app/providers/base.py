"""제공자 어댑터 인터페이스. 음성 인식·텍스트 생성·이미지 생성을 각각 분리한다."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional, Protocol


class ProviderError(Exception):
    """code: timeout | rate_limited | refused | no_image | bad_format | invalid_output | auth | network | upstream | config"""

    def __init__(self, code: str, message: str, retryable: bool = False, usage: Optional["Usage"] = None,
                 http_status: Optional[int] = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable
        self.usage = usage
        # 서버가 HTTP 응답을 돌려줬으면 그 상태 코드(200 응답인데 내용이 잘못된 경우 200).
        # None = 응답을 받지 못함(연결 실패·시간 초과).
        self.http_status = http_status


@dataclass
class Usage:
    provider: str
    model: str
    kind: str  # text | image | stt
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    image_count: Optional[int] = None
    audio_seconds: Optional[float] = None
    settings: dict = field(default_factory=dict)
    # 이미지 모델처럼 입력 토큰 종류가 나뉠 때
    detail: dict = field(default_factory=dict)


@dataclass
class TextResult:
    raw_text: str
    usage: Usage


@dataclass
class ImageResult:
    data: bytes
    mime: str
    width: int
    height: int
    prompt: str
    usage: Usage


class TextProvider(Protocol):
    name: str
    model: str
    is_mock: bool

    async def complete_json(self, system: str, user: str, schema: dict) -> TextResult: ...


class ImageProvider(Protocol):
    name: str
    model: str
    is_mock: bool

    async def generate(self, prompt: str) -> ImageResult: ...


# ---------------- STT ----------------
class SttSessionError(RuntimeError):
    """STT 연결 단계 실패. 메시지는 사용자에게 보여도 되는 내용만 담는다(키·URL 미포함).

    stage:
      config          : 시도 전 (키 없음)
      connect_failed  : 서버 응답 없음 (네트워크·핸드셰이크 시간 초과)
      http_rejected   : 서버가 WebSocket 핸드셰이크를 HTTP 오류로 거부 (인증·권한 등)
      closed_before_ack / ack_timeout : 연결은 됐지만 설정 승인을 받지 못함
      rejected        : 서버가 설정을 오류로 거부
      mismatch        : 승인된 실제 설정이 요청과 다름
      unverifiable    : 승인 응답에 확인할 필수 항목이 없음
    """

    def __init__(self, message: str, stage: str = "unknown", http_status: Optional[int] = None):
        super().__init__(message)
        self.stage = stage
        self.http_status = http_status

    @property
    def server_responded(self) -> Optional[bool]:
        if self.stage == "config":
            return None
        return self.stage != "connect_failed"


@dataclass
class SttEvent:
    type: str  # partial | final | committed | status | error | notice
    segment_id: Optional[str] = None
    text: Optional[str] = None
    message: Optional[str] = None
    state: Optional[str] = None  # connecting | ready | reconnecting | stopped | error
    retryable: bool = False
    local_segment: Optional[str] = None  # 서버 VAD 구간 ID (발화 종료 추정 시각과 연결)


SttCallback = Callable[[SttEvent], Awaitable[None]]


class SttProvider(Protocol):
    name: str
    model: str
    is_mock: bool
    # True: 한 연결 안에서 확정 결과가 commit 순서대로 온다고 보장되는 제공자 → 상위의 순서 보정 대기열을 쓰지 않음
    ordered_finals: bool

    async def start(self, on_event: SttCallback) -> None: ...

    async def send_audio(self, pcm16: bytes) -> None: ...

    async def commit(self, local_segment: str) -> None: ...

    async def close(self) -> None: ...


def usage_dict(u: Usage) -> dict[str, Any]:
    return {
        "provider": u.provider, "model": u.model, "kind": u.kind, "input_tokens": u.input_tokens,
        "output_tokens": u.output_tokens, "image_count": u.image_count, "audio_seconds": u.audio_seconds,
    }
