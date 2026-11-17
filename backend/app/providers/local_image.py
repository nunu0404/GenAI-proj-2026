"""로컬 확산 모델(Stable Diffusion 계열) 이미지 생성 어댑터. API 호출 없음, 비용 0.

선택 설치: backend/requirements-local-image.txt (torch, diffusers, transformers, accelerate).
가중치는 처음 사용할 때 Hugging Face 에서 내려받는다.

설계 메모
- SD 1.x/Turbo 의 CLIP 텍스트 인코더는 77 토큰까지만 읽는다(넘는 부분은 잘림). 기획 단계의 긴 프롬프트
  (화풍 + 장면 + 글자 금지 문구, 약 120 토큰)를 그대로 넣으면 장면 묘사가 잘리므로, 장면을 앞에 두고 화풍을
  짧게 붙인 별도 프롬프트를 만들고 '글자 금지'는 negative prompt 로 보낸다.
- negative prompt 는 CFG 에서 빈 프롬프트(조건 없는 예측) 자리를 대신한다. 따라서 CFG 를 쓰지 않는
  증류 모델(sd-turbo, guidance 0)에서는 효과가 없다.
- 한 장치에서 동시에 여러 장을 만들지 않도록 잠금으로 직렬화하고, 추론은 스레드에서 돌려 이벤트 루프를 막지 않는다.
"""
from __future__ import annotations

import asyncio
import io
import threading
import time
from typing import Any, Callable, Optional

from .base import ImageResult, ProviderError, Usage
from .image_validation import validate_image

# default_cfg: 모델 권장값. sd-turbo 는 적대적 확산 증류(ADD) 모델이라 CFG 없이(guidance 0) 1~4 스텝으로 생성한다.
MODELS: dict[str, dict[str, Any]] = {
    "sd-turbo": {"repo": "stabilityai/sd-turbo", "variant": "fp16", "default_steps": 2, "default_cfg": 0.0},
    # attention_slicing: M5 16GB 실측(2026-11-17)에서 sd15 는 25스텝 CFG 기준 30.5s → 12.1s 로 빨라졌고,
    # sd-turbo 는 오히려 느려져(1스텝 0.5s → 2.2s) 끈다. 메모리 압박(스왑) 상황에 따라 달라질 수 있다.
    "sd15": {"repo": "stable-diffusion-v1-5/stable-diffusion-v1-5", "variant": "fp16", "default_steps": 25,
             "default_cfg": 7.5, "attention_slicing": True},
}

SD_STYLE = ("flat vector educational illustration, simple rounded shapes, navy teal yellow coral palette, "
            "off-white background, clean minimal composition")
SD_NEGATIVE = ("text, letters, words, numbers, writing, caption, label, watermark, logo, signature, "
               "photorealistic, photo, cluttered, blurry, deformed")


def extract_scene(prompt: str) -> str:
    """planner.compose_image_prompt 결과에서 장면 부분만 꺼낸다. 형식이 다르면 원문 그대로."""
    marker = "Scene:"
    if marker in prompt:
        rest = prompt.split(marker, 1)[1]
        return rest.split("\n\n", 1)[0].strip()
    return prompt.strip()


def compose_sd_prompt(prompt: str) -> str:
    scene = extract_scene(prompt).rstrip(". ")
    return f"{scene}. {SD_STYLE}"


def pick_device() -> str:
    import torch

    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def sync(device: str) -> None:
    import torch

    if device == "mps":
        torch.mps.synchronize()
    elif device == "cuda":
        torch.cuda.synchronize()


def load_pipeline(name: str, scheduler: Optional[str] = None):
    """(pipe, device). scheduler: None(모델 기본) | ddim | ddpm | euler"""
    import torch
    from diffusers import AutoPipelineForText2Image, DDIMScheduler, DDPMScheduler, EulerDiscreteScheduler

    spec = MODELS[name]
    device = pick_device()
    dtype = torch.float16 if device != "cpu" else torch.float32
    pipe = AutoPipelineForText2Image.from_pretrained(spec["repo"], dtype=dtype, variant=spec["variant"],
                                                     safety_checker=None, requires_safety_checker=False)
    if scheduler:
        cls = {"ddim": DDIMScheduler, "ddpm": DDPMScheduler, "euler": EulerDiscreteScheduler}[scheduler]
        pipe.scheduler = cls.from_config(pipe.scheduler.config)
    pipe = pipe.to(device)
    if spec.get("attention_slicing") and device == "mps":
        pipe.enable_attention_slicing()
    pipe.set_progress_bar_config(disable=True)
    return pipe, device


class LocalDiffusionImageProvider:
    name = "local"
    is_mock = False

    def __init__(self, model: str = "sd-turbo", steps: Optional[int] = None, cfg: Optional[float] = None,
                 gen_size: str = "768x432", expected_size: str = "1536x864", scheduler: Optional[str] = None,
                 seed: Optional[int] = None, max_bytes: int = 20 * 1024 * 1024,
                 loader: Callable[..., Any] = load_pipeline):
        if model not in MODELS:
            raise ValueError(f"LOCAL_IMAGE_MODEL 은 {sorted(MODELS)} 중 하나여야 합니다: {model}")
        spec = MODELS[model]
        self.key = model
        self.model = spec["repo"]
        self.steps = steps or spec["default_steps"]
        self.cfg = spec["default_cfg"] if cfg is None else cfg
        self.width, self.height = (int(x) for x in gen_size.split("x"))
        if self.width % 8 or self.height % 8:
            raise ValueError("LOCAL_IMAGE_SIZE 의 두 변은 8의 배수여야 합니다 (잠재 공간이 1/8 크기)")
        self.expected_size = expected_size
        self.scheduler = scheduler
        self.seed = seed
        self.max_bytes = max_bytes
        self._loader = loader
        self._pipe = None
        self._device = "cpu"
        self._load_lock = threading.Lock()
        self._run_lock = asyncio.Lock()
        self.load_seconds: Optional[float] = None

    def _ensure_loaded(self) -> None:
        with self._load_lock:
            if self._pipe is None:
                t = time.perf_counter()
                self._pipe, self._device = self._loader(self.key, self.scheduler)
                self.load_seconds = time.perf_counter() - t

    async def warmup(self) -> None:
        """서버 시작 시 미리 로드(첫 요청 지연 방지). 실패해도 첫 생성 때 다시 시도한다."""
        await asyncio.to_thread(self._ensure_loaded)

    def _run(self, sd_prompt: str, seed: int) -> tuple[bytes, float]:
        import torch

        self._ensure_loaded()
        g = torch.Generator("cpu").manual_seed(seed)
        kwargs: dict[str, Any] = dict(num_inference_steps=self.steps, guidance_scale=self.cfg,
                                      width=self.width, height=self.height, generator=g)
        if self.cfg > 1.0:
            kwargs["negative_prompt"] = SD_NEGATIVE
        sync(self._device)
        t = time.perf_counter()
        img = self._pipe(sd_prompt, **kwargs).images[0]
        sync(self._device)
        dt = time.perf_counter() - t
        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="JPEG", quality=90)
        return buf.getvalue(), dt

    async def generate(self, prompt: str) -> ImageResult:
        sd_prompt = compose_sd_prompt(prompt)
        seed = self.seed if self.seed is not None else int.from_bytes(__import__("os").urandom(4), "little")
        settings = {"steps": self.steps, "cfg": self.cfg, "size": f"{self.width}x{self.height}",
                    "scheduler": self.scheduler or "default", "seed": seed, "sd_prompt": sd_prompt}
        usage = Usage(provider=self.name, model=self.model, kind="image", image_count=1, settings=settings)
        async with self._run_lock:
            try:
                data, dt = await asyncio.to_thread(self._run, sd_prompt, seed)
            except ImportError as e:
                raise ProviderError("config", "로컬 이미지 생성 패키지가 없습니다 "
                                              "(backend/requirements-local-image.txt 설치)", usage=usage) from e
            except Exception as e:  # noqa: BLE001  (모델 로드·추론 오류: 메모리 부족 등)
                raise ProviderError("upstream", f"로컬 이미지 생성 실패: {type(e).__name__}: {str(e)[:160]}",
                                    retryable=True, usage=usage) from e
        usage.detail = {"inference_s": round(dt, 3), "load_s": round(self.load_seconds or 0, 2),
                        "device": self._device}
        try:
            mime, w, h = validate_image(data, self.max_bytes, self.expected_size)
        except ProviderError as e:
            e.usage = usage
            raise
        return ImageResult(data=data, mime=mime, width=w, height=h, prompt=prompt, usage=usage)
