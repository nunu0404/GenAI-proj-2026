"""블라인드 평가 시트 집계: 사람이 작성한 rating_sheet.csv 와 key.json 을 결합해 조건별 요약.

실행: python eval/score_ratings.py eval/results/context_ab_YYYYmmdd_HHMMSS
빈 칸은 집계에서 제외하되 응답 수(n)를 함께 표시한다. 평가하지 않은 항목의 점수는 만들지 않는다.
"""
from __future__ import annotations

import csv
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

SCORES = ["request_fit", "continuity", "image_help"]
FLAGS = ["factual_error", "hard_to_read"]


def main(folder: str) -> None:
    d = Path(folder)
    key = json.loads((d / "key.json").read_text())
    meta = json.loads((d / "outputs.json").read_text())["meta"]
    vals: dict[tuple[str, str], list[float]] = defaultdict(list)
    flags: dict[tuple[str, str], list[bool]] = defaultdict(list)
    rated_items = set()
    with (d / "rating_sheet.csv").open(encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            cond = key[row["item_id"]]["condition"]
            for c in SCORES:
                v = (row.get(c) or "").strip()
                if v:
                    vals[(cond, c)].append(float(v))
                    rated_items.add(row["item_id"])
            for c in FLAGS:
                v = (row.get(c) or "").strip().upper()
                if v in ("Y", "N"):
                    flags[(cond, c)].append(v == "Y")
    if not rated_items:
        print("평가 점수가 비어 있습니다. 실제 평가자가 rating_sheet.csv 를 작성한 뒤 다시 실행하세요.")
        return
    if meta.get("mock"):
        print("⚠ MOCK 생성물에 대한 평가입니다. 결과를 보고에 사용하지 마세요.")
    print(f"모델: {meta['text_model']} / {meta['image_model']} · 시나리오 {meta['n_scenarios']} · 반복 {meta['repeats']}")
    print("| 조건 | 기준 | n | 평균 | 중앙값 |")
    print("|---|---|---|---|---|")
    for cond in ("A", "B"):
        for c in SCORES:
            xs = vals.get((cond, c), [])
            if xs:
                print(f"| {cond} | {c} | {len(xs)} | {statistics.fmean(xs):.2f} | {statistics.median(xs):.1f} |")
            else:
                print(f"| {cond} | {c} | 0 | – | – |")
        for c in FLAGS:
            xs = flags.get((cond, c), [])
            print(f"| {cond} | {c} (Y 비율) | {len(xs)} | {(sum(xs)/len(xs)):.0%} | |" if xs else f"| {cond} | {c} | 0 | – | |")
    print("\n표본이 작아 차이를 일반화하기 어렵습니다. 시나리오별 짝 비교와 평가자 간 일치도도 함께 확인하세요.")


if __name__ == "__main__":
    main(sys.argv[1])
