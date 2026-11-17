"""X4 조건 설계: 강의 맥락을 조건에 넣으면 그림이 강사 의도에 더 가까워지는가.

A = 요청만(강의 제목·청중 포함) / B = 요청 + 최근 발화 + 현재 장. 기획 LLM·이미지 모델·시드는 같고 맥락 포함 여부만 다르다.

1) plan   : 실제 기획 LLM 으로 시나리오 12개 × A/B 기획 (비용 발생, 약 $0.01)
   backend/.venv/bin/python eval/diffusion/run_x4_context.py plan
2) render : 같은 로컬 확산 모델·같은 시드로 A/B 그림 프롬프트를 그림 (비용 0)
   backend/.venv/bin/python eval/diffusion/run_x4_context.py render --model sd-turbo --steps 2 --cfg 0
3) score  : CLIP(그림, 정답 장면 설명) 을 시나리오별로 짝지어 비교
   backend/.venv/bin/python eval/diffusion/run_x4_context.py score

정답 장면 설명(x4_gold.json)은 결과를 보기 전에 작성했다. 기획 LLM 이 그림 대신 표·수식 등을 고르면 그 조건은
그림이 없으므로 짝 비교에서 빠지고, 형태 분포는 따로 보고한다.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import random
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
from common import OUT_ROOT, load_pipeline, sync  # noqa: E402

from app.config import Settings  # noqa: E402
from app.planner import PlanError, compose_image_prompt, plan_slide  # noqa: E402
from app.providers import make_text_provider  # noqa: E402
from app.providers.local_image import MODELS, SD_NEGATIVE, compose_sd_prompt, tokenizer_counter  # noqa: E402
from run_context_ab import ctx_of  # noqa: E402

OUT = OUT_ROOT / "x4_context"
SCEN = HERE.parent / "context_scenarios.json"
GOLD = json.loads((HERE / "x4_gold.json").read_text())["gold"]


async def do_plan() -> None:
    s = Settings()
    text = make_text_provider(s)
    if text.is_mock:
        sys.exit("TEXT_PROVIDER 가 mock 입니다. 실제 기획 LLM 으로 실행하세요.")
    OUT.mkdir(parents=True, exist_ok=True)
    recs = []
    for sc in json.loads(SCEN.read_text()):
        for cond in ("A", "B"):
            t0 = time.monotonic()
            rec = {"scenario": sc["id"], "condition": cond, "text_model": text.model}
            try:
                plan = await plan_slide(text, ctx_of(sc), sc["request"], s.text_max_repair,
                                        include_context=(cond == "B"))
                rec.update(status="ok", spec=plan.spec.model_dump(), usage=[u.__dict__ for u in plan.usages])
            except PlanError as e:
                rec.update(status="failed", error=f"{e.code}: {e.message}")
            rec["plan_ms"] = round((time.monotonic() - t0) * 1000, 1)
            spec = rec.get("spec") or {}
            print(sc["id"], cond, rec["status"], spec.get("visual_type"), "|", (spec.get("image_prompt") or "")[:90],
                  flush=True)
            recs.append(rec)
    (OUT / "plans.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in recs) + "\n")


def load_plans() -> list[dict]:
    return [json.loads(x) for x in (OUT / "plans.jsonl").read_text().splitlines() if x.strip()]


def do_render(model: str, steps: int, cfg: float, seeds: list[int]) -> None:
    import torch

    pipe, device = load_pipeline(model)
    (OUT / "images").mkdir(parents=True, exist_ok=True)
    pipe("warmup", num_inference_steps=steps, guidance_scale=cfg, width=768, height=432)
    runs = []
    for r in load_plans():
        ip = ((r.get("spec") or {}).get("image_prompt") or "").strip()
        if r["status"] != "ok" or not ip or (r["spec"].get("needs_clarification")):
            continue
        prompt = compose_sd_prompt(compose_image_prompt(ip), tokenizer_counter(pipe.tokenizer))
        for seed in seeds:
            kw = dict(num_inference_steps=steps, guidance_scale=cfg, width=768, height=432,
                      generator=torch.Generator("cpu").manual_seed(seed))
            if cfg > 1.0:
                kw["negative_prompt"] = SD_NEGATIVE
            sync(device)
            t = time.perf_counter()
            img = pipe(prompt, **kw).images[0]
            sync(device)
            fname = f"{r['scenario']}_{r['condition']}_seed{seed}.jpg"
            img.convert("RGB").save(OUT / "images" / fname, quality=90)
            runs.append({"file": fname, "scenario": r["scenario"], "condition": r["condition"], "seed": seed,
                         "prompt": prompt, "image_prompt": ip, "seconds": round(time.perf_counter() - t, 3)})
            print(fname, flush=True)
    meta = {"model": model, "repo": MODELS[model]["repo"], "steps": steps, "cfg": cfg, "seeds": seeds}
    (OUT / "render_meta.json").write_text(json.dumps(meta, indent=2))
    (OUT / "renders.jsonl").write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in runs) + "\n")


def boot_ci(vals, n=2000, seed=0):
    rnd = random.Random(seed)
    m = sorted(statistics.fmean(rnd.choices(vals, k=len(vals))) for _ in range(n))
    return m[int(0.025 * n)], m[int(0.975 * n) - 1]


def do_score() -> None:
    import torch
    from PIL import Image
    from score_clip import CLIP, _feat
    from transformers import CLIPModel, CLIPProcessor

    model = CLIPModel.from_pretrained(CLIP).eval()
    proc = CLIPProcessor.from_pretrained(CLIP)

    @torch.no_grad()
    def et(texts):
        return torch.nn.functional.normalize(_feat(model.get_text_features(
            **proc(text=texts, return_tensors="pt", padding=True, truncation=True))), dim=-1)

    @torch.no_grad()
    def ei(paths):
        ims = [Image.open(p).convert("RGB") for p in paths]
        return torch.nn.functional.normalize(_feat(model.get_image_features(**proc(images=ims, return_tensors="pt"))),
                                             dim=-1)

    plans = load_plans()
    runs = [json.loads(x) for x in (OUT / "renders.jsonl").read_text().splitlines() if x.strip()]
    gold_ids = sorted(GOLD)
    gemb = dict(zip(gold_ids, et([GOLD[k] for k in gold_ids])))
    for i in range(0, len(runs), 16):
        b = runs[i:i + 16]
        for r, e in zip(b, ei([OUT / "images" / x["file"] for x in b])):
            r["clip_gold"] = round(float(e @ gemb[r["scenario"]]) * 100, 2)
    # 프롬프트(글) 수준: 기획 LLM 이 쓴 그림 묘사 자체가 정답 장면과 얼마나 가까운가
    prompt_sim = {}
    for p in plans:
        ip = ((p.get("spec") or {}).get("image_prompt") or "").strip()
        if ip:
            prompt_sim[(p["scenario"], p["condition"])] = round(float(et([ip])[0] @ gemb[p["scenario"]]) * 100, 2)

    by = {}
    for r in runs:
        by.setdefault((r["scenario"], r["condition"]), []).append(r["clip_gold"])
    paired = [(sid, statistics.fmean(by[(sid, "A")]), statistics.fmean(by[(sid, "B")]))
              for sid in gold_ids if (sid, "A") in by and (sid, "B") in by]
    diffs = [b - a for _, a, b in paired]
    pdiffs = [prompt_sim[(s, "B")] - prompt_sim[(s, "A")] for s in gold_ids
              if (s, "A") in prompt_sim and (s, "B") in prompt_sim]

    vt = {c: {} for c in "AB"}
    for p in plans:
        spec = p.get("spec") or {}
        k = "failed" if p["status"] != "ok" else ("needs_clarification" if spec.get("needs_clarification")
                                                  else spec.get("visual_type"))
        vt[p["condition"]][k] = vt[p["condition"]].get(k, 0) + 1
    meta = json.loads((OUT / "render_meta.json").read_text())
    lines = ["# X4 강의 맥락 조건 (A: 요청만 / B: 요청 + 맥락)", "",
             f"- 기획: {plans[0].get('text_model')} / 그림: {meta['model']} {meta['steps']}스텝 CFG {meta['cfg']} "
             f"시드 {meta['seeds']}", "",
             "## 기획 LLM 이 고른 형태", "", "| 조건 | 분포 |", "|---|---|"]
    for c in "AB":
        lines.append(f"| {c} | {', '.join(f'{k} {v}' for k, v in sorted(vt[c].items(), key=str))} |")
    lines += ["", f"## 정답 장면과의 CLIP 유사도 (A·B 모두 그림이 있는 시나리오 {len(paired)}개, 짝 비교)", "",
              "| 시나리오 | A | B | B−A | 프롬프트 글 B−A |", "|---|---|---|---|---|"]
    for sid, a, b in paired:
        pd = prompt_sim.get((sid, "B"), float("nan")) - prompt_sim.get((sid, "A"), float("nan"))
        lines.append(f"| {sid} | {a:.2f} | {b:.2f} | {b - a:+.2f} | {pd:+.2f} |")
    if len(diffs) >= 2:
        lo, hi = boot_ci(diffs)
        wins = sum(d > 0 for d in diffs)
        lines += ["", f"- 그림: B−A 평균 **{statistics.fmean(diffs):+.2f}** (95% CI {lo:+.2f}–{hi:+.2f}), "
                      f"B 가 높은 시나리오 {wins}/{len(diffs)}"]
    if len(pdiffs) >= 2:
        lo, hi = boot_ci(pdiffs)
        lines.append(f"- 그림 프롬프트(글): B−A 평균 **{statistics.fmean(pdiffs):+.2f}** (95% CI {lo:+.2f}–{hi:+.2f}), "
                     f"n={len(pdiffs)}")
    (OUT / "summary.md").write_text("\n".join(lines) + "\n")
    (OUT / "scores.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in runs) + "\n")
    print("\n".join(lines))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["plan", "render", "score"])
    ap.add_argument("--model", default="sd-turbo")
    ap.add_argument("--steps", type=int, default=2)
    ap.add_argument("--cfg", type=float, default=0.0)
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1])
    a = ap.parse_args()
    if a.stage == "plan":
        asyncio.run(do_plan())
    elif a.stage == "render":
        do_render(a.model, a.steps, a.cfg, a.seeds)
    else:
        do_score()


if __name__ == "__main__":
    main()
