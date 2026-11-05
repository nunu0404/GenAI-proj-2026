"""실제 제공자 단계별 점검 — 전사만 / 기획만 / 이미지만 따로 실행해 결과를 단계별로 구분해 기록한다.

단계(각 제공자별):
  1. 모델명 문서 확인   : 공식 문서에 있는 이름인지 (사람이 확인, 이 스크립트는 기록만)
  2. 계정 권한·호출 성공 : 실제 API 가 요청을 받아들였는지 (STT 는 session.updated 승인 수신)
  3. 결과 수신         : 전사 텍스트 / 유효한 슬라이드 JSON / 유효한 이미지
  4. 측정             : 소요 시간, 토큰 사용량, 추정 비용(실제 청구액 아님)

사용 예 (backend/.env 에 키 설정 필요, 호출마다 비용 발생):
  backend/.venv/bin/python eval/check_providers.py --stt                     # 연결·설정 승인만 (오디오 미전송)
  backend/.venv/bin/python eval/check_providers.py --stt --wav sample_ko.wav # 한국어 녹음 전사까지
  backend/.venv/bin/python eval/check_providers.py --text
  backend/.venv/bin/python eval/check_providers.py --image --quality low
결과: eval/results/provider_check_<시각>.json (키·개인정보는 저장하지 않음)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
import wave
from datetime import datetime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.config import Settings  # noqa: E402
from app.metrics import estimate_cost  # noqa: E402
from app.planner import compose_image_prompt, plan_slide  # noqa: E402
from app.providers.base import ProviderError, SttEvent  # noqa: E402

CTX = {"lecture_title": "머신러닝 기초", "audience": "대학 신입생",
       "transcript": "과적합은 학습 데이터에 지나치게 맞춰져서 새로운 데이터에는 잘 대응하지 못하는 현상입니다.",
       "current_slide": {"title": "과적합이란?", "bullets": ["학습 데이터에만 맞춘 모델", "새 데이터에서 성능 저하"]}}
REQ = "다음 슬라이드에서는 과적합을 시험 문제를 외운 학생에 비유해서 설명하겠습니다."


def load_wav_24k(path: str) -> bytes:
    with wave.open(path, "rb") as w:
        if w.getsampwidth() != 2:
            raise SystemExit("16-bit PCM WAV 만 지원합니다")
        sr, ch = w.getframerate(), w.getnchannels()
        x = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float32)
    if ch > 1:
        x = x.reshape(-1, ch).mean(axis=1)
    if sr != 24000:  # 점검용 단순 리샘플링 (실서비스 경로는 브라우저 AudioWorklet 의 FIR + 보간)
        n = int(len(x) * 24000 / sr)
        x = np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x)
    return np.clip(x, -32768, 32767).astype("<i2").tobytes()


async def check_stt(s: Settings, wav: str | None) -> dict:
    r: dict = {"provider": "openai", "model": s.openai_stt_model, "account_call_ok": None, "result_ok": None}
    if not os.environ.get("OPENAI_API_KEY"):
        return {**r, "status": "미검증 (OPENAI_API_KEY 없음)"}
    from app.providers.openai_stt import OpenAISttProvider, SttSessionError
    events: list[SttEvent] = []

    async def on(ev):
        events.append(ev)

    p = OpenAISttProvider(s.openai_stt_model, [x.strip() for x in s.stt_languages.split(",")], s.stt_delay,
                          s.stt_sample_rate, 0, s.stt_session_ack_timeout_s)
    t0 = time.monotonic()
    try:
        await p.start(on)
    except SttSessionError as e:
        return {**r, "account_call_ok": False, "status": f"연결/설정 실패: {e}"}
    r.update(account_call_ok=True, ack_ms=round((time.monotonic() - t0) * 1000, 1),
             effective_session=p.effective_session)
    if wav:
        pcm = load_wav_24k(wav)
        step = 2400 * 2
        for i in range(0, len(pcm), step):
            await p.send_audio(pcm[i:i + step])
            await asyncio.sleep(0.02)
        t_commit = time.monotonic()
        await p.commit("check-1")
        while time.monotonic() - t_commit < 20 and not any(e.type in ("final", "segment_failed") for e in events):
            await asyncio.sleep(0.05)
        fin = next((e for e in events if e.type == "final"), None)
        r.update(audio_seconds=round(len(pcm) / 2 / 24000, 2), result_ok=bool(fin and fin.text),
                 transcript=fin.text if fin else None,
                 commit_to_final_ms=round((time.monotonic() - t_commit) * 1000, 1) if fin else None,
                 partial_count=sum(1 for e in events if e.type == "partial"),
                 cost_estimate_usd=(len(pcm) / 2 / 24000 / 60 * s.price_stt_per_min) if s.price_stt_per_min else None)
    await p.close()
    r["status"] = "전사 수신 성공" if r["result_ok"] else ("설정 승인 성공 (오디오 미전송)" if not wav else "전사 결과 없음")
    return r


async def check_text(s: Settings) -> dict:
    r: dict = {"provider": "anthropic", "model": s.anthropic_text_model, "effort": s.text_effort}
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return {**r, "status": "미검증 (ANTHROPIC_API_KEY 없음)"}
    from app.providers.anthropic_text import AnthropicTextProvider
    p = AnthropicTextProvider(s.anthropic_text_model, s.text_effort, s.text_timeout_s, s.text_use_fallbacks,
                              s.text_thinking, s.text_max_tokens)
    t0 = time.monotonic()
    try:
        res = await plan_slide(p, CTX, REQ, s.text_max_repair)
    except Exception as e:  # noqa: BLE001
        return {**r, "account_call_ok": False, "status": f"실패: {getattr(e, 'code', '')} {getattr(e, 'message', e)}"}
    costs = [estimate_cost(s, u) for u in res.usages]
    return {**r, "account_call_ok": True, "result_ok": True, "status": "구조화 슬라이드 수신 성공",
            "latency_ms": round((time.monotonic() - t0) * 1000, 1), "repairs": res.repairs,
            "served_model": res.usages[-1].model, "request_settings": res.usages[-1].settings,
            "input_tokens": sum(u.input_tokens or 0 for u in res.usages),
            "output_tokens": sum(u.output_tokens or 0 for u in res.usages),
            "cost_estimate_usd": sum(costs) if all(c is not None for c in costs) else None,
            "spec": res.spec.model_dump()}


async def check_image(s: Settings, out_dir: Path) -> dict:
    r: dict = {"provider": "openai", "model": s.openai_image_model, "size": s.image_size, "quality": s.image_quality,
               "format": s.image_format}
    if not os.environ.get("OPENAI_API_KEY"):
        return {**r, "status": "미검증 (OPENAI_API_KEY 없음)"}
    from app.providers.openai_image import OpenAIImageProvider
    p = OpenAIImageProvider(s.openai_image_model, s.image_size, s.image_quality, s.image_format, s.image_timeout_s,
                            s.image_max_bytes)
    t0 = time.monotonic()
    try:
        img = await p.generate(compose_image_prompt(
            "A student confidently answering a worksheet they memorized, then puzzled in front of a new, unfamiliar exam sheet"))
    except ProviderError as e:
        return {**r, "account_call_ok": e.code not in ("auth", "network"), "result_ok": False,
                "status": f"실패: {e.code} {e.message}"}
    out_dir.mkdir(parents=True, exist_ok=True)
    f = out_dir / f"image_{s.image_quality}_{datetime.now():%H%M%S}.{img.mime.split('/')[1].replace('jpeg', 'jpg')}"
    f.write_bytes(img.data)
    return {**r, "account_call_ok": True, "result_ok": True, "status": "이미지 수신·검증 성공",
            "latency_ms": round((time.monotonic() - t0) * 1000, 1), "returned_size": f"{img.width}x{img.height}",
            "mime": img.mime, "bytes": len(img.data), "input_tokens": img.usage.input_tokens,
            "output_tokens": img.usage.output_tokens, "cost_estimate_usd": estimate_cost(s, img.usage),
            "file": str(f.relative_to(ROOT))}


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stt", action="store_true")
    ap.add_argument("--wav")
    ap.add_argument("--text", action="store_true")
    ap.add_argument("--image", action="store_true")
    ap.add_argument("--quality", choices=["low", "medium", "high"])
    args = ap.parse_args()
    if not (args.stt or args.text or args.image):
        ap.error("--stt / --text / --image 중 하나 이상을 지정하세요 (각 호출은 비용이 발생할 수 있습니다)")
    s = Settings()
    if args.quality:
        s.image_quality = args.quality
    ts = datetime.now()
    report: dict = {"created": ts.isoformat(timespec="seconds"),
                    "note": "비용은 응답 사용량 × 환경변수 단가로 계산한 추정치이며 실제 청구액이 아님"}
    if args.stt:
        report["stt"] = await check_stt(s, args.wav)
    if args.text:
        report["text"] = await check_text(s)
    if args.image:
        report["image"] = await check_image(s, ROOT / "eval" / "results" / f"provider_check_{ts:%Y%m%d_%H%M%S}")
    for k in ("stt", "text", "image"):
        if k in report:
            v = report[k]
            print(f"[{k}] {v.get('model')}: {v['status']} | 호출 성공={v.get('account_call_ok')} 결과={v.get('result_ok')} "
                  f"| 지연={v.get('latency_ms') or v.get('commit_to_final_ms') or v.get('ack_ms')}ms "
                  f"| 토큰 in/out={v.get('input_tokens')}/{v.get('output_tokens')} | 비용≈{v.get('cost_estimate_usd')}")
    ran_real = any(report[k].get("account_call_ok") is not None for k in ("stt", "text", "image") if k in report)
    if ran_real:
        out = ROOT / "eval" / "results" / f"provider_check_{ts:%Y%m%d_%H%M%S}.json"
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2))
        print("저장:", out)
    else:
        print("실제 호출 없음 (키 미설정) — 결과 파일을 만들지 않았습니다.")


if __name__ == "__main__":
    asyncio.run(main())
