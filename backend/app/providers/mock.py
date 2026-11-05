"""자격증명 없이 동작하는 mock 제공자. 결과는 항상 is_mock=True 로 표시되며 실제 API 검증 결과가 아니다."""
from __future__ import annotations

import asyncio
import hashlib
import io
import json
import random
import re
from typing import Optional

from PIL import Image, ImageDraw

from .base import ImageResult, ProviderError, SttCallback, SttEvent, TextResult, Usage


class MockTextProvider:
    name = "mock"
    model = "mock-planner"
    is_mock = True

    def __init__(self, delay_ms: int = 900, fail_times: int = 0, raw_override: Optional[list[str]] = None):
        self.delay_ms = delay_ms
        self.fail_times = fail_times  # 테스트용: 처음 n 번 실패
        self.raw_override = list(raw_override or [])  # 테스트용: 지정 원문을 순서대로 반환
        self.calls = 0

    async def complete_json(self, system: str, user: str, schema: dict) -> TextResult:
        self.calls += 1
        await asyncio.sleep(self.delay_ms / 1000)
        usage = Usage(provider=self.name, model=self.model, kind="text", input_tokens=None, output_tokens=None)
        if self.fail_times > 0:
            self.fail_times -= 1
            raise ProviderError("upstream", "mock text failure", retryable=False, usage=usage)
        if self.raw_override:
            return TextResult(raw_text=self.raw_override.pop(0), usage=usage)
        req = _section(user, "next_slide_request") or ""
        ctx = _section(user, "recent_lecture_transcript") or ""
        topic = re.sub(r"^(다음\s*(슬라이드|장)(에서는|에는|는)?\s*)", "", req).strip()
        topic = re.sub(r"\s*(설명하겠습니다|보여\s*주세요|설명할게요)\.?$", "", topic).strip() or "요청 주제"
        title = topic[:38]
        bullets = [f"{topic[:40]}의 핵심 아이디어", "비유를 통해 개념을 직관적으로 이해"]
        if ctx.strip() and ctx.strip() != "(없음)":
            first = re.split(r"[.!?]\s*", ctx.strip())[0][:50]
            bullets.append(f"앞선 설명과 연결: {first}"[:68])
        spec = {
            "title": title,
            "bullets": bullets,
            "visual_intent": f"{topic} 을(를) 일상적 상황으로 보여주는 그림",
            "image_prompt": f"An educational illustration explaining: {topic}",
            "speaker_notes": "[MOCK] 모의 생성 결과입니다. 실제 LLM 출력이 아닙니다.",
            "needs_clarification": False,
            "clarification_reason": None,
            "precision_warning": None,
        }
        return TextResult(raw_text=json.dumps(spec, ensure_ascii=False), usage=usage)


def _section(text: str, tag: str) -> Optional[str]:
    m = re.search(rf"<{tag}>\n?(.*?)\n?</{tag}>", text, re.S)
    return m.group(1).strip() if m else None


class MockImageProvider:
    name = "mock"
    model = "mock-image"
    is_mock = True

    def __init__(self, delay_ms: int = 2500, size: str = "1536x864", fail_times: int = 0,
                 gate: Optional[asyncio.Event] = None):
        self.delay_ms = delay_ms
        self.size = size
        self.fail_times = fail_times
        self.gate = gate  # 테스트용: 이 이벤트가 set 될 때까지 대기 (생성 중 상태 재현)
        self.calls = 0

    async def generate(self, prompt: str) -> ImageResult:
        self.calls += 1
        if self.gate is not None:
            await self.gate.wait()
        await asyncio.sleep(self.delay_ms / 1000)
        usage = Usage(provider=self.name, model=self.model, kind="image", image_count=1, settings={"size": self.size})
        if self.fail_times > 0:
            self.fail_times -= 1
            raise ProviderError("upstream", "mock image failure", retryable=False, usage=usage)
        data = render_mock_png(prompt, self.size)
        w, h = (int(x) for x in self.size.split("x"))
        return ImageResult(data=data, mime="image/png", width=w, height=h, prompt=prompt, usage=usage)


def render_mock_png(prompt: str, size: str) -> bytes:
    """글자 없이 도형만 그린 placeholder 일러스트 (결정적)."""
    w, h = (int(x) for x in size.split("x"))
    seed = int(hashlib.sha256(prompt.encode()).hexdigest()[:8], 16)
    rnd = random.Random(seed)
    palette = [(31, 58, 96), (42, 157, 143), (233, 196, 106), (244, 162, 97), (231, 111, 81), (138, 177, 125)]
    img = Image.new("RGB", (w, h), (247, 244, 236))
    d = ImageDraw.Draw(img)
    d.rectangle([0, int(h * 0.78), w, h], fill=(229, 222, 205))
    for _ in range(7):
        c = rnd.choice(palette)
        x, y = rnd.randint(0, w - 200), rnd.randint(0, int(h * 0.7))
        r = rnd.randint(60, 220)
        if rnd.random() < 0.5:
            d.ellipse([x, y, x + r, y + r], fill=c)
        else:
            d.rounded_rectangle([x, y, x + r * 1.4, y + r], radius=28, fill=c)
    # 오른쪽 아래 작은 줄무늬 = mock 표식 (텍스트 대신)
    for i in range(6):
        d.rectangle([w - 120 + i * 18, h - 40, w - 110 + i * 18, h - 20], fill=(180, 60, 60))
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


class MockSttProvider:
    """오디오를 실제로 전사하지 않는다. 서버 VAD 가 구간을 나눈 사실만 알린다(파이프라인 점검용)."""

    name = "mock"
    model = "mock-stt"
    is_mock = True

    def __init__(self, sample_rate: int = 24000):
        self.sample_rate = sample_rate
        self._on: Optional[SttCallback] = None
        self._seg_samples = 0
        self.audio_seconds_sent = 0.0

    async def start(self, on_event: SttCallback) -> None:
        self._on = on_event
        await on_event(SttEvent("status", state="ready",
                                message="모의 STT: 음성 구간만 감지하고 전사하지 않습니다. 텍스트 입력/발화 시뮬레이션을 사용하세요."))

    async def send_audio(self, pcm16: bytes) -> None:
        n = len(pcm16) // 2
        self._seg_samples += n
        self.audio_seconds_sent += n / self.sample_rate

    async def commit(self, local_segment: str) -> None:
        secs = self._seg_samples / self.sample_rate
        self._seg_samples = 0
        if self._on:
            await self._on(SttEvent("notice", local_segment=local_segment,
                                    message=f"[모의 STT] 음성 구간 감지됨 ({secs:.1f}초) — 전사는 STT_PROVIDER=openai 에서만 동작"))
            # 순서 보정 대기열이 막히지 않도록 빈 확정 결과로 구간을 닫는다(자막·감지에는 반영되지 않음)
            await self._on(SttEvent("final", segment_id=f"mock-{local_segment}", text="", local_segment=local_segment))

    async def close(self) -> None:
        if self._on:
            await self._on(SttEvent("status", state="stopped", message="STT 중지"))
