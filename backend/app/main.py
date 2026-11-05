"""NextSlide FastAPI 앱."""
from __future__ import annotations

import json
import logging
import re
from contextlib import asynccontextmanager
from typing import Callable, Optional

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import BACKEND_DIR, Settings, settings as default_settings
from .db import Database
from .hub import Hub
from .metrics import summarize_jobs
from .providers import make_image_provider, make_stt_provider, make_text_provider
from .providers.base import ImageProvider, SttProvider, TextProvider
from .runtime import Registry
from .schemas import (ClarifyInput, ManualInput, NavigateInput, RenderMetric, SessionCreate, SessionPatch, SlideEdit)
from .stt_stream import AudioFormatError, SttStream, validate_mic_start

log = logging.getLogger("nextslide")
if not logging.getLogger().handlers:  # uvicorn 아래에서도 앱 로그(INFO)가 보이도록
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(name)s %(message)s")
logging.getLogger("nextslide").setLevel(logging.INFO)
FNAME_RE = re.compile(r"^[A-Za-z0-9_\-]+\.(png|jpg|webp)$")
SID_RE = re.compile(r"^ses_[0-9a-f]{12}$")


def create_app(s: Optional[Settings] = None, text: Optional[TextProvider] = None, image: Optional[ImageProvider] = None,
               stt_factory: Optional[Callable[[], SttProvider]] = None, serve_frontend: bool = True) -> FastAPI:
    s = s or default_settings
    state: dict = {}

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        db = Database(s.db_path)
        n = db.mark_interrupted_jobs()
        if n:
            log.warning("서버 재시작: 중단된 작업 %d개를 failed(interrupted) 로 표시", n)
        for p in s.credential_problems():
            log.warning("설정 문제: %s", p)
        hub = Hub()
        reg = Registry(s, db, hub, text or make_text_provider(s), image or make_image_provider(s))
        state.update(db=db, hub=hub, reg=reg, stt_factory=stt_factory or (lambda: make_stt_provider(s)))
        log.info("providers: %s", json.dumps(s.public_info()["mock"]))
        yield
        await reg.shutdown()
        db.close()

    app = FastAPI(title="NextSlide", lifespan=lifespan)
    app.state.ns = state

    def rt_or_404(sid: str):
        rt = state["reg"].get(sid)
        if rt is None:
            raise HTTPException(404, "세션을 찾을 수 없습니다")
        return rt

    def ok_or_400(res: dict) -> dict:
        if not res.get("ok", True):
            raise HTTPException(409 if res.get("error") != "not_found" else 404, res.get("error"))
        return res

    # ---------------- REST ----------------
    @app.get("/api/config")
    def get_config():
        return {**s.public_info(), "credential_problems": s.credential_problems()}

    @app.get("/api/sessions")
    def list_sessions():
        return state["db"].list_sessions()

    @app.post("/api/sessions")
    def create_session(body: SessionCreate):
        return state["db"].create_session(body.title.strip(), body.audience.strip())

    @app.get("/api/sessions/{sid}")
    def get_session(sid: str, role: str = Query("presenter", pattern="^(presenter|audience)$")):
        return rt_or_404(sid).snapshot(role)

    @app.patch("/api/sessions/{sid}")
    async def patch_session(sid: str, body: SessionPatch):
        rt = rt_or_404(sid)
        fields = body.model_dump(exclude_none=True)
        state["db"].update_session(sid, **fields)
        await rt.emit_session()
        return state["db"].get_session(sid)

    @app.post("/api/sessions/{sid}/input")
    async def manual_input(sid: str, body: ManualInput):
        return await rt_or_404(sid).manual_input(body.text, body.mode)

    @app.post("/api/sessions/{sid}/jobs/{jid}/cancel")
    async def cancel_job(sid: str, jid: str):
        return ok_or_400(await rt_or_404(sid).cancel(jid))

    @app.post("/api/sessions/{sid}/jobs/{jid}/retry")
    async def retry_job(sid: str, jid: str):
        return ok_or_400(await rt_or_404(sid).retry(jid))

    @app.post("/api/sessions/{sid}/jobs/{jid}/clarify")
    async def clarify_job(sid: str, jid: str, body: ClarifyInput):
        return ok_or_400(await rt_or_404(sid).clarify(jid, body.text))

    @app.post("/api/sessions/{sid}/jobs/{jid}/dismiss")
    async def dismiss_job(sid: str, jid: str):
        return ok_or_400(await rt_or_404(sid).dismiss(jid))

    @app.patch("/api/sessions/{sid}/slides/{slide_id}")
    async def edit_slide(sid: str, slide_id: str, body: SlideEdit):
        return ok_or_400(await rt_or_404(sid).edit_slide(slide_id, body))

    @app.post("/api/sessions/{sid}/slides/{slide_id}/finalize-without-image")
    async def finalize_without_image(sid: str, slide_id: str):
        return ok_or_400(await rt_or_404(sid).finalize_without_image(slide_id))

    @app.post("/api/sessions/{sid}/navigate")
    async def navigate(sid: str, body: NavigateInput):
        return ok_or_400(await rt_or_404(sid).navigate(body.slide_id, body.direction))

    @app.post("/api/sessions/{sid}/metrics/render")
    async def render_metric(sid: str, body: RenderMetric):
        await rt_or_404(sid).record_render(body.job_id, body.render_ms)
        return {"ok": True}

    @app.get("/api/metrics")
    def metrics(session_id: Optional[str] = None):
        db = state["db"]
        return summarize_jobs(db.list_jobs(session_id, limit=100000), db.list_usage(session_id))

    @app.get("/images/{sid}/{fname}")
    def get_image(sid: str, fname: str):
        if not SID_RE.match(sid) or not FNAME_RE.match(fname):
            raise HTTPException(404)
        p = (s.image_dir / sid / fname).resolve()
        if s.image_dir.resolve() not in p.parents or not p.is_file():
            raise HTTPException(404)
        return FileResponse(p, headers={"Cache-Control": "public, max-age=31536000, immutable"})

    # ---------------- WebSocket ----------------
    @app.websocket("/ws/sessions/{sid}")
    async def ws_session(ws: WebSocket, sid: str, role: str = "presenter"):
        rt = state["reg"].get(sid)
        if rt is None or role not in ("presenter", "audience"):
            await ws.close(code=4404)
            return
        await ws.accept()
        hub = state["hub"]
        await hub.add(sid, ws, role)
        rt.ensure_started()
        await hub.send(ws, {"type": "snapshot", "session_id": sid, "data": rt.snapshot(role)})
        my_stream: Optional[SttStream] = None
        try:
            while True:
                msg = await ws.receive()
                if msg.get("type") == "websocket.disconnect":
                    break
                if role == "audience":
                    continue
                if msg.get("bytes") is not None:
                    if my_stream is None or not my_stream.active:
                        continue
                    try:
                        await my_stream.on_audio(msg["bytes"])
                    except AudioFormatError as e:
                        await hub.send(ws, {"type": "stt.status", "session_id": sid,
                                            "data": {"state": "error", "message": str(e)}})
                        await my_stream.stop()
                        my_stream = None
                        rt.stt = None
                    continue
                try:
                    data = json.loads(msg.get("text") or "{}")
                except json.JSONDecodeError:
                    continue
                t = data.get("type")
                if t == "mic_start":
                    log.info("mic_start sid=%s sample_rate=%s input_rate=%s stt=%s", sid, data.get("sample_rate"),
                             data.get("input_rate"), s.stt_provider)
                    try:
                        validate_mic_start(data, s)
                    except AudioFormatError as e:
                        await hub.send(ws, {"type": "stt.status", "session_id": sid,
                                            "data": {"state": "error", "message": str(e)}})
                        continue
                    if rt.stt is not None:
                        await rt.stt.stop()
                    my_stream = SttStream(rt, state["stt_factory"](), s)
                    rt.stt = my_stream
                    try:
                        await my_stream.start()
                    except Exception as e:  # noqa: BLE001
                        from .providers.base import SttSessionError
                        reason = str(e) if isinstance(e, SttSessionError) else type(e).__name__
                        log.warning("STT start failed: %s", reason)
                        await hub.send(ws, {"type": "stt.status", "session_id": sid, "data": {
                            "state": "error", "message": f"STT 연결 실패: {reason}. 텍스트 입력으로 계속할 수 있습니다."}})
                        my_stream.active = False
                        my_stream = None
                        rt.stt = None
                elif t == "mic_stop":
                    log.info("mic_stop sid=%s frames=%s segments=%s discarded_short=%s", sid,
                             getattr(my_stream, "frames_in", None), getattr(my_stream, "committed", None),
                             getattr(my_stream, "discarded_short", None))
                    if my_stream is not None:
                        await my_stream.stop()
                        if rt.stt is my_stream:
                            rt.stt = None
                        my_stream = None
                elif t == "ping":
                    await hub.send(ws, {"type": "pong", "session_id": sid, "data": {}})
        except WebSocketDisconnect:
            pass
        finally:
            await hub.remove(sid, ws)
            if my_stream is not None:
                await my_stream.stop()
                if rt.stt is my_stream:
                    rt.stt = None

    # ---------------- 빌드된 프런트엔드 ----------------
    dist = BACKEND_DIR.parent / "frontend" / "dist"
    if serve_frontend and dist.is_dir():
        app.mount("/", StaticFiles(directory=dist, html=True), name="frontend")
    return app


app = create_app()
