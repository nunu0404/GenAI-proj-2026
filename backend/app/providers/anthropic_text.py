"""Claude(Anthropic Messages API) 기반 슬라이드 기획 어댑터.

- 모델 ID 는 환경변수 ANTHROPIC_TEXT_MODEL (임시 기본 claude-haiku-5-5 — 실측 후 확정).
- output_config.format(json_schema) 로 구조화 출력을 요청하고, effort 로 지연·비용을 조절한다.
- 모델별로 허용되는 옵션만 보낸다 (Anthropic 문서/SDK 가이드 기준):
  · 서버 측 refusal fallback(fallbacks: "default", beta server-side-fallback-2026-07-01)은
    Fable 5.1 / Opus 5.5 / Opus 5 / Sonnet 5.5 에서만. Haiku 5.5 는 서버 측 fallback 없음.
  · thinking: {"type": "disabled"} 는 Haiku 5.5·Opus 5 에서 effort low/medium/high 일 때만 허용
    (Opus 5.5 / Sonnet 5.5 / Fable 은 400). 기본은 thinking 을 보내지 않고 effort=low 로 줄인다.
- API 키는 SDK 가 서버 환경변수 ANTHROPIC_API_KEY 에서 읽는다. 이 코드에서 키를 다루지 않는다.
"""
from __future__ import annotations

import asyncio
import logging

import anthropic

from .base import ProviderError, TextResult, Usage

log = logging.getLogger("nextslide.text")
FALLBACK_MODELS = {"claude-fable-5-1", "claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5"}
THINKING_DISABLE_OK = {"claude-haiku-5-5", "claude-opus-5"}


def request_options(model: str, effort: str, thinking: str, use_fallbacks: bool) -> dict:
    """모델이 받아들이는 옵션만 골라 반환한다 (잘못된 조합으로 400 이 나지 않게)."""
    opts: dict = {"fallbacks": use_fallbacks and model in FALLBACK_MODELS, "thinking": None}
    if thinking == "disabled":
        if model in THINKING_DISABLE_OK and effort in ("low", "medium", "high"):
            opts["thinking"] = {"type": "disabled"}
        else:
            log.warning("TEXT_THINKING=disabled 는 %s / effort=%s 에서 허용되지 않아 생략합니다", model, effort)
    elif thinking == "adaptive":
        opts["thinking"] = {"type": "adaptive"}
    return opts


class AnthropicTextProvider:
    name = "anthropic"
    is_mock = False

    def __init__(self, model: str, effort: str = "low", timeout_s: float = 60.0, use_fallbacks: bool = True,
                 thinking: str = "", max_tokens: int = 4000):
        self.model = model
        self.effort = effort
        self.timeout_s = timeout_s
        self.max_tokens = max_tokens
        self.opts = request_options(model, effort, thinking, use_fallbacks)
        # SDK 자체 재시도는 1회로 제한(429/5xx/연결 오류). 무한 재시도 없음.
        self._client = anthropic.AsyncAnthropic(timeout=timeout_s, max_retries=1)

    async def complete_json(self, system: str, user: str, schema: dict) -> TextResult:
        kwargs = dict(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_config={"effort": self.effort, "format": {"type": "json_schema", "schema": schema}},
        )
        if self.opts["thinking"] is not None:
            kwargs["thinking"] = self.opts["thinking"]
        use_fallbacks = self.opts["fallbacks"]
        settings = {"effort": self.effort, "thinking": self.opts["thinking"], "fallbacks": "default" if use_fallbacks else None,
                    "max_tokens": self.max_tokens}
        try:
            if use_fallbacks:
                resp = await asyncio.wait_for(
                    self._client.beta.messages.create(
                        betas=["server-side-fallback-2026-07-01"], fallbacks="default", **kwargs
                    ),
                    timeout=self.timeout_s + 5,
                )
            else:
                resp = await asyncio.wait_for(self._client.messages.create(**kwargs), timeout=self.timeout_s + 5)
        except asyncio.TimeoutError as e:
            raise ProviderError("timeout", "텍스트 생성 시간 초과", retryable=True) from e
        except anthropic.APITimeoutError as e:
            raise ProviderError("timeout", "텍스트 생성 시간 초과", retryable=True) from e
        except anthropic.AuthenticationError as e:
            raise ProviderError("auth", "Anthropic 인증 실패 (ANTHROPIC_API_KEY 확인)", http_status=e.status_code) from e
        except anthropic.RateLimitError as e:
            raise ProviderError("rate_limited", "Anthropic 요청 한도 초과", retryable=True, http_status=e.status_code) from e
        except anthropic.BadRequestError as e:
            raise ProviderError("upstream", f"Anthropic 요청 오류: {getattr(e, 'message', str(e))[:200]}",
                                http_status=e.status_code) from e
        except anthropic.APIStatusError as e:
            raise ProviderError("upstream", f"Anthropic 서버 오류 {e.status_code}", retryable=e.status_code >= 500,
                                http_status=e.status_code) from e
        except anthropic.APIConnectionError as e:
            raise ProviderError("network", "Anthropic 연결 실패", retryable=True) from e

        u = resp.usage
        usage = Usage(provider=self.name, model=getattr(resp, "model", self.model) or self.model, kind="text",
                      input_tokens=getattr(u, "input_tokens", None), output_tokens=getattr(u, "output_tokens", None),
                      settings=settings)
        if resp.stop_reason == "refusal":
            cat = getattr(getattr(resp, "stop_details", None), "category", None)
            raise ProviderError("refused", f"모델이 요청을 거절했습니다 (category={cat})", usage=usage, http_status=200)
        if resp.stop_reason == "max_tokens":
            raise ProviderError("invalid_output", "출력이 max_tokens 에서 잘렸습니다", retryable=True, usage=usage, http_status=200)
        text = next((b.text for b in resp.content if getattr(b, "type", None) == "text"), None)
        if not text:
            raise ProviderError("invalid_output", "텍스트 블록이 없습니다", retryable=True, usage=usage, http_status=200)
        return TextResult(raw_text=text, usage=usage)

