"""run_sweep.py 결과 채점: CLIP 유사도(프롬프트 일치도), 시드 간 다양성, 생성 시간.

  backend/.venv/bin/python eval/diffusion/score_clip.py eval/results/diffusion/x2_cfg

- 평가 모델: openai/clip-vit-base-patch32. 생성에 쓰인 텍스트 인코더(SD1.5: CLIP ViT-L/14, SD-Turbo: OpenCLIP ViT-H)와
  다른 모델이라 '생성기가 자기 인코더 기준으로만 맞춘' 효과를 줄인다. 그래도 CLIP 계열 편향은 남는다.
- CLIP 유사도 = 이미지 임베딩과 '장면 문장'(화풍 문구 제외) 임베딩의 코사인 × 100.
- 다양성 = 같은 장면·조건에서 시드끼리 이미지 임베딩의 (1 - 코사인) 평균. 시드 2개면 쌍 1개.
- 신뢰구간: 장면별로 시드 평균을 낸 뒤 장면 12개를 부트스트랩(2000회)한 95% 구간. 표본이 작으니 경향으로만 해석한다.
- 이 점수는 '그림이 장면 문장과 얼마나 맞는가'만 본다. 설명에 도움이 되는지, 글자가 섞였는지는 사람이 따로 본다.
결과: summary.md, summary.csv, scores.jsonl, sheet.html(눈으로 비교용).
"""
from __future__ import annotations

import csv
import html
import json
import random
import statistics
import sys
from collections import defaultdict
from itertools import combinations
from pathlib import Path

CLIP = "openai/clip-vit-base-patch32"


def boot_ci(vals: list[float], n: int = 2000, seed: int = 0) -> tuple[float, float]:
    if len(vals) < 2:
        return (float("nan"), float("nan"))
    rnd = random.Random(seed)
    means = sorted(statistics.fmean(rnd.choices(vals, k=len(vals))) for _ in range(n))
    return means[int(0.025 * n)], means[int(0.975 * n) - 1]


def main(run_dir: Path) -> None:
    import torch
    from PIL import Image
    from transformers import CLIPModel, CLIPProcessor

    runs = [json.loads(x) for x in (run_dir / "runs.jsonl").read_text().splitlines() if x.strip()]
    model = CLIPModel.from_pretrained(CLIP).eval()
    proc = CLIPProcessor.from_pretrained(CLIP)

    @torch.no_grad()
    def emb_text(texts):
        t = proc(text=texts, return_tensors="pt", padding=True, truncation=True)
        e = model.get_text_features(**t)
        return torch.nn.functional.normalize(e, dim=-1)

    @torch.no_grad()
    def emb_img(paths):
        ims = [Image.open(p).convert("RGB") for p in paths]
        e = model.get_image_features(**proc(images=ims, return_tensors="pt"))
        return torch.nn.functional.normalize(e, dim=-1)

    scene_texts = sorted({r["scene_text"] for r in runs})
    temb = dict(zip(scene_texts, emb_text(scene_texts)))
    img_emb = {}
    for i in range(0, len(runs), 16):
        batch = runs[i:i + 16]
        for r, e in zip(batch, emb_img([run_dir / "images" / r["file"] for r in batch])):
            img_emb[r["file"]] = e
    for r in runs:
        r["clip"] = round(float(img_emb[r["file"]] @ temb[r["scene_text"]]) * 100, 2)
    (run_dir / "scores.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in runs) + "\n")

    key = lambda r: (r["scheduler"], r["steps"], r["cfg"])  # noqa: E731
    groups: dict = defaultdict(list)
    for r in runs:
        groups[key(r)].append(r)
    rows = []
    for k, rs in sorted(groups.items(), key=lambda kv: (kv[0][0], -kv[0][1], kv[0][2])):
        by_scene: dict = defaultdict(list)
        for r in rs:
            by_scene[r["scene"]].append(r)
        scene_clip = [statistics.fmean(x["clip"] for x in v) for v in by_scene.values()]
        div = []
        for v in by_scene.values():
            pairs = list(combinations(v, 2))
            if pairs:
                div.append(statistics.fmean(1 - float(img_emb[a["file"]] @ img_emb[b["file"]]) for a, b in pairs))
        lo, hi = boot_ci(scene_clip)
        secs = [r["seconds"] for r in rs]
        rows.append({"scheduler": k[0], "steps": k[1], "cfg": k[2], "n_images": len(rs), "n_scenes": len(by_scene),
                     "clip_mean": round(statistics.fmean(scene_clip), 2), "clip_ci_lo": round(lo, 2),
                     "clip_ci_hi": round(hi, 2), "diversity": round(statistics.fmean(div), 4) if div else None,
                     "sec_median": round(statistics.median(secs), 2), "sec_max": round(max(secs), 2)})

    with (run_dir / "summary.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    meta = json.loads((run_dir / "meta.json").read_text()) if (run_dir / "meta.json").exists() else {}
    md = [f"# {run_dir.name}", "", f"- 모델: {meta.get('model')} / 장치: {meta.get('device', {}).get('device')}",
          f"- 평가: {CLIP}, CLIP 유사도 = 코사인×100 (장면 문장 기준), 95% CI = 장면 부트스트랩", "",
          "| 샘플러 | 스텝 | CFG | 이미지 | CLIP 유사도 (95% CI) | 다양성 | 시간 중앙값(s) |", "|---|---|---|---|---|---|---|"]
    for r in rows:
        md.append(f"| {r['scheduler']} | {r['steps']} | {r['cfg']:g} | {r['n_images']} | {r['clip_mean']} "
                  f"({r['clip_ci_lo']}–{r['clip_ci_hi']}) | {r['diversity']} | {r['sec_median']} |")
    (run_dir / "summary.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))

    # 눈으로 비교할 표: 행 = 장면(시드 0), 열 = 조건
    cols = [k for k in sorted(groups, key=lambda k: (k[0], -k[1], k[2]))]
    seed0 = min(r["seed"] for r in runs)
    cell = {(r["scene"], key(r)): r for r in runs if r["seed"] == seed0}
    scenes = sorted({r["scene"] for r in runs})
    h = ["<!doctype html><meta charset=utf-8><title>sheet</title><style>body{font:13px system-ui;margin:16px}"
         "table{border-collapse:collapse}td,th{border:1px solid #ddd;padding:4px;vertical-align:top}"
         "img{width:240px;display:block}</style><table><tr><th>scene</th>"]
    h += [f"<th>{html.escape(f'{c[0]} / {c[1]} steps / cfg {c[2]:g}')}</th>" for c in cols]
    h.append("</tr>")
    for s in scenes:
        h.append(f"<tr><th>{s}</th>")
        for c in cols:
            r = cell.get((s, c))
            h.append(f"<td><img src='images/{r['file']}'>{r['clip']} · {r['seconds']}s</td>" if r else "<td></td>")
        h.append("</tr>")
    (run_dir / "sheet.html").write_text("".join(h) + "</table>")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
