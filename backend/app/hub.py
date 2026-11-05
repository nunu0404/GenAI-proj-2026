"""세션별 WebSocket 브로드캐스트. 청중(audience) 연결에는 완성된 슬라이드와 현재 장 정보만 보낸다."""
from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, Optional

from fastapi import WebSocket

log = logging.getLogger("nextslide.hub")

AUDIENCE_EVENTS = {"slide.updated", "slide.removed", "session.updated", "snapshot"}


def image_url(slide: dict) -> Optional[str]:
    p = slide.get("image_path")
    if not p:
        return None
    return f"/images/{slide['session_id']}/{os.path.basename(p)}"


def serialize_slide(slide: dict, audience: bool = False) -> dict:
    base = {
        "id": slide["id"],
        "session_id": slide["session_id"],
        "position": slide["position"],
        "layout": slide["layout"],
        "status": slide["status"],
        "title": slide["title"],
        "bullets": slide["bullets"],
        "image_url": image_url(slide),
        "image_alt": slide.get("image_alt") or "",
    }
    if audience:
        return base
    base.update({
        "job_id": slide.get("job_id"),
        "image_prompt": slide.get("image_prompt"),
        "image_model": slide.get("image_model"),
        "text_model": slide.get("text_model"),
        "speaker_notes": slide.get("speaker_notes"),
        "precision_warning": slide.get("precision_warning"),
        "error": slide.get("error"),
        "is_mock": bool((slide.get("text_model") or "").startswith("mock") or (slide.get("image_model") or "").startswith("mock")),
        "updated_at": slide.get("updated_at"),
    })
    return base


def serialize_job(job: dict) -> dict:
    return {k: job.get(k) for k in (
        "id", "session_id", "slide_id", "status", "request_text", "topic", "source", "trigger", "attempt",
        "error_code", "error_message", "clarification_reason", "metrics", "created_at", "updated_at")} | {
        "job_id": job.get("id"),
        "context_preview": {
            "transcript_chars": len((job.get("context") or {}).get("transcript") or ""),
            "current_slide_title": ((job.get("context") or {}).get("current_slide") or {}).get("title"),
        },
    }


class Hub:
    def __init__(self) -> None:
        self._conns: dict[str, list[tuple[WebSocket, str]]] = {}
        self._lock = asyncio.Lock()

    async def add(self, sid: str, ws: WebSocket, role: str) -> None:
        async with self._lock:
            self._conns.setdefault(sid, []).append((ws, role))

    async def remove(self, sid: str, ws: WebSocket) -> None:
        async with self._lock:
            self._conns[sid] = [(w, r) for (w, r) in self._conns.get(sid, []) if w is not ws]

    def count(self, sid: str, role: Optional[str] = None) -> int:
        return len([1 for (_, r) in self._conns.get(sid, []) if role is None or r == role])

    async def send(self, ws: WebSocket, payload: dict) -> None:
        try:
            await ws.send_text(json.dumps(payload, ensure_ascii=False))
        except Exception:  # noqa: BLE001 - 끊긴 연결은 receive 루프에서 정리
            pass

    async def broadcast(self, sid: str, type_: str, data: Optional[dict[str, Any]], audience_data: Optional[dict] = None,
                        job_id: Optional[str] = None, audience_type: Optional[str] = None) -> None:
        """모든 이벤트에 session_id 를 넣고, 작업 관련 이벤트에는 job_id 를 넣는다.
        data=None 이면 발표자에게 보내지 않는다. 청중에게는 허용된 이벤트 타입만 보낸다."""
        payload = None
        if data is not None:
            payload = {"type": type_, "session_id": sid, **({"job_id": job_id} if job_id else {}), "data": data}
        aud_payload = None
        a_type = audience_type or type_
        if a_type in AUDIENCE_EVENTS and audience_data is not None:
            aud_payload = {"type": a_type, "session_id": sid, "data": audience_data}
        for ws, role in list(self._conns.get(sid, [])):
            if role == "audience":
                if aud_payload is not None:
                    await self.send(ws, aud_payload)
            elif payload is not None:
                await self.send(ws, payload)
