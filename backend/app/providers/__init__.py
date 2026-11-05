from __future__ import annotations

from ..config import Settings
from .base import ImageProvider, SttProvider, TextProvider
from .mock import MockImageProvider, MockSttProvider, MockTextProvider


def _csv(v: str) -> list[str]:
    return [x.strip() for x in v.split(",") if x.strip()]


def make_text_provider(s: Settings) -> TextProvider:
    if s.text_provider == "openai":
        from .openai_text import OpenAITextProvider
        return OpenAITextProvider(s.openai_text_model, s.openai_text_reasoning, s.text_timeout_s, s.text_max_tokens)
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
    if s.stt_provider == "gemini":
        from .gemini_stt import GeminiSttProvider
        return GeminiSttProvider(s.gemini_stt_model, _csv(s.gemini_stt_languages), s.gemini_stt_mode,
                                 _csv(s.gemini_stt_vocabulary), s.stt_sample_rate, s.stt_max_reconnects,
                                 s.stt_session_ack_timeout_s, s.gemini_stt_rotate_s)
    if s.stt_provider == "openai":
        from .openai_stt import OpenAISttProvider
        return OpenAISttProvider(s.openai_stt_model, _csv(s.stt_languages), s.stt_delay, s.stt_sample_rate,
                                 s.stt_max_reconnects, s.stt_session_ack_timeout_s, s.stt_strict_session_check)
    return MockSttProvider(sample_rate=s.stt_sample_rate)
