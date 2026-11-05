"""OpenAI Images API 기반 설명 이미지 생성 어댑터.

확인한 공식 문서 사항 (developers.openai.com, 2026-11-05 확인):
- 엔드포인트 v1/images/generations, 응답 data[0].b64_json (GPT Image 모델은 base64 반환)
- 사용자 지정 크기 WIDTHxHEIGHT: 두 변 16의 배수, 비율 1:3~3:1, 총 픽셀 655,360~8,294,400 → 1536x864(16:9) 사용
- output_format: png | jpeg | webp (jpeg 가 png 보다 빠름)
- 응답 usage(input/output tokens) 제공
"""
from __future__ import annotations

import asyncio
import base64
import binascii

import openai

from .base import ImageResult, ProviderError, Usage
from .image_validation import validate_image


class OpenAIImageProvider:
    name = "openai"
    is_mock = False

    def __init__(self, model: str, size: str, quality: str, output_format: str, timeout_s: float, max_bytes: int):
        self.model = model
        self.size = size
        self.quality = quality
        self.output_format = output_format
        self.timeout_s = timeout_s
        self.max_bytes = max_bytes
        # 재시도는 작업 관리자에서 횟수를 세어 제한적으로 수행한다.
        self._client = openai.AsyncOpenAI(timeout=timeout_s, max_retries=0)

    async def generate(self, prompt: str) -> ImageResult:
        settings = {"size": self.size, "quality": self.quality, "output_format": self.output_format}
        try:
            resp = await asyncio.wait_for(
                self._client.images.generate(
                    model=self.model, prompt=prompt, size=self.size, quality=self.quality,  # type: ignore[arg-type]
                    output_format=self.output_format, n=1,  # type: ignore[arg-type]
                ),
                timeout=self.timeout_s + 5,
            )
        except asyncio.TimeoutError as e:
            raise ProviderError("timeout", "이미지 생성 시간 초과", retryable=True) from e
        except openai.APITimeoutError as e:
            raise ProviderError("timeout", "이미지 생성 시간 초과", retryable=True) from e
        except openai.AuthenticationError as e:
            raise ProviderError("auth", "OpenAI 인증 실패 (OPENAI_API_KEY 확인)", http_status=e.status_code) from e
        except openai.RateLimitError as e:
            raise ProviderError("rate_limited", "OpenAI 요청 한도 초과", retryable=True, http_status=e.status_code) from e
        except openai.BadRequestError as e:
            code = getattr(e, "code", None) or ""
            if "moderation" in str(code) or "safety" in str(e).lower():
                raise ProviderError("refused", "이미지 생성이 안전 정책으로 거절되었습니다", http_status=e.status_code) from e
            raise ProviderError("upstream", f"OpenAI 이미지 요청 오류: {str(e)[:200]}", http_status=e.status_code) from e
        except openai.APIStatusError as e:
            raise ProviderError("upstream", f"OpenAI 서버 오류 {e.status_code}", retryable=e.status_code >= 500,
                                http_status=e.status_code) from e
        except openai.APIConnectionError as e:
            raise ProviderError("network", "OpenAI 연결 실패", retryable=True) from e

        u = getattr(resp, "usage", None)
        usage = Usage(
            provider=self.name, model=self.model, kind="image", image_count=1, settings=settings,
            input_tokens=getattr(u, "input_tokens", None), output_tokens=getattr(u, "output_tokens", None),
            detail={"input_tokens_details": _dump(getattr(u, "input_tokens_details", None))},
        )
        if not resp.data:
            raise ProviderError("no_image", "응답에 이미지가 없습니다", usage=usage, http_status=200)
        b64 = getattr(resp.data[0], "b64_json", None)
        if not b64:
            raise ProviderError("no_image", "응답에 b64_json 이미지 데이터가 없습니다", usage=usage, http_status=200)
        try:
            data = base64.b64decode(b64, validate=True)
        except (binascii.Error, ValueError) as e:
            raise ProviderError("bad_format", "base64 디코딩 실패", usage=usage, http_status=200) from e
        try:
            mime, w, h = validate_image(data, self.max_bytes, self.size)
        except ProviderError as e:
            e.usage = usage
            e.http_status = 200  # 응답은 정상(200)이었지만 이미지가 유효하지 않음
            raise
        return ImageResult(data=data, mime=mime, width=w, height=h, prompt=prompt, usage=usage)


def _dump(obj):
    if obj is None:
        return None
    try:
        return obj.model_dump()
    except Exception:  # noqa: BLE001
        return None
