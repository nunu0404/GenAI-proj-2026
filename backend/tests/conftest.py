import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import Settings  # noqa: E402
from app.db import Database  # noqa: E402
from app.hub import Hub  # noqa: E402
from app.providers.mock import MockImageProvider, MockTextProvider  # noqa: E402
from app.runtime import SessionRuntime  # noqa: E402


PROXY_VARS = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "WS_PROXY", "WSS_PROXY",
              "http_proxy", "https_proxy", "all_proxy", "ws_proxy", "wss_proxy")


@pytest.fixture(autouse=True)
def _no_proxy_for_local_fakes(monkeypatch):
    """로컬 가짜 서버로 가는 요청이 사용자 환경의 프록시를 타지 않게 한다."""
    for v in PROXY_VARS:
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    monkeypatch.setenv("no_proxy", "127.0.0.1,localhost")


@pytest.fixture
def settings(tmp_path) -> Settings:
    s = Settings()
    s.data_dir = tmp_path / "data"
    s.stt_provider = s.text_provider = s.image_provider = "mock"
    s.request_silence_ms = 300
    s.max_queue = 3
    s.image_max_retries = 1
    return s


@pytest.fixture
def db(settings):
    d = Database(settings.db_path)
    yield d
    d.close()


class RecordingHub(Hub):
    def __init__(self):
        super().__init__()
        self.events: list[dict] = []

    async def broadcast(self, sid, type_, data, audience_data=None, job_id=None, audience_type=None):
        self.events.append({"type": type_, "data": data, "job_id": job_id, "audience_data": audience_data,
                            "audience_type": audience_type})
        await super().broadcast(sid, type_, data, audience_data, job_id, audience_type)

    def of(self, t):
        return [e for e in self.events if e["type"] == t]


@pytest.fixture
def make_rt(settings, db):
    created = []

    def _make(text=None, image=None, title="머신러닝 기초", audience="대학 신입생"):
        sess = db.create_session(title, audience)
        hub = RecordingHub()
        rt = SessionRuntime(sess["id"], settings, db, hub, text or MockTextProvider(delay_ms=10),
                            image or MockImageProvider(delay_ms=10))
        created.append(rt)
        return rt

    yield _make
    for rt in created:
        for t in (rt._worker, rt._ticker):
            if t:
                t.cancel()


async def wait_for(pred, timeout=5.0, interval=0.02):
    end = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < end:
        if pred():
            return True
        await asyncio.sleep(interval)
    raise AssertionError("timeout waiting for condition")
