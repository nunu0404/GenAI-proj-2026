"""확산 모델 실험 공통. 시스템과 같은 로더·모델 표를 쓰도록 백엔드 어댑터에서 가져온다."""
from __future__ import annotations

import platform
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.providers.local_image import MODELS, load_pipeline, sync  # noqa: E402,F401

OUT_ROOT = ROOT / "eval" / "results" / "diffusion"


def device_info(device: str) -> dict:
    import torch

    return {"device": device, "torch": torch.__version__, "machine": platform.machine(),
            "platform": platform.platform()}
