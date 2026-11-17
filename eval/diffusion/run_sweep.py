"""확산 모델 설정 비교 실험 (로컬, API 비용 0). 한 번에 한 설정만 바꾼다.

X1 샘플러·스텝:   --model sd15 --schedulers ddpm ddim --steps 50 25 10 --cfg 7.5
X2 CFG 스케일:     --model sd15 --schedulers ddim --steps 25 --cfg 1 3 5 7.5 12
X3 모델(증류):     --model sd-turbo --steps 1 2 4 --cfg 0

- 프롬프트는 시스템과 같은 방식(장면 + 짧은 화풍, CFG>1 이면 글자 금지 negative prompt)으로 만든다.
- 시드는 장면·조건마다 같은 값을 써서 조건만 다르게 한다(초기 잡음 고정).
- 결과: eval/results/diffusion/<이름>/ 아래 이미지와 runs.jsonl(조건, 시간). 채점은 score_clip.py.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import OUT_ROOT, device_info, load_pipeline, sync  # noqa: E402

from app.providers.local_image import SD_NEGATIVE, compose_sd_prompt, tokenizer_counter  # noqa: E402

PROMPTS = Path(__file__).resolve().parent / "prompts.json"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True, help="결과 폴더 이름 (예: x1_sampler)")
    ap.add_argument("--model", required=True)
    ap.add_argument("--schedulers", nargs="+", default=["default"], help="default | ddim | ddpm | euler")
    ap.add_argument("--steps", type=int, nargs="+", required=True)
    ap.add_argument("--cfg", type=float, nargs="+", required=True)
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1])
    ap.add_argument("--width", type=int, default=768)
    ap.add_argument("--height", type=int, default=432)
    ap.add_argument("--limit", type=int, default=0, help="장면 수 제한(점검용)")
    args = ap.parse_args()

    import torch
    from diffusers import DDIMScheduler, DDPMScheduler, EulerDiscreteScheduler

    scenes = json.loads(PROMPTS.read_text())["scenes"]
    if args.limit:
        scenes = scenes[:args.limit]
    out = OUT_ROOT / args.name
    (out / "images").mkdir(parents=True, exist_ok=True)
    runs_path = out / "runs.jsonl"
    done = set()
    if runs_path.exists():  # 중단 후 이어서 실행
        for line in runs_path.read_text().splitlines():
            r = json.loads(line)
            done.add(r["file"])

    t = time.perf_counter()
    pipe, device = load_pipeline(args.model)
    load_s = time.perf_counter() - t
    base_cfg = pipe.scheduler.config
    classes = {"ddim": DDIMScheduler, "ddpm": DDPMScheduler, "euler": EulerDiscreteScheduler,
               "default": type(pipe.scheduler)}
    meta = {"model": args.model, "device": device_info(device), "load_s": round(load_s, 1), "args": vars(args),
            "default_scheduler": type(pipe.scheduler).__name__}
    (out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2))

    # 워밍업 1회 (기록 안 함)
    pipe("warmup", num_inference_steps=args.steps[0], guidance_scale=args.cfg[0], width=args.width,
         height=args.height)

    total = len(args.schedulers) * len(args.steps) * len(args.cfg) * len(scenes) * len(args.seeds)
    k = 0
    with runs_path.open("a") as f:
        for sch in args.schedulers:
            pipe.scheduler = classes[sch].from_config(base_cfg)
            for steps in args.steps:
                for cfg in args.cfg:
                    for sc in scenes:
                        prompt = compose_sd_prompt(sc["scene"], tokenizer_counter(pipe.tokenizer))
                        for seed in args.seeds:
                            k += 1
                            fname = f"{sc['id']}_{sch}_s{steps}_g{cfg:g}_seed{seed}.jpg"
                            if fname in done:
                                continue
                            kw = dict(num_inference_steps=steps, guidance_scale=cfg, width=args.width,
                                      height=args.height, generator=torch.Generator("cpu").manual_seed(seed))
                            if cfg > 1.0:
                                kw["negative_prompt"] = SD_NEGATIVE
                            sync(device)
                            s = time.perf_counter()
                            img = pipe(prompt, **kw).images[0]
                            sync(device)
                            dt = time.perf_counter() - s
                            img.convert("RGB").save(out / "images" / fname, quality=90)
                            rec = {"file": fname, "scene": sc["id"], "scheduler": sch, "steps": steps, "cfg": cfg,
                                   "seed": seed, "seconds": round(dt, 3), "prompt": prompt, "scene_text": sc["scene"]}
                            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                            f.flush()
                            print(f"[{k}/{total}] {fname} {dt:.2f}s", flush=True)
    print(f"done → {out}")


if __name__ == "__main__":
    main()
