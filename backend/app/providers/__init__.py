from __future__ import annotations

from ..config import Settings
from .base import ImageProvider, SttProvider, TextProvider
from .mock import MockImageProvider, MockSttProvider, MockTextProvider


def make_text_provider(s: Settings) -> TextProvider:
    if s.text_provider == "anthropic":
        from .anthropic_text import AnthropicTextProvider
        return AnthropicTextProvider(s.anthropic_text_model, s.text_effort, s.text_timeout_s, s.text_use_fallbacks,
                                     s.text_thinking, s.text_max_tokens)
    return MockTextProvider(delay_ms=s.mock_text_delay_ms)


def make_image_provider(s: Settings) -> ImageProvider:
    if s.image_provider == "openai":
        from .openai_image import OpenAIImageProvider
        return OpenAIImageProvider(s.openai_image_model, s.image_size, s.image_quality, s.image_format,
                                   s.image_timeout_s, s.image_max_bytes)
    return MockImageProvider(delay_ms=s.mock_image_delay_ms, size=s.image_size)


def make_stt_provider(s: Settings) -> SttProvider:
    if s.stt_provider == "openai":
        from .openai_stt import OpenAISttProvider
        langs = [x.strip() for x in s.stt_languages.split(",") if x.strip()]
        return OpenAISttProvider(s.openai_stt_model, langs, s.stt_delay, s.stt_sample_rate, s.stt_max_reconnects,
                                 s.stt_session_ack_timeout_s, s.stt_strict_session_check)
    return MockSttProvider(sample_rate=s.stt_sample_rate)
