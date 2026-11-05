"""지연·실패 형태 측정: 실제 파이프라인(SessionRuntime → 기획 → 이미지)을 N회 실행한다.

- 텍스트 입력('현재 입력으로 생성') 경로이므로 '발화 종료 → …' 지연은 계산 불가로 기록된다.
- 실패도 제외하지 않고 실패율과 오류 코드를 함께 출력한다.
- 결과는 eval/results/latency_<provider>_<timestamp>.json 에 저장된다.

실행 (실제 API, 비용 발생):
  TEXT_PROVIDER=anthropic IMAGE_PROVIDER=openai backend/.venv/bin/python eval/latency_probe.py -n 5
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.config import Settings  # noqa: E402
from app.db import Database  # noqa: E402
from app.hub import Hub  # noqa: E402
from app.metrics import summarize_jobs  # noqa: E402
from app.providers import make_image_provider, make_text_provider  # noqa: E402
from app.runtime import SessionRuntime  # noqa: E402

SAMPLES = [
    ("과적합은 학습 데이터에 지나치게 맞춰져서 새 데이터에 약해지는 현상입니다.", "다음 슬라이드에서는 과적합을 시험 문제를 외운 학생에 비유해서 설명하겠습니다."),
    ("경사하강법은 손실이 줄어드는 방향으로 조금씩 이동합니다.", "다음 슬라이드에서는 학습률이 너무 크면 어떻게 되는지 산을 내려오는 사람에 비유해 보여주세요."),
    ("표본은 모집단의 일부입니다.", "다음 슬라이드에서는 표본 편향을 국 맛보기에 비유해서 설명하겠습니다."),
    ("세포를 공장에 비유하고 있습니다.", "다음 슬라이드에서는 미토콘드리아를 발전소에 비유해 설명하겠습니다."),
    ("인덱스는 책의 찾아보기와 같습니다.", "다음 슬라이드에서는 인덱스가 너무 많을 때의 단점을 설명하겠습니다."),
]


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("-n", type=int, default=5)
    ap.add_argument("--allow-mock", action="store_true")
    ap.add_argument("--quality", choices=["low", "medium", "high"], help="IMAGE_QUALITY 덮어쓰기 (비교 측정용)")
    ap.add_argument("--text-model", help="ANTHROPIC_TEXT_MODEL 덮어쓰기 (비교 측정용)")
    ap.add_argument("--effort", choices=["low", "medium", "high"], help="TEXT_EFFORT 덮어쓰기")
    args = ap.parse_args()
    s = Settings()
    if args.quality:
        s.image_quality = args.quality
    if args.text_model:
        s.anthropic_text_model = args.text_model
    if args.effort:
        s.text_effort = args.effort
    s.data_dir = Path(tempfile.mkdtemp(prefix="nextslide_probe_"))
    text, image = make_text_provider(s), make_image_provider(s)
    mock = text.is_mock or image.is_mock
    if mock and not args.allow_mock:
        sys.exit("mock 제공자입니다. 실제 측정은 TEXT_PROVIDER/IMAGE_PROVIDER 를 설정하세요 (하네스 점검: --allow-mock).")
    db = Database(s.db_path)
    sess = db.create_session("지연 측정", "대학 신입생")
    rt = SessionRuntime(sess["id"], s, db, Hub(), text, image)
    rt.ensure_started()
    for i in range(args.n):
        ctx_line, req = SAMPLES[i % len(SAMPLES)]
        await rt.handle_final(f"ctx{i}", ctx_line, "simulated")
        r = await rt.manual_input(req, "force")
        jid = r["job_id"]
        while db.get_job(jid)["status"] not in ("ready", "failed", "cancelled", "needs_input"):
            await asyncio.sleep(0.1)
        j = db.get_job(jid)
        m = j["metrics"]
        print(f"[{i+1}/{args.n}] {j['status']} {j.get('error_code') or ''} "
              f"text={m.get('confirm_to_text_ready_ms')}ms image={m.get('image_ms')}ms total={m.get('confirm_to_ready_ms')}ms "
              f"| text tok in/out={m.get('text_input_tokens')}/{m.get('text_output_tokens')} "
              f"img tok in/out={m.get('image_input_tokens')}/{m.get('image_output_tokens')} "
              f"cost≈${(m.get('text_cost_estimate_usd') or 0) + (m.get('image_cost_estimate_usd') or 0):.4f}")
    summary = summarize_jobs(db.list_jobs(sess["id"], limit=1000), db.list_usage(sess["id"]))
    summary["meta"] = {"created": datetime.now().isoformat(timespec="seconds"), "mock": mock, "text_model": text.model,
                       "image_model": image.model, "image_size": s.image_size, "image_quality": s.image_quality,
                       "image_format": s.image_format, "text_effort": s.text_effort, "text_thinking": s.text_thinking or "(생략)",
                       "cost_note": "비용은 응답 토큰 × 환경변수 단가로 계산한 추정치이며 실제 청구액이 아님", "path": "text input (force) — 발화 종료 기준 지연 계산 불가"}
    summary["jobs"] = [{k: j[k] for k in ("status", "error_code", "error_message", "metrics")} for j in db.list_jobs(sess["id"])]
    tag = "mock" if mock else f"{text.model}-{image.model}-{s.image_quality}"
    out = ROOT / "eval" / "results" / f"latency_{tag}_{datetime.now():%Y%m%d_%H%M%S}.json"
    if mock:
        out = Path(s.data_dir) / out.name  # mock 결과는 결과 폴더에 남기지 않는다
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    d = summary["durations_ms"]
    for k in ("confirm_to_text_ready_ms", "image_ms", "confirm_to_ready_ms"):
        print(f"{d[k]['label']}: n={d[k]['n']} mean={d[k]['mean']} median={d[k]['median']} p95={d[k]['p95']}")
    print("실패율:", summary["failure_rate"], "오류:", summary["failure_codes"])
    print("저장:", out, "(MOCK — 실제 성능 아님)" if mock else "")
    await rt.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
