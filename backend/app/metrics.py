"""지연 지표 요약과 비용 추정.

시간 기준:
- 서버 구간은 모두 같은 프로세스의 time.monotonic() 차이로 계산한다(밀리초).
- client_render_ms 는 브라우저 performance.now() 차이(브라우저 단일 시계)로만 계산한다. 서버·브라우저 시계를 섞지 않는다.
- '실제 발화 종료' 시각은 알 수 없다. 음성 경로에서는 서버 VAD 가 추정한 발화 종료(마지막 유성 프레임 도착 시각)를
  별도 이름(vad_*)으로 기록하고, 텍스트 입력 경로에서는 계산 불가(None)로 둔다.
"""
from __future__ import annotations

import statistics
from typing import Iterable, Optional

from .config import Settings
from .providers.base import Usage

DURATION_KEYS = [
    ("vad_speech_end_to_stt_final_ms", "VAD 추정 발화 종료 → 확정 STT 수신"),
    ("stt_final_to_confirm_ms", "확정 STT 수신 → 생성 요청 확정"),
    ("confirm_to_text_ready_ms", "요청 확정 → 슬라이드 기획 완료(텍스트)"),
    ("image_ms", "이미지 생성 소요"),
    ("confirm_to_ready_ms", "요청 확정 → 이미지 포함 준비 완료"),
    ("vad_speech_end_to_ready_ms", "VAD 추정 발화 종료 → 준비 완료"),
    ("client_render_ms", "준비 이벤트 수신 → 브라우저 렌더링 완료"),
]


def percentile(values: list[float], p: float) -> Optional[float]:
    if not values:
        return None
    s = sorted(values)
    if len(s) == 1:
        return s[0]
    k = (len(s) - 1) * p
    f = int(k)
    c = min(f + 1, len(s) - 1)
    return s[f] + (s[c] - s[f]) * (k - f)


def describe(values: list[float]) -> dict:
    if not values:
        return {"n": 0, "mean": None, "median": None, "p95": None, "min": None, "max": None}
    return {
        "n": len(values),
        "mean": round(statistics.fmean(values), 1),
        "median": round(statistics.median(values), 1),
        "p95": round(percentile(values, 0.95), 1),  # type: ignore[arg-type]
        "min": round(min(values), 1),
        "max": round(max(values), 1),
    }


def summarize_jobs(jobs: Iterable[dict], usage_rows: Iterable[dict]) -> dict:
    jobs = list(jobs)
    usage_rows = list(usage_rows)
    counts: dict[str, int] = {}
    for j in jobs:
        counts[j["status"]] = counts.get(j["status"], 0) + 1
    finished = counts.get("ready", 0) + counts.get("failed", 0)
    failure_codes: dict[str, int] = {}
    for j in jobs:
        if j["status"] == "failed":
            failure_codes[j.get("error_code") or "unknown"] = failure_codes.get(j.get("error_code") or "unknown", 0) + 1
    durations = {}
    for key, label in DURATION_KEYS:
        vals = [float(j["metrics"][key]) for j in jobs if isinstance(j.get("metrics"), dict) and j["metrics"].get(key) is not None]
        durations[key] = {"label": label, **describe(vals)}
    # 텍스트 입력 경로에서는 발화 종료 기준 지연을 계산할 수 없음을 명시
    not_computable = sum(1 for j in jobs if j.get("source") != "voice")
    models: dict[str, int] = {}
    for u in usage_rows:
        k = f"{u['kind']}:{u['provider']}:{u['model']}"
        models[k] = models.get(k, 0) + 1
    costs = [u["cost_estimate_usd"] for u in usage_rows if u.get("cost_estimate_usd") is not None]
    return {
        "jobs_total": len(jobs),
        "status_counts": counts,
        "failure_rate": {"failed": counts.get("failed", 0), "finished": finished,
                         "rate": round(counts.get("failed", 0) / finished, 3) if finished else None,
                         "note": "실패율 = failed / (ready + failed). cancelled·needs_input 은 분모에서 제외하고 따로 집계"},
        "failure_codes": failure_codes,
        "durations_ms": durations,
        "speech_end_not_computable_jobs": not_computable,
        "usage": {
            "calls_by_model": models,
            "text_input_tokens": sum(u.get("input_tokens") or 0 for u in usage_rows if u["kind"] == "text"),
            "text_output_tokens": sum(u.get("output_tokens") or 0 for u in usage_rows if u["kind"] == "text"),
            "images": sum(u.get("image_count") or 0 for u in usage_rows if u["kind"] == "image"),
            "stt_audio_seconds": round(sum(u.get("audio_seconds") or 0 for u in usage_rows if u["kind"] == "stt"), 1),
            "ignored_after_cancel": sum(1 for u in usage_rows if u["outcome"].startswith("ignored")),
            "cost_estimate_usd": round(sum(costs), 4) if costs else None,
            "cost_note": "확인된 단가 환경변수 기반 추정치이며 실제 청구액이 아닙니다. 단가 미설정 항목은 합산하지 않습니다.",
            "rows_without_cost": sum(1 for u in usage_rows if u.get("cost_estimate_usd") is None),
        },
    }


def estimate_cost(s: Settings, u: Usage) -> Optional[float]:
    if u.provider == "mock":
        return None
    if u.kind == "text":
        if s.price_text_in_per_mtok is None or s.price_text_out_per_mtok is None:
            return None
        if u.input_tokens is None or u.output_tokens is None:
            return None
        return (u.input_tokens * s.price_text_in_per_mtok + u.output_tokens * s.price_text_out_per_mtok) / 1e6
    if u.kind == "image":
        if s.price_image_text_in_per_mtok is None or s.price_image_out_per_mtok is None:
            return None
        if u.input_tokens is None or u.output_tokens is None:
            return None
        return (u.input_tokens * s.price_image_text_in_per_mtok + u.output_tokens * s.price_image_out_per_mtok) / 1e6
    if u.kind == "stt":
        if s.price_stt_per_min is None or u.audio_seconds is None:
            return None
        return u.audio_seconds / 60 * s.price_stt_per_min
    return None
