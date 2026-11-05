"""Claude(Anthropic Messages API) 기반 슬라이드 기획 어댑터.

- 모델 ID 는 환경변수 ANTHROPIC_TEXT_MODEL (기본 claude-opus-5-5).
- output_config.format(json_schema) 로 구조화 출력을 요청한다.
- 거절(refusal) 시 서버 측 fallbacks: "default" (beta server-side-fallback-2026-07-01) 를 사용한다.
- API 키는 SDK 가 서버 환경변수 ANTHROPIC_API_KEY 에서 읽는다. 이 코드에서 키를 다루지 않는다.
"""
from __future__ import annotations

import asyncio

import anthropic

from .base import ProviderError, TextResult, Usage


class AnthropicTextProvider:
    name = "anthropic"
    is_mock = False

    def __init__(self, model: str, effort: str = "low", timeout_s: float = 60.0, use_fallbacks: bool = True):
        self.model = model
        self.effort = effort
        self.timeout_s = timeout_s
        self.use_fallbacks = use_fallbacks
        # SDK 자체 재시도는 1회로 제한(429/5xx/연결 오류). 무한 재시도 없음.
        self._client = anthropic.AsyncAnthropic(timeout=timeout_s, max_retries=1)

    async def complete_json(self, system: str, user: str, schema: dict) -> TextResult:
        kwargs = dict(
            model=self.model,
            max_tokens=4000,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_config={"effort": self.effort, "format": {"type": "json_schema", "schema": schema}},
        )
        settings = {"effort": self.effort, "fallbacks": "default" if self.use_fallbacks else None}
        try:
            if self.use_fallbacks:
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
            raise ProviderError("auth", "Anthropic 인증 실패 (ANTHROPIC_API_KEY 확인)") from e
        except anthropic.RateLimitError as e:
            raise ProviderError("rate_limited", "Anthropic 요청 한도 초과", retryable=True) from e
        except anthropic.BadRequestError as e:
            raise ProviderError("upstream", f"Anthropic 요청 오류: {getattr(e, 'message', str(e))[:200]}") from e
        except anthropic.APIStatusError as e:
            raise ProviderError("upstream", f"Anthropic 서버 오류 {e.status_code}", retryable=e.status_code >= 500) from e
        except anthropic.APIConnectionError as e:
            raise ProviderError("network", "Anthropic 연결 실패", retryable=True) from e

        u = resp.usage
        usage = Usage(provider=self.name, model=getattr(resp, "model", self.model) or self.model, kind="text",
                      input_tokens=getattr(u, "input_tokens", None), output_tokens=getattr(u, "output_tokens", None),
                      settings=settings)
        if resp.stop_reason == "refusal":
            cat = getattr(getattr(resp, "stop_details", None), "category", None)
            raise ProviderError("refused", f"모델이 요청을 거절했습니다 (category={cat})", usage=usage)
        if resp.stop_reason == "max_tokens":
            raise ProviderError("invalid_output", "출력이 max_tokens 에서 잘렸습니다", retryable=True, usage=usage)
        text = next((b.text for b in resp.content if getattr(b, "type", None) == "text"), None)
        if not text:
            raise ProviderError("invalid_output", "텍스트 블록이 없습니다", retryable=True, usage=usage)
        return TextResult(raw_text=text, usage=usage)

