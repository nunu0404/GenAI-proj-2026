"""맥락 효과 비교 (A: 요청만 / B: 요청 + 최근 강의 맥락).

- 모델·프롬프트·템플릿·이미지 스타일은 동일하게 고정하고 '맥락 포함 여부'만 바꾼다.
  (A·B 모두 강의 제목과 청중 수준은 포함한다.)
- 실패한 생성도 결과에 그대로 남긴다(조용히 제외하지 않음).
- 평가자가 조건을 모르도록 순서를 섞은 블라인드 자료(review.html, rating_sheet.csv)와
  별도의 정답 키(key.json)를 만든다. 점수는 사람이 매긴 뒤 score_ratings.py 로 집계한다.
- 생성은 확률적이므로 시나리오 12개·반복 1회 결과를 일반화하지 않는다(--repeats 로 반복 가능).

실행 (실제 API, 비용 발생):
  TEXT_PROVIDER=anthropic IMAGE_PROVIDER=openai backend/.venv/bin/python eval/run_context_ab.py --images
mock 으로 하네스만 점검:
  backend/.venv/bin/python eval/run_context_ab.py --allow-mock --out <dir>
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import html
import json
import random
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.config import Settings  # noqa: E402
from app.planner import PlanError, compose_image_prompt, plan_slide  # noqa: E402
from app.providers import make_image_provider, make_text_provider  # noqa: E402
from app.providers.base import ProviderError  # noqa: E402
from app.providers.image_validation import EXT  # noqa: E402

CRITERIA = [
    ("request_fit", "요청 적합성 (1~5)"),
    ("continuity", "앞선 설명과의 연결 (1~5)"),
    ("image_help", "이미지의 설명 도움 정도 (1~5, 이미지 없으면 비움)"),
    ("factual_error", "사실 오류 있음 (Y/N)"),
    ("hard_to_read", "읽기 어려움 (Y/N)"),
]


def ctx_of(sc: dict) -> dict:
    return {"lecture_title": sc["lecture_title"], "audience": sc["audience"], "transcript": " ".join(sc["transcript"]),
            "current_slide": sc["current_slide"]}


async def run_one(s: Settings, text, image, sc: dict, cond: str, with_images: bool, out: Path, rep: int) -> dict:
    rec: dict = {"scenario": sc["id"], "condition": cond, "repeat": rep, "text_model": text.model,
                 "image_model": image.model if with_images else None, "mock": text.is_mock or (with_images and image.is_mock)}
    t0 = time.monotonic()
    try:
        plan = await plan_slide(text, ctx_of(sc), sc["request"], s.text_max_repair, include_context=(cond == "B"))
        rec["plan_ms"] = round((time.monotonic() - t0) * 1000, 1)
        rec["spec"] = plan.spec.model_dump()
        rec["usage"] = [u.__dict__ for u in plan.usages]
    except PlanError as e:
        rec.update(status="failed", stage="plan", error=f"{e.code}: {e.message}", plan_ms=round((time.monotonic() - t0) * 1000, 1))
        return rec
    if plan.spec.needs_clarification:
        rec.update(status="needs_clarification")
        return rec
    if with_images:
        t1 = time.monotonic()
        try:
            img = await image.generate(compose_image_prompt(plan.spec.image_prompt))
            p = out / "images" / f"{sc['id']}_{cond}_r{rep}.{EXT[img.mime]}"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(img.data)
            rec["image_file"] = str(p.relative_to(out))
            rec["image_ms"] = round((time.monotonic() - t1) * 1000, 1)
        except ProviderError as e:
            rec.update(status="failed", stage="image", error=f"{e.code}: {e.message}", image_ms=round((time.monotonic() - t1) * 1000, 1))
            return rec
    rec["status"] = "ok"
    return rec


def write_blind(out: Path, records: list[dict], scenarios: dict, seed: int) -> None:
    rnd = random.Random(seed)
    items = list(records)
    rnd.shuffle(items)
    key, cards = {}, []
    for i, r in enumerate(items, 1):
        iid = f"item-{i:02d}"
        key[iid] = {"scenario": r["scenario"], "condition": r["condition"], "repeat": r["repeat"]}
        sc = scenarios[r["scenario"]]
        spec = r.get("spec") or {}
        body = (
            f"<h3>{iid}</h3>"
            f"<div class='ctx'><b>강의</b> {html.escape(sc['lecture_title'])} · {html.escape(sc['audience'])}<br>"
            f"<b>최근 강의 발화</b> {html.escape(' '.join(sc['transcript']))}<br>"
            f"<b>현재 슬라이드</b> {html.escape(sc['current_slide']['title'])}<br>"
            f"<b>요청</b> {html.escape(sc['request'])}</div>"
        )
        if r["status"] == "ok":
            bullets = "".join(f"<li>{html.escape(b)}</li>" for b in spec.get("bullets", []))
            img = f"<img src='{html.escape(r['image_file'])}'>" if r.get("image_file") else "<div class='noimg'>이미지 없음</div>"
            body += f"<div class='slide'><div><h2>{html.escape(spec['title'])}</h2><ul>{bullets}</ul></div>{img}</div>"
        else:
            body += f"<div class='fail'>생성 결과 없음 ({html.escape(r['status'])})</div>"
        cards.append(f"<section>{body}</section>")
    mock_note = "<p class='mock'>⚠ MOCK 결과 — 평가용으로 사용하지 마세요.</p>" if any(r.get("mock") for r in records) else ""
    (out / "review.html").write_text(
        "<!doctype html><meta charset='utf-8'><title>NextSlide 블라인드 평가</title>"
        "<style>body{font-family:'Noto Sans KR',sans-serif;max-width:1000px;margin:auto;padding:16px}section{border:1px solid #ddd;"
        "border-radius:8px;padding:12px;margin:16px 0}.ctx{font-size:13px;color:#444;background:#f7f7f7;padding:8px;border-radius:6px}"
        ".slide{display:grid;grid-template-columns:42% 1fr;gap:16px;margin-top:10px;aspect-ratio:16/9;background:#fbfaf6;padding:16px}"
        ".slide img{width:100%;height:100%;object-fit:contain}.mock{color:#b00;font-weight:700}.fail{color:#b00}</style>"
        f"<h1>블라인드 평가</h1>{mock_note}<p>각 항목을 보고 rating_sheet.csv 에 점수를 적어 주세요. 조건(A/B)은 표시하지 않습니다.</p>"
        + "".join(cards))
    with (out / "rating_sheet.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["item_id", "rater"] + [c for c, _ in CRITERIA] + ["memo"])
        for iid in key:
            w.writerow([iid, ""] + [""] * len(CRITERIA) + [""])
    (out / "key.json").write_text(json.dumps(key, ensure_ascii=False, indent=2))
    (out / "RATING_GUIDE.md").write_text(
        "# 평가 기준\n\n" + "\n".join(f"- `{c}`: {d}" for c, d in CRITERIA)
        + "\n\n평가 전에는 key.json 을 열지 마세요. 집계: `python eval/score_ratings.py <이 폴더>`\n")


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", action="store_true", help="이미지까지 생성 (비용 증가)")
    ap.add_argument("--allow-mock", action="store_true")
    ap.add_argument("--repeats", type=int, default=1)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--seed", type=int, default=20261105)
    ap.add_argument("--out", type=str, default="")
    args = ap.parse_args()

    s = Settings()
    text, image = make_text_provider(s), make_image_provider(s)
    if (text.is_mock or (args.images and image.is_mock)) and not args.allow_mock:
        sys.exit("mock 제공자가 설정되어 있습니다. 실제 평가는 TEXT_PROVIDER/IMAGE_PROVIDER 를 설정하세요 "
                 "(하네스 점검만 하려면 --allow-mock).")
    scenarios = json.loads((ROOT / "eval" / "context_scenarios.json").read_text())
    if args.limit:
        scenarios = scenarios[: args.limit]
    out = Path(args.out) if args.out else ROOT / "eval" / "results" / f"context_ab_{datetime.now():%Y%m%d_%H%M%S}"
    out.mkdir(parents=True, exist_ok=True)
    records = []
    for rep in range(args.repeats):
        for sc in scenarios:
            for cond in ("A", "B"):
                r = await run_one(s, text, image, sc, cond, args.images, out, rep)
                print(f"{sc['id']} {cond} r{rep}: {r['status']} plan={r.get('plan_ms')}ms image={r.get('image_ms')}ms {r.get('error', '')}")
                records.append(r)
    meta = {"created": datetime.now().isoformat(timespec="seconds"), "text_model": text.model,
            "image_model": image.model if args.images else None, "mock": any(r.get("mock") for r in records),
            "n_scenarios": len(scenarios), "repeats": args.repeats,
            "status_counts": {k: sum(1 for r in records if r["status"] == k) for k in {r["status"] for r in records}},
            "note": "A=요청만(강의 제목·청중 포함), B=요청+최근 발화+현재 슬라이드. 나머지 조건 동일."}
    (out / "outputs.json").write_text(json.dumps({"meta": meta, "records": records}, ensure_ascii=False, indent=2))
    write_blind(out, records, {sc["id"]: sc for sc in scenarios}, args.seed)
    print(json.dumps(meta, ensure_ascii=False))
    print(f"출력: {out}")


if __name__ == "__main__":
    asyncio.run(main())
