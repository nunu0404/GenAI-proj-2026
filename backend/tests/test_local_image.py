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
    p, loads = make(pipe, model="sd15", scheduler="ddim")
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
