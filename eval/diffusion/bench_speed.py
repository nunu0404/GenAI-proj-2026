"""로컬 확산 모델 생성 속도 측정 (API 미사용, 비용 0).

예)
  backend/.venv/bin/python eval/diffusion/bench_speed.py --model sd-turbo --steps 1 2 4 -n 3
  backend/.venv/bin/python eval/diffusion/bench_speed.py --model sd15 --steps 50 25 10 -n 3 --cfg 7.5

- 시간은 파이프라인 호출 전후의 단조 시계(time.perf_counter) 차이이며, MPS/CUDA 동기화 후 잰다.
- 첫 호출(워밍업)은 그래프 준비·메모리 할당이 섞이므로 따로 기록하고 통계에서 뺀다.
- 결과: eval/results/diffusion/speed_<model>_<시각>.json 과 생성 이미지.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import MODELS, OUT_ROOT, device_info, load_pipeline, sync  # noqa: E402

PROMPT = ("flat vector illustration for a lecture slide: a student studying only past exam answers "
          "and failing a new question, overfitting metaphor, clean shapes, soft colors, no text")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", choices=sorted(MODELS), required=True)
    ap.add_argument("--steps", type=int, nargs="+", required=True)
    ap.add_argument("-n", type=int, default=3, help="스텝 설정별 반복 횟수(워밍업 제외)")
    ap.add_argument("--cfg", type=float, default=None, help="미지정 시 모델 기본값")
    ap.add_argument("--width", type=int, default=768)
    ap.add_argument("--height", type=int, default=432)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    spec = MODELS[args.model]
    cfg = spec["default_cfg"] if args.cfg is None else args.cfg
    t0 = time.perf_counter()
    pipe, device = load_pipeline(args.model)
    load_s = time.perf_counter() - t0

    import torch

    stamp = time.strftime("%Y%m%d_%H%M%S")
    out_dir = OUT_ROOT / f"speed_{args.model}_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    def run(steps: int, seed: int):
        g = torch.Generator("cpu").manual_seed(seed)
        sync(device)
        s = time.perf_counter()
        img = pipe(PROMPT, num_inference_steps=steps, guidance_scale=cfg, width=args.width, height=args.height,
                   generator=g).images[0]
        sync(device)
        return img, time.perf_counter() - s

    warm_img, warm_s = run(args.steps[0], args.seed)
    rows = []
    for steps in args.steps:
        times = []
        for i in range(args.n):
            img, dt = run(steps, args.seed + i)
            times.append(dt)
            img.save(out_dir / f"steps{steps}_seed{args.seed + i}.png")
        rows.append({"steps": steps, "n": len(times), "times_s": [round(t, 3) for t in times],
                     "median_s": round(statistics.median(times), 3), "min_s": round(min(times), 3),
                     "max_s": round(max(times), 3)})
        print(f"{args.model} steps={steps:>3} cfg={cfg}: median {statistics.median(times):.2f}s "
              f"(min {min(times):.2f}, max {max(times):.2f}, n={len(times)})", flush=True)

    result = {"model": args.model, "repo": spec["repo"], "device": device_info(device), "cfg": cfg,
              "size": [args.width, args.height], "prompt": PROMPT, "load_s": round(load_s, 2),
              "warmup_s": round(warm_s, 3), "rows": rows, "images": str(out_dir)}
    (out_dir / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"load {load_s:.1f}s, warmup {warm_s:.2f}s → {out_dir}/result.json")


if __name__ == "__main__":
    main()
