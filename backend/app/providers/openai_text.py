"""OpenAI Responses API 기반 슬라이드 기획 어댑터.

- 모델 ID: OPENAI_TEXT_MODEL (임시 기본 gpt-6-luna — 모델 페이지: "focused, high-volume tasks" 용,
  $0.10/$0.50 per 1M tokens, 구조화 출력·reasoning effort none~max 지원, v1/responses 지원; 2026-11-05 확인)
- text.format = json_schema (strict) 로 구조화 출력을 요청하고, reasoning.effort 로 지연·비용을 조절한다(기본 none).
- store=False: 응답을 OpenAI 쪽에 저장하지 않는다.
- API 키는 SDK 가 서버 환경변수 OPENAI_API_KEY 에서 읽는다.
"""
from __future__ import annotations

import asyncio

import openai

from .base import ProviderError, TextResult, Usage


class OpenAITextProvider:
    name = "openai"
    is_mock = False

    def __init__(self, model: str, reasoning: str = "none", timeout_s: float = 60.0, max_tokens: int = 4000):
        self.model = model
        self.reasoning = reasoning
        self.timeout_s = timeout_s
        self.max_tokens = max_tokens
        self._client = openai.AsyncOpenAI(timeout=timeout_s, max_retries=1)

    async def complete_json(self, system: str, user: str, schema: dict) -> TextResult:
        kwargs: dict = dict(
            model=self.model, instructions=system, input=user, max_output_tokens=self.max_tokens, store=False,
            text={"format": {"type": "json_schema", "name": "slide_spec", "schema": schema, "strict": True}},
        )
        if self.reasoning:
            kwargs["reasoning"] = {"effort": self.reasoning}
        settings = {"reasoning_effort": self.reasoning or None, "max_output_tokens": self.max_tokens, "store": False}
        try:
            resp = await asyncio.wait_for(self._client.responses.create(**kwargs), timeout=self.timeout_s + 5)
        except asyncio.TimeoutError as e:
            raise ProviderError("timeout", "텍스트 생성 시간 초과", retryable=True) from e
        except openai.APITimeoutError as e:
            raise ProviderError("timeout", "텍스트 생성 시간 초과", retryable=True) from e
        except openai.AuthenticationError as e:
            raise ProviderError("auth", "OpenAI 인증 실패 (OPENAI_API_KEY 확인)", http_status=e.status_code) from e
        except openai.RateLimitError as e:
            raise ProviderError("rate_limited", "OpenAI 요청 한도 초과", retryable=True, http_status=e.status_code) from e
        except openai.APIStatusError as e:
            raise ProviderError("upstream", f"OpenAI 텍스트 요청 오류 {e.status_code}: {str(e)[:200]}",
                                retryable=e.status_code >= 500, http_status=e.status_code) from e
        except openai.APIConnectionError as e:
            raise ProviderError("network", "OpenAI 연결 실패", retryable=True) from e

        u = getattr(resp, "usage", None)
        usage = Usage(provider=self.name, model=getattr(resp, "model", None) or self.model, kind="text",
                      input_tokens=getattr(u, "input_tokens", None), output_tokens=getattr(u, "output_tokens", None),
                      settings=settings)
        for item in resp.output or []:
            for c in getattr(item, "content", None) or []:
                if getattr(c, "type", None) == "refusal":
                    raise ProviderError("refused", f"모델이 요청을 거절했습니다: {str(getattr(c, 'refusal', ''))[:200]}",
                                        usage=usage, http_status=200)
        if resp.status == "incomplete":
            reason = getattr(getattr(resp, "incomplete_details", None), "reason", None)
            raise ProviderError("invalid_output", f"응답이 완료되지 않았습니다 ({reason})", retryable=True,
                                usage=usage, http_status=200)
        text = resp.output_text
        if not text:
            raise ProviderError("invalid_output", "텍스트 출력이 없습니다", retryable=True, usage=usage, http_status=200)
        return TextResult(raw_text=text, usage=usage)
