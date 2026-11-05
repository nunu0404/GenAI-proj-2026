"""세션 런타임: 발화 → 요청 감지 → 작업 대기열 → 기획 → 이미지 → 슬라이드.

동시성 원칙
- 세션마다 작업자 1개가 작업 하나만 실행한다. 대기열(실행 중 제외)은 최대 settings.max_queue 개.
- STT/자막 처리는 작업자와 별개 경로(WebSocket 수신 루프)로 처리되므로 생성 중에도 계속된다.
- 취소: 외부 호출을 강제로 끊지 않고 결과를 버린다(사용량은 ignored_cancelled 로 기록).
- 늦게 도착한 결과는 DB 에서 (job 상태, attempt) 를 확인한 뒤에만 슬라이드에 반영한다.
"""
from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Any, Awaitable, Optional

from .config import Settings
from .db import Database
from .detector import DetectorEvent, RequestDetector, clean_topic
from .hub import Hub, serialize_job, serialize_slide
from .metrics import estimate_cost
from .planner import PlanError, PlanResult, compose_image_prompt, plan_slide
from .providers.base import ImageProvider, ImageResult, ProviderError, TextProvider, Usage
from .providers.image_validation import EXT
from .schemas import JobStatus, SlideEdit

log = logging.getLogger("nextslide.runtime")

REASON_TEXT = {
    "topic_unclear": "주제가 불분명합니다 (예: '이거', '아까 말한 거'). 다룰 주제를 입력해 주세요.",
    "topic_missing": "생성 요청은 들었지만 주제가 인식되지 않았습니다.",
    "cut_off": "요청이 중간에 끊긴 것 같습니다. 주제를 확인해 주세요.",
    "no_request_expression": "생성 요청 표현 없이 문장이 끝났습니다. 슬라이드를 만들지 확인해 주세요.",
}
IGNORED_TEXT = {"negated": "부정 지시로 판단해 생성하지 않음", "quoted": "인용된 지시로 판단해 생성하지 않음"}


class JobCancelled(Exception):
    pass


class SessionRuntime:
    def __init__(self, sid: str, settings: Settings, db: Database, hub: Hub, text: TextProvider, image: ImageProvider):
        self.sid = sid
        self.s = settings
        self.db = db
        self.hub = hub
        self.text = text
        self.image = image
        self.detector = RequestDetector(silence_s=settings.request_silence_ms / 1000)
        self.waiting: list[str] = []
        self.running: Optional[str] = None
        self.cancel_events: dict[str, asyncio.Event] = {}
        self.timings: dict[str, dict[str, float]] = {}
        self.seg_speech_end: dict[str, float] = {}
        self.seg_source: dict[str, str] = {}
        self._wake = asyncio.Event()
        self._worker: Optional[asyncio.Task] = None
        self._ticker: Optional[asyncio.Task] = None
        self._manual_counter = 0
        self.stt = None  # SttStream (presenter 마이크, 세션당 1개)

    # ------------------------------------------------------------ lifecycle
    def ensure_started(self) -> None:
        if self._worker is None or self._worker.done():
            self._worker = asyncio.create_task(self._worker_loop())
        if self._ticker is None or self._ticker.done():
            self._ticker = asyncio.create_task(self._tick_loop())

    async def shutdown(self) -> None:
        for t in (self._worker, self._ticker):
            if t:
                t.cancel()
        if self.stt:
            await self.stt.stop()

    async def _tick_loop(self) -> None:
        while True:
            await asyncio.sleep(0.25)
            try:
                evs = self.detector.tick(time.monotonic())
                if evs:
                    await self._on_detector_events(evs)
            except Exception:  # noqa: BLE001
                log.exception("tick failed")

    # ------------------------------------------------------------ emit helpers
    async def emit_job(self, jid: str) -> None:
        j = self.db.get_job(jid)
        if j:
            await self.hub.broadcast(self.sid, "job.updated", serialize_job(j), job_id=jid)

    async def emit_slide(self, slide_id: str) -> None:
        sl = self.db.get_slide(slide_id)
        if not sl:
            return
        if sl["status"] == JobStatus.cancelled.value:
            await self.hub.broadcast(self.sid, "slide.removed", {"slide_id": slide_id}, {"slide_id": slide_id},
                                     job_id=sl.get("job_id"))
            return
        aud = serialize_slide(sl, audience=True) if sl["status"] == JobStatus.ready.value else None
        if aud is None:
            # 발표자에게는 진행 상태를, 청중에게는 '없음'(미완성 장 비노출)을 보낸다
            await self.hub.broadcast(self.sid, "slide.updated", serialize_slide(sl), {"slide_id": slide_id},
                                     job_id=sl.get("job_id"), audience_type="slide.removed")
        else:
            await self.hub.broadcast(self.sid, "slide.updated", serialize_slide(sl), aud, job_id=sl.get("job_id"))

    async def emit_session(self) -> None:
        s = self.db.get_session(self.sid)
        if s:
            await self.hub.broadcast(self.sid, "session.updated", s,
                                     {"id": s["id"], "title": s["title"], "current_slide_id": s["current_slide_id"]})

    def snapshot(self, role: str) -> dict:
        s = self.db.get_session(self.sid)
        slides = self.db.list_slides(self.sid)
        if role == "audience":
            return {
                "session": {"id": s["id"], "title": s["title"], "current_slide_id": s["current_slide_id"]} if s else None,
                "slides": [serialize_slide(x, audience=True) for x in slides if x["status"] == JobStatus.ready.value],
            }
        return {
            "session": s,
            "slides": [serialize_slide(x) for x in slides],
            "jobs": [serialize_job(j) for j in self.db.list_jobs(self.sid, limit=40)],
            "utterances": self.db.list_utterances(self.sid, limit=60),
            "config": self.s.public_info(),
            "credential_problems": self.s.credential_problems(),
            "queue": {"running": self.running, "waiting": list(self.waiting), "max": self.s.max_queue},
            "detector_pending": self.detector.has_pending,
            "mic_active": self.stt is not None and self.stt.active,
        }

    # ------------------------------------------------------------ 발화 입력
    async def handle_partial(self, segment_id: Optional[str], text: str) -> None:
        self.detector.feed_partial(time.monotonic())
        await self.hub.broadcast(self.sid, "transcript.partial", {"segment_id": segment_id, "text": text})

    async def handle_final(self, segment_id: str, text: str, source: str,
                           speech_end_mono: Optional[float] = None, received_mono: Optional[float] = None,
                           feed_detector: bool = True) -> None:
        """확정 발화 처리. received_mono: 확정 결과가 서버에 도착한 시각(순서 보정으로 늦게 전달돼도 실제 수신 시각).
        feed_detector=False: 순서가 어긋나 늦게 온 구간 → 기록·자막에만 반영."""
        self.ensure_started()
        text = (text or "").strip()
        now_mono = received_mono if received_mono is not None else time.monotonic()
        if not text:
            await self.hub.broadcast(self.sid, "transcript.final", {"segment_id": segment_id, "text": "", "empty": True})
            return
        uid = self.db.add_utterance(self.sid, segment_id, text, source, time.time())
        if uid is None:
            return  # 같은 segment_id 의 중복 확정 결과
        self.seg_source[segment_id] = source
        if speech_end_mono is not None:
            self.seg_speech_end[segment_id] = speech_end_mono
        await self.hub.broadcast(self.sid, "transcript.final",
                                 {"segment_id": segment_id, "text": text, "utterance_id": uid, "source": source,
                                  "late": not feed_detector})
        if not feed_detector:
            return
        evs = self.detector.feed_final(segment_id, text, now_mono)
        if evs:
            await self._on_detector_events(evs)

    async def manual_input(self, text: str, mode: str) -> dict:
        """mode=detect: 확정 발화처럼 감지기로 보냄('|' 로 STT 구간 분할). mode=force: 현재 입력으로 바로 생성."""
        self.ensure_started()
        self._manual_counter += 1
        if mode == "force":
            job = await self.submit(request_text=text.strip(), topic=clean_topic(text) or text.strip(), source="manual",
                                    trigger="force", dedupe_key=None, segment_ids=[], t_last=None, context_prefix="")
            return {"accepted": job is not None, "job_id": job["id"] if job else None}
        parts = [p.strip() for p in text.split("|") if p.strip()]
        for i, p in enumerate(parts):
            seg_id = f"sim{int(time.time()*1000)}-{self._manual_counter}-{i}"
            await self.handle_final(seg_id, p, "simulated")
        return {"accepted": True, "segments": len(parts)}

    async def _on_detector_events(self, evs: list[DetectorEvent]) -> None:
        for ev in evs:
            if ev.kind == "candidate":
                await self.hub.broadcast(self.sid, "detector", {"kind": "candidate", "text": ev.text})
            elif ev.kind == "ignored":
                await self.hub.broadcast(self.sid, "detector", {"kind": "ignored", "reason": ev.reason,
                                                                "message": IGNORED_TEXT.get(ev.reason or "", ev.reason),
                                                                "text": ev.text})
            elif ev.kind == "needs_input":
                ctx = self.build_context(ev.segment_ids, ev.context_prefix)
                j = self.db.insert_job(self.sid, request_text=ev.text, topic=ev.topic, source=self._source_of(ev),
                                       trigger=ev.trigger or "completion", dedupe_key=ev.dedupe_key, context=ctx,
                                       status=JobStatus.needs_input.value,
                                       clarification_reason=REASON_TEXT.get(ev.reason or "", ev.reason))
                if j:
                    await self.hub.broadcast(self.sid, "detector", {"kind": "needs_input", "text": ev.text,
                                                                    "reason": ev.reason}, job_id=j["id"])
                    await self.emit_job(j["id"])
            elif ev.kind == "request":
                await self.hub.broadcast(self.sid, "detector", {"kind": "request", "text": ev.text, "topic": ev.topic,
                                                                "trigger": ev.trigger})
                await self.submit(request_text=ev.text, topic=ev.topic, source=self._source_of(ev),
                                  trigger=ev.trigger or "completion", dedupe_key=ev.dedupe_key,
                                  segment_ids=ev.segment_ids, t_last=ev.t_last, context_prefix=ev.context_prefix)

    def _source_of(self, ev: DetectorEvent) -> str:
        srcs = {self.seg_source.get(s, "simulated") for s in ev.segment_ids}
        if srcs == {"stt"}:
            return "voice"
        return "simulated" if "simulated" in srcs else "manual"

    # ------------------------------------------------------------ 맥락 (요청 확정 시점에 고정)
    def build_context(self, segment_ids: list[str], context_prefix: str = "") -> dict:
        until = time.time()
        if segment_ids:
            rows = self.db.recent_utterances(self.sid, 0, None)
            req_rows = [r for r in rows if r["segment_id"] in set(segment_ids)]
            if req_rows:
                until = min(r["received_at"] for r in req_rows)
        since = until - self.s.context_window_s
        rows = self.db.recent_utterances(self.sid, since, until, exclude_segments=segment_ids)
        texts = [r["text"] for r in rows]
        if context_prefix:
            texts.append(context_prefix)
        transcript = " ".join(texts).strip()
        truncated = False
        if len(transcript) > self.s.context_max_chars:
            transcript = "…" + transcript[-self.s.context_max_chars:]
            truncated = True
        sess = self.db.get_session(self.sid) or {}
        cur = self.db.get_slide(sess.get("current_slide_id") or "") if sess.get("current_slide_id") else None
        return {
            "lecture_title": sess.get("title", ""),
            "audience": sess.get("audience", ""),
            "transcript": transcript,
            "transcript_truncated": truncated,
            "utterance_count": len(rows),
            "window_s": self.s.context_window_s,
            "current_slide": {"title": cur["title"], "bullets": cur["bullets"]} if cur else None,
            "frozen_at": time.time(),
        }

    # ------------------------------------------------------------ 대기열
    async def submit(self, *, request_text: str, topic: Optional[str], source: str, trigger: str,
                     dedupe_key: Optional[str], segment_ids: list[str], t_last: Optional[float],
                     context_prefix: str) -> Optional[dict]:
        self.ensure_started()
        if len(self.waiting) >= self.s.max_queue:
            await self.hub.broadcast(self.sid, "queue.rejected", {
                "text": request_text, "reason": f"대기열이 가득 찼습니다 (최대 {self.s.max_queue}개). 요청이 접수되지 않았습니다."})
            return None
        confirmed = time.monotonic()
        ctx = self.build_context(segment_ids, context_prefix)
        metrics: dict[str, Any] = {"source": source, "trigger": trigger}
        if t_last is not None and source in ("voice", "simulated"):
            metrics["stt_final_to_confirm_ms"] = round((confirmed - t_last) * 1000, 1)
        speech_end = self.seg_speech_end.get(segment_ids[-1]) if segment_ids else None
        if speech_end is not None and t_last is not None:
            metrics["vad_speech_end_to_stt_final_ms"] = round((t_last - speech_end) * 1000, 1)
        job = self.db.insert_job(self.sid, request_text=request_text, topic=topic, source=source, trigger=trigger,
                                 dedupe_key=dedupe_key, context=ctx, status=JobStatus.queued.value, metrics=metrics)
        if job is None:
            await self.hub.broadcast(self.sid, "detector", {"kind": "duplicate", "text": request_text})
            return None
        self.timings[job["id"]] = {"confirmed": confirmed, **({"speech_end": speech_end} if speech_end else {})}
        self._enqueue(job["id"])
        await self.emit_job(job["id"])
        return job

    def _enqueue(self, jid: str) -> None:
        self.cancel_events[jid] = asyncio.Event()
        self.waiting.append(jid)
        self._wake.set()

    async def _worker_loop(self) -> None:
        while True:
            await self._wake.wait()
            self._wake.clear()
            while self.waiting:
                jid = self.waiting.pop(0)
                self.running = jid
                try:
                    await self._run_job(jid)
                except Exception as e:  # noqa: BLE001
                    log.exception("job crashed")
                    self.db.update_job(jid, status=JobStatus.failed.value, error_code="internal",
                                       error_message=f"내부 오류: {type(e).__name__}")
                    await self.emit_job(jid)
                finally:
                    self.running = None

    def _is_cancelled(self, jid: str) -> bool:
        ev = self.cancel_events.get(jid)
        if ev is not None and ev.is_set():
            return True
        j = self.db.get_job(jid)
        return j is None or j["status"] == JobStatus.cancelled.value

    def _log_usage(self, jid: Optional[str], u: Usage, outcome: str) -> None:
        self.db.log_usage(session_id=self.sid, job_id=jid, kind=u.kind, provider=u.provider, model=u.model,
                          settings=u.settings, outcome=outcome, input_tokens=u.input_tokens,
                          output_tokens=u.output_tokens, image_count=u.image_count, audio_seconds=u.audio_seconds,
                          cost_estimate_usd=estimate_cost(self.s, u))

    def _log_orphan(self, jid: str, task: asyncio.Task) -> None:
        """취소 후 늦게 끝난 외부 호출: 결과는 버리고 사용량만 기록."""
        try:
            res = task.result()
            usages = res.usages if isinstance(res, PlanResult) else [res.usage] if isinstance(res, ImageResult) else []
        except PlanError as e:
            usages = e.usages
        except ProviderError as e:
            usages = [e.usage] if e.usage else []
        except BaseException:  # noqa: BLE001
            usages = []
        for u in usages:
            self._log_usage(jid, u, "ignored_cancelled")

    async def _guarded(self, jid: str, coro: Awaitable) -> Any:
        task = asyncio.ensure_future(coro)
        cancel_ev = self.cancel_events.setdefault(jid, asyncio.Event())
        waiter = asyncio.ensure_future(cancel_ev.wait())
        done, _ = await asyncio.wait({task, waiter}, return_when=asyncio.FIRST_COMPLETED)
        if task in done:
            waiter.cancel()
            return task.result()
        task.add_done_callback(lambda t: self._log_orphan(jid, t))
        raise JobCancelled()

    async def _fail(self, jid: str, code: str, message: str, slide_id: Optional[str], attempt: int) -> None:
        if self._is_cancelled(jid):
            return
        self.db.update_job(jid, status=JobStatus.failed.value, error_code=code, error_message=message)
        if slide_id:
            # 텍스트 초안은 유지하고 상태만 failed (재시도 가능)
            self.db.update_slide_if_job_attempt(slide_id, jid, attempt, status=JobStatus.failed.value, error=message)
            await self.emit_slide(slide_id)
        await self.emit_job(jid)

    async def _run_job(self, jid: str) -> None:
        job = self.db.get_job(jid)
        if not job or job["status"] != JobStatus.queued.value:
            return
        attempt = job["attempt"] + 1
        self.db.update_job(jid, attempt=attempt, error_code=None, error_message=None)
        tm = self.timings.setdefault(jid, {"confirmed": time.monotonic()})
        slide = self.db.get_slide(job["slide_id"]) if job.get("slide_id") else None

        # ---------------- 1) 기획
        if slide is None or not slide["title"]:
            self.db.update_job(jid, status=JobStatus.planning.value)
            await self.emit_job(jid)
            try:
                plan: PlanResult = await self._guarded(
                    jid, plan_slide(self.text, job["context"], job["request_text"], self.s.text_max_repair))
            except JobCancelled:
                return
            except PlanError as e:
                for u in e.usages:
                    self._log_usage(jid, u, "error")
                await self._fail(jid, e.code, e.message, None, attempt)
                return
            for u in plan.usages:
                self._log_usage(jid, u, "used")
            if self._is_cancelled(jid):
                return
            costs = [estimate_cost(self.s, u) for u in plan.usages]
            self.db.merge_job_metrics(
                jid, planning_repairs=plan.repairs, local_fixes=plan.local_fixes, text_model=self.text.model,
                text_settings=plan.usages[-1].settings if plan.usages else {},
                text_input_tokens=sum(u.input_tokens or 0 for u in plan.usages),
                text_output_tokens=sum(u.output_tokens or 0 for u in plan.usages),
                text_cost_estimate_usd=round(sum(costs), 6) if costs and all(c is not None for c in costs) else None)
            spec = plan.spec
            if spec.needs_clarification:
                self.db.update_job(jid, status=JobStatus.needs_input.value,
                                   clarification_reason=spec.clarification_reason or "모델이 보완을 요청했습니다")
                await self.emit_job(jid)
                return
            slide = self.db.insert_slide(
                self.sid, layout="title_bullets_image", status=JobStatus.text_ready.value, title=spec.title,
                bullets=spec.bullets, job_id=jid, image_alt=spec.visual_intent,
                image_prompt=compose_image_prompt(spec.image_prompt), text_model=self.text.model,
                speaker_notes=spec.speaker_notes, precision_warning=spec.precision_warning)
            self.db.update_job(jid, slide_id=slide["id"], status=JobStatus.text_ready.value)
            self.db.merge_job_metrics(jid, confirm_to_text_ready_ms=round((time.monotonic() - tm["confirmed"]) * 1000, 1))
            await self.emit_slide(slide["id"])
            await self.emit_job(jid)

        slide_id = slide["id"]
        prompt = slide["image_prompt"] or compose_image_prompt(slide["title"])

        # ---------------- 2) 이미지
        self.db.update_job(jid, status=JobStatus.generating_image.value)
        self.db.update_slide_if_job_attempt(slide_id, jid, attempt, status=JobStatus.generating_image.value, error=None)
        await self.emit_slide(slide_id)
        await self.emit_job(jid)
        t_img = time.monotonic()
        tries = 0
        while True:
            try:
                img: ImageResult = await self._guarded(jid, self.image.generate(prompt))
                break
            except JobCancelled:
                return
            except ProviderError as e:
                if e.usage:
                    self._log_usage(jid, e.usage, "error")
                if e.retryable and tries < self.s.image_max_retries and not self._is_cancelled(jid):
                    tries += 1
                    self.db.merge_job_metrics(jid, image_retries=tries)
                    continue
                await self._fail(jid, e.code, e.message, slide_id, attempt)
                return
        if self._is_cancelled(jid):
            self._log_usage(jid, img.usage, "ignored_cancelled")
            return
        path = self._save_image(slide_id, attempt, img)
        ok = self.db.update_slide_if_job_attempt(slide_id, jid, attempt, status=JobStatus.ready.value,
                                                 image_path=str(path), image_model=self.image.model, error=None)
        if not ok:
            self._log_usage(jid, img.usage, "ignored_stale")
            path.unlink(missing_ok=True)
            return
        self._log_usage(jid, img.usage, "used")
        now = time.monotonic()
        img_cost = estimate_cost(self.s, img.usage)
        m: dict[str, Any] = {"image_ms": round((now - t_img) * 1000, 1),
                             "confirm_to_ready_ms": round((now - tm["confirmed"]) * 1000, 1),
                             "image_model": self.image.model, "image_size": f"{img.width}x{img.height}",
                             "image_settings": img.usage.settings, "image_bytes": len(img.data),
                             "image_input_tokens": img.usage.input_tokens, "image_output_tokens": img.usage.output_tokens,
                             "image_cost_estimate_usd": round(img_cost, 6) if img_cost is not None else None}
        if "speech_end" in tm:
            m["vad_speech_end_to_ready_ms"] = round((now - tm["speech_end"]) * 1000, 1)
        self.db.merge_job_metrics(jid, **m)
        self.db.update_job(jid, status=JobStatus.ready.value)
        await self.emit_slide(slide_id)
        await self.emit_job(jid)
        await self._maybe_auto_advance(slide_id)

    def _save_image(self, slide_id: str, attempt: int, img: ImageResult) -> Path:
        d = self.s.image_dir / self.sid
        d.mkdir(parents=True, exist_ok=True)
        p = d / f"{slide_id}_a{attempt}.{EXT[img.mime]}"
        p.write_bytes(img.data)
        return p

    async def _maybe_auto_advance(self, new_slide_id: str) -> None:
        s = self.db.get_session(self.sid)
        if not s or not (s["auto_advance"] and s["presenting"]):
            return
        ready = [x["id"] for x in self.db.list_slides(self.sid) if x["status"] == JobStatus.ready.value]
        if s["current_slide_id"] in ready and new_slide_id in ready:
            if ready.index(new_slide_id) == ready.index(s["current_slide_id"]) + 1:
                self.db.update_session(self.sid, current_slide_id=new_slide_id)
                await self.emit_session()

    # ------------------------------------------------------------ 사용자 조작
    async def cancel(self, jid: str) -> dict:
        job = self.db.get_job(jid)
        if not job or job["session_id"] != self.sid:
            return {"ok": False, "error": "not_found"}
        st = job["status"]
        if st in (JobStatus.ready.value, JobStatus.failed.value, JobStatus.cancelled.value):
            return {"ok": False, "error": f"이미 {st} 상태라 취소할 수 없습니다"}
        if jid in self.waiting:
            self.waiting.remove(jid)
        self.db.update_job(jid, status=JobStatus.cancelled.value)
        ev = self.cancel_events.get(jid)
        if ev:
            ev.set()
        if job.get("slide_id"):
            sl = self.db.get_slide(job["slide_id"])
            if sl and sl["status"] != JobStatus.ready.value:
                self.db.update_slide(sl["id"], status=JobStatus.cancelled.value)
                await self.emit_slide(sl["id"])
        await self.emit_job(jid)
        return {"ok": True}

    async def retry(self, jid: str) -> dict:
        job = self.db.get_job(jid)
        if not job or job["session_id"] != self.sid:
            return {"ok": False, "error": "not_found"}
        if job["status"] != JobStatus.failed.value:
            return {"ok": False, "error": "실패한 작업만 재시도할 수 있습니다"}
        if len(self.waiting) >= self.s.max_queue:
            return {"ok": False, "error": "대기열이 가득 찼습니다"}
        self.ensure_started()
        self.db.update_job(jid, status=JobStatus.queued.value, error_code=None, error_message=None)
        if job.get("slide_id"):
            self.db.update_slide(job["slide_id"], status=JobStatus.queued.value, error=None)
            await self.emit_slide(job["slide_id"])
        self.timings[jid] = {"confirmed": time.monotonic()}
        self.db.merge_job_metrics(jid, retried=True)
        self._enqueue(jid)
        await self.emit_job(jid)
        return {"ok": True}

    async def clarify(self, jid: str, text: str) -> dict:
        job = self.db.get_job(jid)
        if not job or job["session_id"] != self.sid:
            return {"ok": False, "error": "not_found"}
        if job["status"] != JobStatus.needs_input.value:
            return {"ok": False, "error": "입력 보완 상태가 아닙니다"}
        if len(self.waiting) >= self.s.max_queue:
            return {"ok": False, "error": "대기열이 가득 찼습니다"}
        self.ensure_started()
        req = f"{text.strip()}\n(원래 발화: {job['request_text']})"
        self.db.update_job(jid, status=JobStatus.queued.value, request_text=req, topic=text.strip(),
                           clarification_reason=None, source="clarified")
        self.timings[jid] = {"confirmed": time.monotonic()}
        self._enqueue(jid)
        await self.emit_job(jid)
        return {"ok": True}

    async def dismiss(self, jid: str) -> dict:
        job = self.db.get_job(jid)
        if not job or job["status"] != JobStatus.needs_input.value:
            return {"ok": False, "error": "입력 보완 상태의 요청만 무시할 수 있습니다"}
        self.db.update_job(jid, status=JobStatus.cancelled.value)
        await self.emit_job(jid)
        return {"ok": True}

    async def navigate(self, slide_id: Optional[str] = None, direction: Optional[str] = None) -> dict:
        s = self.db.get_session(self.sid)
        ready = [x for x in self.db.list_slides(self.sid) if x["status"] == JobStatus.ready.value]
        ids = [x["id"] for x in ready]
        if not ids:
            return {"ok": False, "error": "표시할 수 있는 슬라이드가 없습니다"}
        cur = s["current_slide_id"] if s and s["current_slide_id"] in ids else ids[0]
        target = cur
        if slide_id:
            if slide_id not in ids:
                return {"ok": False, "error": "준비 완료된 슬라이드만 표시할 수 있습니다"}
            target = slide_id
        elif direction == "next":
            target = ids[min(ids.index(cur) + 1, len(ids) - 1)]
        elif direction == "prev":
            target = ids[max(ids.index(cur) - 1, 0)]
        if target != (s or {}).get("current_slide_id"):
            self.db.update_session(self.sid, current_slide_id=target)
            await self.emit_session()
        return {"ok": True, "current_slide_id": target}

    async def edit_slide(self, slide_id: str, edit: SlideEdit) -> dict:
        sl = self.db.get_slide(slide_id)
        if not sl or sl["session_id"] != self.sid:
            return {"ok": False, "error": "not_found"}
        fields: dict[str, Any] = {}
        if edit.title is not None:
            fields["title"] = edit.title
        if edit.bullets is not None:
            fields["bullets"] = edit.bullets
        if fields:
            self.db.update_slide(slide_id, **fields)
            await self.emit_slide(slide_id)
        return {"ok": True}

    async def finalize_without_image(self, slide_id: str) -> dict:
        sl = self.db.get_slide(slide_id)
        if not sl or sl["session_id"] != self.sid:
            return {"ok": False, "error": "not_found"}
        if sl["status"] != JobStatus.failed.value or not sl["title"]:
            return {"ok": False, "error": "이미지 생성에 실패한 텍스트 초안만 이미지 없이 완료할 수 있습니다"}
        self.db.update_slide(slide_id, status=JobStatus.ready.value, image_path=None, error=None)
        if sl.get("job_id"):
            self.db.merge_job_metrics(sl["job_id"], finalized_without_image=True)
        await self.emit_slide(slide_id)
        return {"ok": True}

    async def record_render(self, jid: str, render_ms: float) -> None:
        j = self.db.get_job(jid)
        if j and j["session_id"] == self.sid and "client_render_ms" not in j["metrics"]:
            self.db.merge_job_metrics(jid, client_render_ms=round(render_ms, 1))


class Registry:
    """세션 ID → 런타임."""

    def __init__(self, settings: Settings, db: Database, hub: Hub, text: TextProvider, image: ImageProvider):
        self.s, self.db, self.hub, self.text, self.image = settings, db, hub, text, image
        self._rt: dict[str, SessionRuntime] = {}

    def get(self, sid: str) -> Optional[SessionRuntime]:
        if sid in self._rt:
            return self._rt[sid]
        if not self.db.get_session(sid):
            return None
        rt = SessionRuntime(sid, self.s, self.db, self.hub, self.text, self.image)
        self._rt[sid] = rt
        return rt

    async def shutdown(self) -> None:
        for rt in self._rt.values():
            await rt.shutdown()
