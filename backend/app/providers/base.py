"""제공자 어댑터 인터페이스. 음성 인식·텍스트 생성·이미지 생성을 각각 분리한다."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional, Protocol


class ProviderError(Exception):
    """code: timeout | rate_limited | refused | no_image | bad_format | invalid_output | auth | network | upstream | config"""

    def __init__(self, code: str, message: str, retryable: bool = False, usage: Optional["Usage"] = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable
        self.usage = usage


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

    async def start(self, on_event: SttCallback) -> None: ...

    async def send_audio(self, pcm16: bytes) -> None: ...

    async def commit(self, local_segment: str) -> None: ...

    async def close(self) -> None: ...


def usage_dict(u: Usage) -> dict[str, Any]:
    return {
        "provider": u.provider, "model": u.model, "kind": u.kind, "input_tokens": u.input_tokens,
        "output_tokens": u.output_tokens, "image_count": u.image_count, "audio_seconds": u.audio_seconds,
    }
