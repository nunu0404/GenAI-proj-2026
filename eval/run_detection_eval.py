"""요청 감지 평가: 정답 라벨이 있는 발화 세트를 규칙 기반 감지기에 넣어 정확도를 측정한다 (API 호출 없음).

실행: backend/.venv/bin/python eval/run_detection_eval.py
결과: eval/results/detection_results.md
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.detector import RequestDetector  # noqa: E402

LABELS = ["request", "needs_input", "none"]


def predict(segments: list[str], gap_s: float = 0.8, silence_s: float = 2.5) -> tuple[str, str | None]:
    d = RequestDetector(silence_s=silence_s)
    t, evs = 0.0, []
    for i, seg in enumerate(segments):
        t += gap_s
        evs += d.feed_final(f"seg{i}", seg, t)
    evs += d.tick(t + silence_s + 0.1)  # 발화 후 침묵
    kinds = [e for e in evs if e.kind in ("request", "needs_input")]
    if any(e.kind == "request" for e in kinds):
        e = next(e for e in kinds if e.kind == "request")
        n_req = sum(1 for e in kinds if e.kind == "request")
        return ("request" if n_req == 1 else f"request x{n_req}"), e.topic
    if kinds:
        return "needs_input", kinds[0].topic
    return "none", None


def main() -> None:
    cases = [json.loads(l) for l in (ROOT / "eval" / "detection_cases.jsonl").read_text().splitlines() if l.strip()]
    rows, conf = [], Counter()
    by_cat: dict[str, list[bool]] = defaultdict(list)
    for c in cases:
        pred, topic = predict(c["segments"])
        ok = pred == c["label"]
        topic_ok = None
        if ok and c["label"] == "request" and c.get("topic_contains"):
            topic_ok = bool(topic and c["topic_contains"] in topic)
        conf[(c["label"], pred)] += 1
        by_cat[c["category"]].append(ok)
        rows.append((c, pred, topic, ok, topic_ok))

    n = len(cases)
    acc = sum(r[3] for r in rows) / n
    gen_fp = sum(1 for r in rows if r[0]["label"] != "request" and r[1].startswith("request"))
    gen_fn = sum(1 for r in rows if r[0]["label"] == "request" and not r[1].startswith("request"))
    lines = [
        "# 요청 감지 평가 결과",
        "",
        f"- 실행 시각: {datetime.now().isoformat(timespec='seconds')}",
        f"- 표본 수: {n} (규칙 기반 감지기, API 호출 없음, 결정적)",
        "- 시뮬레이션 조건: 확정 STT 구간 0.8초 간격 입력 후 침묵 2.6초 (REQUEST_SILENCE_MS=2500)",
        f"- 전체 정확도(3분류: request / needs_input / none): **{acc:.1%}** ({sum(r[3] for r in rows)}/{n})",
        f"- 잘못 생성(정답이 request 가 아닌데 생성): {gen_fp}건 · 놓친 생성(정답 request 인데 미생성): {gen_fn}건",
        "",
        "## 범주별",
        "",
        "| 범주 | n | 정답 |",
        "|---|---|---|",
    ]
    for cat, oks in by_cat.items():
        lines.append(f"| {cat} | {len(oks)} | {sum(oks)}/{len(oks)} |")
    lines += ["", "## 혼동 행렬 (행=정답, 열=예측)", "", "| 정답 \\ 예측 | " + " | ".join(LABELS) + " | 기타 |", "|---|---|---|---|---|"]
    for gold in LABELS:
        other = sum(v for (g, p), v in conf.items() if g == gold and p not in LABELS)
        lines.append(f"| {gold} | " + " | ".join(str(conf[(gold, p)]) for p in LABELS) + f" | {other} |")
    lines += ["", "## 사례별", "", "| id | 범주 | 입력 | 정답 | 예측 | 주제 추출 | 결과 |", "|---|---|---|---|---|---|---|"]
    for c, pred, topic, ok, topic_ok in rows:
        txt = " ▏".join(c["segments"]).replace("|", "/")
        mark = "✅" if ok else "❌"
        if topic_ok is False:
            mark += " (주제 불일치)"
        lines.append(f"| {c['id']} | {c['category']} | {txt} | {c['label']} | {pred} | {topic or ''} | {mark} |")
    fails = [r for r in rows if not r[3]]
    if fails:
        lines += ["", "## 오답 분석", ""]
        for c, pred, topic, *_ in fails:
            lines.append(f"- `{c['id']}`: 정답 {c['label']} → 예측 {pred}. 입력: “{' '.join(c['segments'])}”")
    out = ROOT / "eval" / "results" / "detection_results.md"
    out.write_text("\n".join(lines) + "\n")
    print("\n".join(lines[:12]))
    print(f"... 전체 결과: {out}")


if __name__ == "__main__":
    main()
