"""환경변수 기반 설정. API 키는 여기서 '존재 여부'만 확인하고 값은 절대 로그/응답에 노출하지 않는다."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")


def _env(name: str, default: str) -> str:
    v = os.environ.get(name)
    return default if v is None or v.strip() == "" else v.strip()


def _float_or_none(name: str) -> Optional[float]:
    v = os.environ.get(name, "").strip()
    if not v:
        return None
    try:
        return float(v)
    except ValueError:
        return None


@dataclass
class Settings:
    # --- 제공자 선택 (mock | 실제) ---
    stt_provider: str = field(default_factory=lambda: _env("STT_PROVIDER", "mock"))  # openai | mock
    text_provider: str = field(default_factory=lambda: _env("TEXT_PROVIDER", "mock"))  # anthropic | mock
    image_provider: str = field(default_factory=lambda: _env("IMAGE_PROVIDER", "mock"))  # openai | mock

    # --- STT (OpenAI Realtime transcription) ---
    openai_stt_model: str = field(default_factory=lambda: _env("OPENAI_STT_MODEL", "gpt-live-transcribe"))
    stt_languages: str = field(default_factory=lambda: _env("STT_LANGUAGES", "ko"))
    stt_delay: str = field(default_factory=lambda: _env("STT_DELAY", "low"))
    stt_sample_rate: int = 24000  # OpenAI 문서: audio/pcm 24kHz mono PCM16. 변경 불가 상수로 둔다.
    stt_max_reconnects: int = field(default_factory=lambda: int(_env("STT_MAX_RECONNECTS", "3")))
    vad_rms_threshold: float = field(default_factory=lambda: float(_env("VAD_RMS_THRESHOLD", "450")))
    vad_silence_ms: int = field(default_factory=lambda: int(_env("VAD_SILENCE_MS", "700")))
    vad_min_speech_ms: int = field(default_factory=lambda: int(_env("VAD_MIN_SPEECH_MS", "250")))
    vad_max_segment_ms: int = field(default_factory=lambda: int(_env("VAD_MAX_SEGMENT_MS", "12000")))
    vad_preroll_ms: int = field(default_factory=lambda: int(_env("VAD_PREROLL_MS", "300")))

    # --- 텍스트(슬라이드 기획) ---
    anthropic_text_model: str = field(default_factory=lambda: _env("ANTHROPIC_TEXT_MODEL", "claude-opus-5-5"))
    text_effort: str = field(default_factory=lambda: _env("TEXT_EFFORT", "low"))
    text_timeout_s: float = field(default_factory=lambda: float(_env("TEXT_TIMEOUT_S", "60")))
    text_max_repair: int = field(default_factory=lambda: int(_env("TEXT_MAX_REPAIR", "1")))
    text_use_fallbacks: bool = field(default_factory=lambda: _env("TEXT_USE_FALLBACKS", "true").lower() == "true")

    # --- 이미지 ---
    openai_image_model: str = field(default_factory=lambda: _env("OPENAI_IMAGE_MODEL", "gpt-image-2"))
    image_size: str = field(default_factory=lambda: _env("IMAGE_SIZE", "1536x864"))
    image_quality: str = field(default_factory=lambda: _env("IMAGE_QUALITY", "medium"))
    image_format: str = field(default_factory=lambda: _env("IMAGE_FORMAT", "jpeg"))
    image_timeout_s: float = field(default_factory=lambda: float(_env("IMAGE_TIMEOUT_S", "150")))
    image_max_retries: int = field(default_factory=lambda: int(_env("IMAGE_MAX_RETRIES", "1")))
    image_max_bytes: int = 20 * 1024 * 1024

    # --- 요청 감지 / 맥락 ---
    request_silence_ms: int = field(default_factory=lambda: int(_env("REQUEST_SILENCE_MS", "2500")))
    context_window_s: float = field(default_factory=lambda: float(_env("CONTEXT_WINDOW_S", "90")))
    context_max_chars: int = field(default_factory=lambda: int(_env("CONTEXT_MAX_CHARS", "1500")))
    max_queue: int = field(default_factory=lambda: int(_env("MAX_QUEUE", "3")))

    # --- mock 지연(시연용) ---
    mock_text_delay_ms: int = field(default_factory=lambda: int(_env("MOCK_TEXT_DELAY_MS", "900")))
    mock_image_delay_ms: int = field(default_factory=lambda: int(_env("MOCK_IMAGE_DELAY_MS", "2500")))

    # --- 단가(확인 가능한 값만, 미설정 시 비용 추정하지 않음). 단위: USD ---
    price_text_in_per_mtok: Optional[float] = field(default_factory=lambda: _float_or_none("PRICE_TEXT_INPUT_PER_MTOK"))
    price_text_out_per_mtok: Optional[float] = field(default_factory=lambda: _float_or_none("PRICE_TEXT_OUTPUT_PER_MTOK"))
    price_image_text_in_per_mtok: Optional[float] = field(default_factory=lambda: _float_or_none("PRICE_IMAGE_TEXT_INPUT_PER_MTOK"))
    price_image_out_per_mtok: Optional[float] = field(default_factory=lambda: _float_or_none("PRICE_IMAGE_OUTPUT_PER_MTOK"))
    price_stt_per_min: Optional[float] = field(default_factory=lambda: _float_or_none("PRICE_STT_PER_MIN"))

    data_dir: Path = field(default_factory=lambda: Path(_env("DATA_DIR", str(BACKEND_DIR / "data"))))

    @property
    def db_path(self) -> Path:
        return self.data_dir / "nextslide.sqlite3"

    @property
    def image_dir(self) -> Path:
        return self.data_dir / "images"

    def public_info(self) -> dict:
        """브라우저에 보낼 수 있는 정보(키 제외)."""
        return {
            "stt": {"provider": self.stt_provider, "model": self.openai_stt_model if self.stt_provider == "openai" else "mock",
                    "sample_rate": self.stt_sample_rate, "encoding": "pcm_s16le", "channels": 1},
            "text": {"provider": self.text_provider, "model": self.anthropic_text_model if self.text_provider == "anthropic" else "mock"},
            "image": {"provider": self.image_provider, "model": self.openai_image_model if self.image_provider == "openai" else "mock",
                      "size": self.image_size},
            "mock": {
                "stt": self.stt_provider == "mock",
                "text": self.text_provider == "mock",
                "image": self.image_provider == "mock",
            },
            "request_silence_ms": self.request_silence_ms,
            "max_queue": self.max_queue,
        }

    def credential_problems(self) -> list[str]:
        probs = []
        if self.text_provider == "anthropic" and not os.environ.get("ANTHROPIC_API_KEY"):
            probs.append("TEXT_PROVIDER=anthropic 이지만 ANTHROPIC_API_KEY 가 없습니다.")
        if self.image_provider == "openai" and not os.environ.get("OPENAI_API_KEY"):
            probs.append("IMAGE_PROVIDER=openai 이지만 OPENAI_API_KEY 가 없습니다.")
        if self.stt_provider == "openai" and not os.environ.get("OPENAI_API_KEY"):
            probs.append("STT_PROVIDER=openai 이지만 OPENAI_API_KEY 가 없습니다.")
        return probs


settings = Settings()
