"""HTTP/WebSocket 통합 테스트 (mock 제공자, 실제 API 호출 없음)."""
import time

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.providers.mock import MockImageProvider, MockSttProvider, MockTextProvider


@pytest.fixture
def client(settings):
    app = create_app(settings, text=MockTextProvider(delay_ms=10), image=MockImageProvider(delay_ms=50),
                     stt_factory=lambda: MockSttProvider(), serve_frontend=False)
    with TestClient(app) as c:
        yield c


def recv_until(ws, pred, limit=200):
    got = []
    for _ in range(limit):
        m = ws.receive_json()
        got.append(m)
        if pred(m):
            return got
    raise AssertionError("event not received")


def test_presenter_audience_flow(client):
    s = client.post("/api/sessions", json={"title": "머신러닝 기초", "audience": "대학 신입생"}).json()
    sid = s["id"]
    with client.websocket_connect(f"/ws/sessions/{sid}?role=presenter") as pres, \
            client.websocket_connect(f"/ws/sessions/{sid}?role=audience") as aud:
        assert pres.receive_json()["type"] == "snapshot"
        snap_a = aud.receive_json()
        assert snap_a["type"] == "snapshot" and "jobs" not in snap_a["data"] and "utterances" not in snap_a["data"]
        client.post(f"/api/sessions/{sid}/input", json={"text": "과적합은 새 데이터에 약한 현상입니다.", "mode": "detect"})
        client.post(f"/api/sessions/{sid}/input",
                    json={"text": "다음 슬라이드에서는 | 과적합을 학생에 비유해 | 설명하겠습니다", "mode": "detect"})
        got = recv_until(pres, lambda m: m["type"] == "job.updated" and m["data"]["status"] == "ready")
        types = {m["type"] for m in got}
        assert {"transcript.final", "detector", "job.updated", "slide.updated"} <= types
        assert all("session_id" in m for m in got)
        assert all(m.get("job_id") for m in got if m["type"] == "job.updated")
        # 청중: 자막/작업/감지 이벤트를 받지 않고, 완성된 장만 받는다
        aud_got = recv_until(aud, lambda m: m["type"] == "slide.updated")
        assert {m["type"] for m in aud_got} <= {"slide.updated", "slide.removed", "session.updated"}
        ready = aud_got[-1]["data"]
        assert ready["status"] == "ready" and ready["image_url"] and "speaker_notes" not in ready
        # 동기화: 발표자가 다음 장으로 이동 → 청중에 session.updated
        r = client.post(f"/api/sessions/{sid}/navigate", json={"direction": "next"}).json()
        upd = recv_until(aud, lambda m: m["type"] == "session.updated")[-1]
        assert upd["data"]["current_slide_id"] == r["current_slide_id"]
        img = client.get(ready["image_url"])
        assert img.status_code == 200 and img.headers["content-type"] == "image/png"
    # 새로고침 후 복원
    snap = client.get(f"/api/sessions/{sid}").json()
    assert len(snap["slides"]) == 2 and snap["session"]["current_slide_id"] == r["current_slide_id"]
    assert len(snap["utterances"]) == 4
    assert client.get("/api/sessions").json()[0]["id"] == sid


def test_image_path_traversal_rejected(client):
    s = client.post("/api/sessions", json={"title": "t", "audience": "a"}).json()
    assert client.get(f"/images/{s['id']}/..%2F..%2Fnextslide.sqlite3").status_code == 404
    assert client.get("/images/../etc/passwd").status_code == 404


def test_config_never_exposes_keys(client, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-secret-value")
    body = client.get("/api/config").text
    assert "sk-test-secret-value" not in body


def test_mic_wrong_format_rejected_and_vad_segments(client):
    s = client.post("/api/sessions", json={"title": "t", "audience": "a"}).json()
    sid = s["id"]
    with client.websocket_connect(f"/ws/sessions/{sid}") as ws:
        ws.receive_json()
        ws.send_json({"type": "mic_start", "sample_rate": 48000, "encoding": "pcm_s16le", "channels": 1})
        m = recv_until(ws, lambda m: m["type"] == "stt.status")[-1]
        assert m["data"]["state"] == "error" and "24000" in m["data"]["message"]
        ws.send_json({"type": "mic_start", "sample_rate": 24000, "encoding": "pcm_s16le", "channels": 1})
        m = recv_until(ws, lambda m: m["type"] == "stt.status")[-1]
        assert m["data"]["state"] == "ready"
        sr = 24000
        silence = np.zeros(int(sr * 0.5), dtype=np.int16)
        t = np.arange(int(sr * 0.8)) / sr
        tone = (3000 * np.sin(2 * np.pi * 220 * t)).astype(np.int16)
        tail = np.zeros(int(sr * 1.0), dtype=np.int16)
        pcm = np.concatenate([silence, tone, tail]).astype("<i2").tobytes()
        step = int(sr * 0.1) * 2
        for i in range(0, len(pcm), step):
            ws.send_bytes(pcm[i:i + step])
        got = recv_until(ws, lambda m: m["type"] == "stt.notice")
        assert any(m["type"] == "stt.vad" and m["data"]["speaking"] for m in got)
        assert "음성 구간 감지됨" in got[-1]["data"]["message"]
        ws.send_bytes(b"\x00\x01\x02")  # 홀수 길이 → 형식 오류로 마이크 중단
        m = recv_until(ws, lambda m: m["type"] == "stt.status" and m["data"]["state"] in ("error",))[-1]
        assert "홀수" in m["data"]["message"]


def test_metrics_endpoint_counts_failures(settings):
    app = create_app(settings, text=MockTextProvider(delay_ms=0), image=MockImageProvider(delay_ms=0, fail_times=1),
                     stt_factory=lambda: MockSttProvider(), serve_frontend=False)
    with TestClient(app) as c:
        sid = c.post("/api/sessions", json={"title": "t", "audience": "a"}).json()["id"]
        c.post(f"/api/sessions/{sid}/input", json={"text": "다음 슬라이드에서는 과적합을 설명하겠습니다", "mode": "force"})
        c.post(f"/api/sessions/{sid}/input", json={"text": "다음 슬라이드에서는 정규화를 설명하겠습니다", "mode": "force"})
        deadline = time.time() + 5
        while time.time() < deadline:
            js = c.get(f"/api/sessions/{sid}").json()["jobs"]
            if all(j["status"] in ("ready", "failed") for j in js):
                break
            time.sleep(0.05)
        m = c.get(f"/api/metrics?session_id={sid}").json()
        assert m["failure_rate"]["failed"] == 1 and m["failure_rate"]["finished"] == 2
        assert m["durations_ms"]["confirm_to_ready_ms"]["n"] == 1
        assert m["speech_end_not_computable_jobs"] == 2
        assert m["usage"]["cost_estimate_usd"] is None  # mock 은 비용 추정하지 않음
