"""로컬 확산 모델 어댑터 테스트. 실제 모델 대신 가짜 파이프라인을 주입한다(torch 필요 없음, 장치는 cpu)."""
import asyncio
import io
import sys
import types

import pytest
from PIL import Image

from app.planner import compose_image_prompt
from app.providers.base import ProviderError
from app.providers.local_image import SD_NEGATIVE, LocalDiffusionImageProvider, compose_sd_prompt, extract_scene


@pytest.fixture(autouse=True)
def fake_torch(monkeypatch):
    """torch 가 설치돼 있지 않아도 돌도록 Generator 만 흉내 낸다."""
    t = types.ModuleType("torch")

    class Gen:
        def __init__(self, dev):
            self.dev = dev

        def manual_seed(self, s):
            self.seed = s
            return self

    t.Generator = Gen
    monkeypatch.setitem(sys.modules, "torch", t)


class FakePipe:
    def __init__(self, size=(768, 432)):
        self.calls = []
        self.size = size

    def __call__(self, prompt, **kw):
        self.calls.append((prompt, kw))
        return types.SimpleNamespace(images=[Image.new("RGB", self.size, (200, 180, 160))])


def make(pipe, **kw):
    loads = []

    def loader(key, scheduler):
        loads.append((key, scheduler))
        return pipe, "cpu"

    p = LocalDiffusionImageProvider(loader=loader, seed=7, **kw)
    return p, loads


def test_scene_first_and_short_prompt():
    full = compose_image_prompt("A student memorizes past exam answers but fails a new question.")
    assert extract_scene(full) == "A student memorizes past exam answers but fails a new question."
    sd = compose_sd_prompt(full)
    assert sd.startswith("A student memorizes")
    assert "Do not include any text" not in sd  # 글자 금지는 negative prompt 로
    assert len(sd.split()) < 40  # CLIP 77 토큰 한도 안쪽 (단어 수로 대략 확인)


def test_turbo_defaults_no_negative_prompt():
    pipe = FakePipe()
    p, loads = make(pipe, model="sd-turbo")
    r = asyncio.run(p.generate(compose_image_prompt("a cat")))
    prompt, kw = pipe.calls[0]
    assert kw["num_inference_steps"] == 2 and kw["guidance_scale"] == 0.0
    assert "negative_prompt" not in kw  # CFG 를 안 쓰면 negative prompt 는 효과가 없으므로 보내지 않음
    assert (kw["width"], kw["height"]) == (768, 432)
    assert r.mime == "image/jpeg" and (r.width, r.height) == (768, 432)
    assert r.usage.provider == "local" and r.usage.settings["seed"] == 7 and r.usage.settings["sd_prompt"] == prompt
    assert loads == [("sd-turbo", None)]
    asyncio.run(p.generate("again"))
    assert len(loads) == 1  # 한 번만 로드


def test_sd15_uses_cfg_and_negative_prompt():
    pipe = FakePipe()
    p, loads = make(pipe, model="sd15")  # 기본 스케줄러 ddim (미리보기에 x̂0 가 필요)
    asyncio.run(p.generate("x"))
    _, kw = pipe.calls[0]
    assert kw["num_inference_steps"] == 25 and kw["guidance_scale"] == 7.5 and kw["negative_prompt"] == SD_NEGATIVE
    assert loads == [("sd15", "ddim")]


def test_wrong_aspect_rejected():
    p, _ = make(FakePipe(size=(512, 512)), model="sd-turbo")
    with pytest.raises(ProviderError) as e:
        asyncio.run(p.generate("x"))
    assert e.value.code == "bad_format" and e.value.usage is not None


def test_pipeline_error_is_retryable_upstream():
    class Boom:
        def __call__(self, *a, **k):
            raise RuntimeError("MPS backend out of memory")

    p, _ = make(Boom(), model="sd-turbo")
    with pytest.raises(ProviderError) as e:
        asyncio.run(p.generate("x"))
    assert e.value.code == "upstream" and e.value.retryable and "out of memory" in e.value.message


def test_invalid_settings():
    with pytest.raises(ValueError):
        LocalDiffusionImageProvider(model="nope")
    with pytest.raises(ValueError):
        LocalDiffusionImageProvider(model="sd-turbo", gen_size="770x432")


def test_config_and_cost(monkeypatch):
    from app.config import Settings
    from app.metrics import estimate_cost
    from app.providers.base import Usage

    monkeypatch.setenv("IMAGE_PROVIDER", "local")
    s = Settings()
    info = s.public_info()
    assert info["image"]["provider"] == "local" and info["mock"]["image"] is False
    assert estimate_cost(s, Usage(provider="local", model="m", kind="image", image_count=1)) == 0.0


def test_fit_prompt_keeps_style_and_drops_trailing_sentences():
    from app.providers.local_image import SD_STYLE

    count = lambda s: len(s.split()) + 2  # noqa: E731  (가짜 토크나이저: 단어 1개 = 토큰 1개 + 시작·끝)
    scene = "First short sentence here. " + "Second sentence " * 20 + ". Third one."
    out = compose_sd_prompt(compose_image_prompt(scene), count, max_tokens=40)
    assert out.endswith(SD_STYLE) and count(out) <= 40
    assert out.startswith("First short sentence here")
    assert "Third" not in out


def test_fit_prompt_cuts_words_when_single_long_sentence():
    count = lambda s: len(s.split()) + 2  # noqa: E731
    out = compose_sd_prompt("word " * 100, count, max_tokens=30)
    assert count(out) <= 30 and out.startswith("word word")


def test_fit_prompt_short_scene_unchanged():
    count = lambda s: len(s.split()) + 2  # noqa: E731
    assert compose_sd_prompt("a cat", count) == compose_sd_prompt("a cat")


class StepPipe(FakePipe):
    """스케줄러 step 과 callback_on_step_end 를 흉내 내는 가짜 파이프라인."""

    def __init__(self, steps):
        super().__init__()
        self.scheduler = types.SimpleNamespace(step=lambda *a, **k: ("prev", f"x0-{len(self.calls)}"))
        self.tokenizer = None

    def __call__(self, prompt, **kw):
        cb = kw.get("callback_on_step_end")
        for i in range(kw["num_inference_steps"]):
            self.scheduler.step(None, i, None, return_dict=False)
            if cb:
                cb(self, i, i, {"latents": "lat"})
        return super().__call__(prompt, **kw)


def test_preview_called_each_step_except_last(monkeypatch):
    import app.providers.local_image as li

    monkeypatch.setattr(li, "latent_preview_jpeg", lambda x0: f"jpg:{x0}".encode())
    monkeypatch.setattr(li, "PREVIEW_MIN_INTERVAL_S", 0.0)
    got = []

    async def on_preview(step, total, jpg):
        got.append((step, total, jpg))

    pipe = StepPipe(4)
    p, _ = make(pipe, model="sd15", steps=4)

    async def go():
        r = await p.generate("x", on_preview=on_preview)
        await asyncio.sleep(0.01)  # call_soon_threadsafe 로 넘긴 미리보기 처리
        return r

    asyncio.run(go())
    assert [g[0] for g in got] == [1, 2, 3] and all(g[1] == 4 for g in got)
    assert got[0][2] == b"jpg:x0-0"
    assert "step" not in vars(pipe.scheduler) or callable(pipe.scheduler.step)
