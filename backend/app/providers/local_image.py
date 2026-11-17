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
import re
import threading
import time
from typing import Any, Awaitable, Callable, Optional

from .base import ImageResult, ProviderError, Usage
from .image_validation import validate_image

# default_cfg: 모델 권장값. sd-turbo 는 적대적 확산 증류(ADD) 모델이라 CFG 없이(guidance 0) 1~4 스텝으로 생성한다.
MODELS: dict[str, dict[str, Any]] = {
    "sd-turbo": {"repo": "stabilityai/sd-turbo", "variant": "fp16", "default_steps": 2, "default_cfg": 0.0},
    # attention_slicing: M5 16GB 실측(2026-11-17)에서 sd15 는 25스텝 CFG 기준 30.5s → 12.1s 로 빨라졌고,
    # sd-turbo 는 오히려 느려져(1스텝 0.5s → 2.2s) 끈다. 메모리 압박(스왑) 상황에 따라 달라질 수 있다.
    # default_scheduler ddim: 기본 PNDM 은 step 이 예측된 깨끗한 잠재(x̂0)를 돌려주지 않아 미리보기에 잡음(x_t)만 보인다.
    # DDIM 은 x̂0 를 돌려주고, X1·X2 실험도 DDIM 기준이다.
    "sd15": {"repo": "stable-diffusion-v1-5/stable-diffusion-v1-5", "variant": "fp16", "default_steps": 25,
             "default_cfg": 7.5, "attention_slicing": True, "default_scheduler": "ddim"},
}

SD_STYLE = ("flat vector educational illustration, simple rounded shapes, navy teal yellow coral palette, "
            "off-white background, clean minimal composition")
# SD 1.x/2.x VAE 잠재(4채널, scaling_factor 적용 공간) → RGB 선형 근사. 커뮤니티 미리보기 도구(ComfyUI 등)에서
# 널리 쓰는 계수다. VAE 디코더를 매 스텝 돌리는 대신 이 근사로 작은 미리보기만 만든다(정확한 색이 아님).
LATENT_RGB_FACTORS = [
    [0.3512, 0.2297, 0.3227],
    [0.3250, 0.4974, 0.2350],
    [-0.2829, 0.1762, 0.2721],
    [-0.2120, -0.2616, -0.7177],
]
PREVIEW_MIN_INTERVAL_S = 0.12

SD_NEGATIVE = ("text, letters, words, numbers, writing, caption, label, watermark, logo, signature, "
               "photorealistic, photo, cluttered, blurry, deformed")


def extract_scene(prompt: str) -> str:
    """planner.compose_image_prompt 결과에서 장면 부분만 꺼낸다. 형식이 다르면 원문 그대로."""
    marker = "Scene:"
    if marker in prompt:
        rest = prompt.split(marker, 1)[1]
        return rest.split("\n\n", 1)[0].strip()
    return prompt.strip()


def compose_sd_prompt(prompt: str, count_tokens: Optional[Callable[[str], int]] = None, max_tokens: int = 77) -> str:
    """장면 + 짧은 화풍. count_tokens(토크나이저 기준, 시작·끝 토큰 포함)를 주면 max_tokens 안에 맞춘다.

    기획 LLM 의 장면 묘사는 보통 80~110 토큰이라 그대로 두면 뒷부분(화풍 문구 포함)이 잘린다.
    화풍은 항상 남기고, 장면은 뒤 문장부터 빼고, 한 문장도 길면 뒤 단어부터 뺀다.
    """
    scene = extract_scene(prompt).rstrip(". ")

    def build(sc: str) -> str:
        return f"{sc}. {SD_STYLE}"

    if count_tokens is None or count_tokens(build(scene)) <= max_tokens:
        return build(scene)
    sentences = [x.strip() for x in re.split(r"(?<=[.!?])\s+", scene) if x.strip()]
    while len(sentences) > 1 and count_tokens(build(" ".join(sentences).rstrip(". "))) > max_tokens:
        sentences.pop()
    words = " ".join(sentences).rstrip(". ").split()
    while len(words) > 3 and count_tokens(build(" ".join(words).rstrip(",;: "))) > max_tokens:
        words.pop()
    return build(" ".join(words).rstrip(",;: "))


def tokenizer_counter(tokenizer) -> Callable[[str], int]:
    return lambda text: len(tokenizer(text).input_ids)


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


def latent_preview_jpeg(latent, scale: int = 4, quality: int = 70) -> bytes:
    """잠재 텐서(1,4,h,w 또는 4,h,w) → 근사 RGB JPEG. h·w 는 이미지의 1/8 이라 scale 배 키운다."""
    import torch
    from PIL import Image

    lat = latent[0] if latent.dim() == 4 else latent
    f = torch.tensor(LATENT_RGB_FACTORS, dtype=torch.float32)
    rgb = torch.einsum("chw,cr->hwr", lat.detach().float().cpu(), f)
    rgb = ((rgb + 1) / 2).clamp(0, 1).mul(255).byte().numpy()
    im = Image.fromarray(rgb, "RGB")
    im = im.resize((im.width * scale, im.height * scale), Image.BILINEAR)
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


class LocalDiffusionImageProvider:
    name = "local"
    is_mock = False
    supports_preview = True

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
        self.scheduler = scheduler or spec.get("default_scheduler")
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

    def _run(self, prompt: str, seed: int, preview: Optional[Callable[[int, int, bytes], None]] = None
             ) -> tuple[bytes, float, str]:
        import torch

        self._ensure_loaded()
        tok = getattr(self._pipe, "tokenizer", None)
        sd_prompt = compose_sd_prompt(prompt, tokenizer_counter(tok) if tok is not None else None)
        g = torch.Generator("cpu").manual_seed(seed)
        kwargs: dict[str, Any] = dict(num_inference_steps=self.steps, guidance_scale=self.cfg,
                                      width=self.width, height=self.height, generator=g)
        if self.cfg > 1.0:
            kwargs["negative_prompt"] = SD_NEGATIVE
        restore = None
        if preview is not None and self.steps > 1:
            sched = self._pipe.scheduler
            # 매 스텝 스케줄러가 계산하는 '예측된 깨끗한 잠재(x̂0)'를 가로채 미리보기로 보낸다(마지막 스텝 제외).
            captured: dict[str, Any] = {}
            orig_step = sched.step
            last = {"t": 0.0}

            def step_wrap(*a, **k):
                out = orig_step(*a, **k)
                if isinstance(out, tuple) and len(out) > 1:
                    captured["x0"] = out[1]
                elif getattr(out, "pred_original_sample", None) is not None:
                    captured["x0"] = out.pred_original_sample
                return out

            def on_step_end(pipe, i, t, cb_kwargs):
                now = time.perf_counter()
                if i < self.steps - 1 and now - last["t"] >= PREVIEW_MIN_INTERVAL_S:
                    last["t"] = now
                    try:
                        preview(i + 1, self.steps, latent_preview_jpeg(captured.get("x0", cb_kwargs["latents"])))
                    except Exception:  # noqa: BLE001  (미리보기는 실패해도 생성은 계속)
                        pass
                return cb_kwargs

            sched.step = step_wrap
            restore = lambda: delattr(sched, "step")  # noqa: E731  (인스턴스 속성 제거 → 클래스 메서드로 복귀)
            kwargs["callback_on_step_end"] = on_step_end
        sync(self._device)
        t = time.perf_counter()
        try:
            img = self._pipe(sd_prompt, **kwargs).images[0]
        finally:
            if restore:
                restore()
        sync(self._device)
        dt = time.perf_counter() - t
        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="JPEG", quality=90)
        return buf.getvalue(), dt, sd_prompt

    async def generate(self, prompt: str,
                       on_preview: Optional[Callable[[int, int, bytes], Awaitable[None]]] = None) -> ImageResult:
        """on_preview(step, total, jpeg): 디노이징 중간 미리보기. 이벤트 루프에서 호출된다."""
        seed = self.seed if self.seed is not None else int.from_bytes(__import__("os").urandom(4), "little")
        settings = {"steps": self.steps, "cfg": self.cfg, "size": f"{self.width}x{self.height}",
                    "scheduler": self.scheduler or "default", "seed": seed}
        usage = Usage(provider=self.name, model=self.model, kind="image", image_count=1, settings=settings)
        async with self._run_lock:
            try:
                preview = None
                if on_preview is not None:
                    loop = asyncio.get_running_loop()

                    def preview(step: int, total: int, jpg: bytes) -> None:  # 추론 스레드에서 호출됨
                        loop.call_soon_threadsafe(lambda: asyncio.ensure_future(on_preview(step, total, jpg)))
                data, dt, sd_prompt = await asyncio.to_thread(self._run, prompt, seed, preview)
            except ImportError as e:
                raise ProviderError("config", "로컬 이미지 생성 패키지가 없습니다 "
                                              "(backend/requirements-local-image.txt 설치)", usage=usage) from e
            except Exception as e:  # noqa: BLE001  (모델 로드·추론 오류: 메모리 부족 등)
                raise ProviderError("upstream", f"로컬 이미지 생성 실패: {type(e).__name__}: {str(e)[:160]}",
                                    retryable=True, usage=usage) from e
        settings["sd_prompt"] = sd_prompt
        usage.detail = {"inference_s": round(dt, 3), "load_s": round(self.load_seconds or 0, 2),
                        "device": self._device}
        try:
            mime, w, h = validate_image(data, self.max_bytes, self.expected_size)
        except ProviderError as e:
            e.usage = usage
            raise
        return ImageResult(data=data, mime=mime, width=w, height=h, prompt=prompt, usage=usage)
