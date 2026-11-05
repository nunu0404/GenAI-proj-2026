"""Gemini Live 전사 어댑터 / OpenAI 텍스트 어댑터 계약 테스트 — 문서 형식을 흉내 낸 로컬 가짜 서버 사용.

⚠ 실제 API 호출 검증이 아니다.
"""
import asyncio
import base64
import json
from urllib.parse import parse_qs, urlparse

import pytest
import websockets

from app.config import Settings
from app.providers import gemini_stt, make_stt_provider
from app.providers.base import ProviderError, SttSessionError
from app.stt_stream import AudioFormatError, validate_mic_start
from test_provider_contracts import Stub  # noqa: F401  (HTTP 스텁 재사용)

KEY = "AIza-test-secret-key-123"


async def _until(pred, timeout=5.0):
    for _ in range(int(timeout / 0.02)):
        if pred():
            return
        await asyncio.sleep(0.02)
    raise AssertionError("timeout")


class FakeGemini:
    """setup → setupComplete, activityEnd 마다 interim → final 을 보낸다."""

    def __init__(self, send_setup_complete=True, reject=None):
        self.conns = 0
        self.msgs: list[list[dict]] = []
        self.paths: list[str] = []
        self.send_setup_complete = send_setup_complete
        self.reject = reject
        self.ws_list = []

    async def handler(self, ws):
        self.conns += 1
        self.paths.append(ws.request.path)
        mine: list[dict] = []
        self.msgs.append(mine)
        self.ws_list.append(ws)
        n = 0
        async for raw in ws:
            m = json.loads(raw)
            mine.append(m)
            if "setup" in m:
                if self.reject:
                    await ws.close(code=1008, reason=self.reject)
                    return
                if self.send_setup_complete:
                    await ws.send(json.dumps({"setupComplete": {}}))
            elif m.get("realtimeInput", {}).get("activityEnd") is not None:
                n += 1
                await ws.send(json.dumps({"serverContent": {"interimInputTranscription": {"text": "다음 슬"}}}))
                await ws.send(json.dumps({"serverContent": {"inputTranscription": {"text": f"구간{self.conns}-{n}"}}}))


async def _serve(fake):
    server = await websockets.serve(fake.handler, "127.0.0.1", 0)
    return server, server.sockets[0].getsockname()[1]


def _prov(monkeypatch, port, **kw):
    monkeypatch.setenv("GEMINI_API_KEY", KEY)
    monkeypatch.setattr(gemini_stt, "ENDPOINT", f"ws://127.0.0.1:{port}/ws/BidiGenerateContent")
    return gemini_stt.GeminiSttProvider("gemini-3.5-transcribe-live", ["ko-KR"], **kw)


@pytest.mark.asyncio
async def test_gemini_setup_audio_activity_and_finals(monkeypatch):
    fake = FakeGemini()
    server, port = await _serve(fake)
    events = []

    async def on(ev):
        events.append(ev)

    p = _prov(monkeypatch, port, ack_timeout_s=2)
    await p.start(on)
    assert [e.state for e in events if e.type == "status"] == ["connecting", "ready"]
    assert parse_qs(urlparse(fake.paths[0]).query)["key"] == [KEY]
    setup = fake.msgs[0][0]["setup"]
    assert setup == {"model": "models/gemini-3.5-transcribe-live",
                     "generationConfig": {"responseModalities": ["TEXT"]},
                     "inputAudioTranscription": {"languageCodes": ["ko-KR"]},
                     "realtimeInputConfig": {"automaticActivityDetection": {"disabled": True}}}
    pcm = b"\x01\x00" * 1600  # 100ms @16k
    await p.send_audio(pcm)
    await p.send_audio(pcm)
    await p.commit("v1")
    await p.send_audio(pcm)
    await p.commit("v2")
    await _until(lambda: sum(1 for e in events if e.type == "final") == 2)
    ri = [m["realtimeInput"] for m in fake.msgs[0][1:]]
    assert "activityStart" in ri[0]
    assert ri[1]["audio"]["mimeType"] == "audio/pcm;rate=16000"
    assert base64.b64decode(ri[1]["audio"]["data"]) == pcm
    assert "activityEnd" in ri[3] and "activityStart" in ri[4]
    finals = [e for e in events if e.type == "final"]
    assert [(f.text, f.local_segment) for f in finals] == [("구간1-1", "v1"), ("구간1-2", "v2")]
    assert any(e.type == "partial" and e.text == "다음 슬" for e in events)
    assert p.ordered_finals is True and p.audio_seconds_sent == pytest.approx(0.3)
    await p.close()
    server.close()


@pytest.mark.asyncio
async def test_gemini_not_ready_without_setup_complete_and_key_not_leaked(monkeypatch):
    fake = FakeGemini(send_setup_complete=False)
    server, port = await _serve(fake)
    events = []

    async def on(ev):
        events.append(ev)

    p = _prov(monkeypatch, port, ack_timeout_s=0.5)
    with pytest.raises(SttSessionError) as ei:
        await p.start(on)
    assert ei.value.stage == "ack_timeout" and "setupComplete" in str(ei.value)
    assert "ready" not in [e.state for e in events if e.type == "status"]
    assert all(KEY not in (e.message or "") for e in events) and KEY not in str(ei.value)
    server.close()


@pytest.mark.asyncio
async def test_gemini_rejected_setup(monkeypatch):
    fake = FakeGemini(reject="models/gemini-3.5-transcribe-live is not found")
    server, port = await _serve(fake)

    async def on(ev):
        pass

    p = _prov(monkeypatch, port, ack_timeout_s=2)
    with pytest.raises(SttSessionError) as ei:
        await p.start(on)
    assert ei.value.stage == "rejected" and "not found" in str(ei.value) and KEY not in str(ei.value)
    server.close()


@pytest.mark.asyncio
async def test_gemini_rotates_session_on_goaway_and_age(monkeypatch):
    fake = FakeGemini()
    server, port = await _serve(fake)
    events = []

    async def on(ev):
        events.append(ev)

    p = _prov(monkeypatch, port, ack_timeout_s=2, rotate_s=3600)
    await p.start(on)
    await p.send_audio(b"\x01\x00" * 1600)
    await p.commit("v1")
    await _until(lambda: sum(1 for e in events if e.type == "final") == 1)
    await fake.ws_list[0].send(json.dumps({"goAway": {"timeLeft": "10s"}}))
    await _until(lambda: p.rotations == 1)
    assert fake.conns == 2
    await p.send_audio(b"\x01\x00" * 1600)
    await p.commit("v2")
    await _until(lambda: sum(1 for e in events if e.type == "final") == 2)
    assert [e.text for e in events if e.type == "final"] == ["구간1-1", "구간2-1"]  # 새 세션으로 이어짐
    # 나이 기준 교체
    p.rotate_s = 0.0
    await p.send_audio(b"\x01\x00" * 1600)
    await p.commit("v3")
    await _until(lambda: p.rotations == 2)
    await p.close()
    server.close()


def test_sample_rate_follows_provider(settings):
    settings.stt_provider = "gemini"
    assert settings.stt_sample_rate == 16000
    with pytest.raises(AudioFormatError):
        validate_mic_start({"sample_rate": 24000, "encoding": "pcm_s16le", "channels": 1}, settings)
    validate_mic_start({"sample_rate": 16000, "encoding": "pcm_s16le", "channels": 1}, settings)
    assert isinstance(make_stt_provider(settings), gemini_stt.GeminiSttProvider)
    settings.stt_provider = "openai"
    assert settings.stt_sample_rate == 24000
    assert Settings().public_info()["stt"]["sample_rate"] in (16000, 24000)


# ------------------------------------------------------------------ OpenAI Responses 텍스트 어댑터


def _resp(text=None, status="completed", refusal=None, incomplete=None):
    content = []
    if text is not None:
        content.append({"type": "output_text", "text": text, "annotations": []})
    if refusal is not None:
        content.append({"type": "refusal", "refusal": refusal})
    return {"id": "resp_1", "object": "response", "created_at": 1, "model": "gpt-6-luna", "status": status,
            "incomplete_details": {"reason": incomplete} if incomplete else None,
            "output": [{"type": "message", "id": "msg_1", "status": "completed", "role": "assistant",
                        "content": content}],
            "parallel_tool_calls": True, "tool_choice": "auto", "tools": [],
            "usage": {"input_tokens": 1200, "output_tokens": 300, "total_tokens": 1500,
                      "input_tokens_details": {"cached_tokens": 0}, "output_tokens_details": {"reasoning_tokens": 0}}}


@pytest.fixture
def http_stub():
    s = Stub()
    yield s
    s.close()


@pytest.mark.asyncio
async def test_openai_text_request_shape_and_errors(http_stub, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")
    monkeypatch.setenv("OPENAI_BASE_URL", f"http://127.0.0.1:{http_stub.port}/v1")
    from app.providers.openai_text import OpenAITextProvider
    p = OpenAITextProvider("gpt-6-luna", reasoning="none", timeout_s=10)
    schema = {"type": "object", "properties": {"title": {"type": "string"}}, "required": ["title"],
              "additionalProperties": False}
    http_stub.responses.append((200, _resp('{"title":"x"}')))
    res = await p.complete_json("SYS", "USER", schema)
    path, headers, body = http_stub.requests[-1]
    assert path == "/v1/responses"
    assert body["model"] == "gpt-6-luna" and body["instructions"] == "SYS" and body["input"] == "USER"
    assert body["text"] == {"format": {"type": "json_schema", "name": "slide_spec", "schema": schema, "strict": True}}
    assert body["reasoning"] == {"effort": "none"} and body["store"] is False
    assert res.raw_text == '{"title":"x"}' and res.usage.input_tokens == 1200 and res.usage.output_tokens == 300
    http_stub.responses.append((200, _resp(refusal="I can't help with that")))
    with pytest.raises(ProviderError) as e:
        await p.complete_json("S", "U", schema)
    assert e.value.code == "refused" and e.value.http_status == 200
    http_stub.responses.append((200, _resp('{"ti', status="incomplete", incomplete="max_output_tokens")))
    with pytest.raises(ProviderError) as e:
        await p.complete_json("S", "U", schema)
    assert e.value.code == "invalid_output" and "max_output_tokens" in e.value.message
    http_stub.responses.append((401, {"error": {"message": "bad key", "type": "invalid_request_error", "code": "invalid_api_key"}}))
    with pytest.raises(ProviderError) as e:
        await p.complete_json("S", "U", schema)
    assert e.value.code == "auth" and e.value.http_status == 401


@pytest.mark.asyncio
async def test_gemini_full_path_through_vad_to_detection(monkeypatch, make_rt, settings):
    """16kHz PCM → 서버 VAD → Gemini 어댑터(가짜 서버) → 순서대로 감지기 → 생성 작업."""
    import numpy as np

    from app.stt_stream import SttStream
    texts = iter(["다음 슬라이드에서는", "과적합을 시험 문제를 외운 학생에 비유해서 설명하겠습니다."])

    class Fake(FakeGemini):
        async def handler(self, ws):
            async for raw in ws:
                m = json.loads(raw)
                if "setup" in m:
                    await ws.send(json.dumps({"setupComplete": {}}))
                elif m.get("realtimeInput", {}).get("activityEnd") is not None:
                    await ws.send(json.dumps({"serverContent": {"inputTranscription": {"text": next(texts)}}}))

    fake = Fake()
    server, port = await _serve(fake)
    settings.stt_provider = "gemini"
    rt = make_rt()
    st = SttStream(rt, _prov(monkeypatch, port, ack_timeout_s=2), settings)
    rt.stt = st
    await st.start()
    sr = 16000

    def tone(ms):
        t = np.arange(int(sr * ms / 1000)) / sr
        return (3000 * np.sin(2 * np.pi * 220 * t)).astype("<i2").tobytes()

    silence = np.zeros(int(sr * 0.8), dtype="<i2").tobytes()
    pcm = tone(400) + silence + tone(400) + silence
    step = sr // 10 * 2
    for i in range(0, len(pcm), step):
        await st.on_audio(pcm[i:i + step])
    await _until(lambda: len(rt.db.list_jobs(rt.sid)) == 1)
    job = rt.db.list_jobs(rt.sid)[0]
    assert job["source"] == "voice" and "시험 문제" in job["topic"]
    assert not st._order  # 순서 보정 대기열을 쓰지 않음 (ordered_finals)
    assert "vad_speech_end_to_stt_final_ms" in job["metrics"]
    await st.stop()
    server.close()
