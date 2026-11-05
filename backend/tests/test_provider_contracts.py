"""실제 제공자 어댑터의 '계약 테스트' — 공식 문서에 기술된 요청/응답 형식을 흉내 낸 로컬 가짜 서버를 사용한다.

⚠ 실제 API 호출 검증이 아니다. 어댑터가 문서대로 요청을 만들고 응답·오류를 처리하는지만 확인한다.
"""
import asyncio
import base64
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
import websockets

from app.providers import openai_stt
from app.providers.base import ProviderError
from app.providers.mock import render_mock_png

# ------------------------------------------------------------------ Realtime 전사 (WebSocket)

PROXY_VARS = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "WS_PROXY", "WSS_PROXY",
              "http_proxy", "https_proxy", "all_proxy", "ws_proxy", "wss_proxy")


@pytest.fixture(autouse=True)
def _no_proxy_for_local_fakes(monkeypatch):
    """로컬 가짜 서버로 가는 요청이 사용자 환경의 프록시를 타지 않게 한다."""
    for v in PROXY_VARS:
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    monkeypatch.setenv("no_proxy", "127.0.0.1,localhost")


def _ack(update: dict) -> str:
    """문서: session.update 가 적용되면 실제 반영된 설정 전체를 담아 session.updated 를 보낸다."""
    return json.dumps({"type": "session.updated", "session": update["session"]})


async def _start_fake(handler):
    server = await websockets.serve(handler, "127.0.0.1", 0)
    return server, server.sockets[0].getsockname()[1]


def _provider(monkeypatch, port, ack_timeout=2.0):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")
    monkeypatch.setattr(openai_stt, "URL", f"ws://127.0.0.1:{port}/v1/realtime?intent=transcription")
    return openai_stt.OpenAISttProvider("gpt-live-transcribe", ["ko"], "low", 24000, max_reconnects=2,
                                        ack_timeout_s=ack_timeout)


async def _until(pred, timeout=5.0):
    for _ in range(int(timeout / 0.05)):
        if pred():
            return
        await asyncio.sleep(0.05)
    raise AssertionError("timeout")


@pytest.mark.asyncio
async def test_openai_stt_adapter_against_fake_realtime(monkeypatch):
    received: list[dict] = []
    headers_seen: list[str] = []
    conn_count = 0

    async def handler(ws):
        nonlocal conn_count
        conn_count += 1
        headers_seen.append(ws.request.headers.get("Authorization", ""))
        item_no = 0
        async for raw in ws:
            msg = json.loads(raw)
            received.append(msg)
            if msg["type"] == "session.update":
                await ws.send(_ack(msg))
            if msg["type"] == "input_audio_buffer.commit":
                item_no += 1
                item = f"item_{conn_count}_{item_no}"
                await ws.send(json.dumps({"type": "input_audio_buffer.committed", "item_id": item}))
                await ws.send(json.dumps({"type": "conversation.item.input_audio_transcription.delta", "item_id": item, "delta": "다음 "}))
                await ws.send(json.dumps({"type": "conversation.item.input_audio_transcription.delta", "item_id": item, "delta": "슬라이드"}))
                done = {"type": "conversation.item.input_audio_transcription.completed", "item_id": item, "transcript": "다음 슬라이드"}
                await ws.send(json.dumps(done))
                await ws.send(json.dumps(done))  # 중복 완료 이벤트
                if conn_count == 1:
                    await ws.close()  # 연결 끊김 → 재연결 확인

    server, port = await _start_fake(handler)
    events = []

    async def on_event(ev):
        events.append(ev)

    p = _provider(monkeypatch, port)
    await p.start(on_event)
    states = [e.state for e in events if e.type == "status"]
    assert states == ["connecting", "ready"]  # 승인(session.updated) 후에만 ready
    assert p.effective_session["type"] == "transcription"
    await p.send_audio(b"\x01\x00" * 480)
    await p.commit("v1")
    await _until(lambda: [e.state for e in events if e.type == "status"].count("ready") >= 2)
    await p.send_audio(b"\x02\x00" * 480)
    await p.commit("v2")
    await _until(lambda: sum(1 for e in events if e.type == "final") >= 2)
    await p.close()
    server.close()

    su = received[0]
    assert su["type"] == "session.update"
    assert su["session"]["type"] == "transcription"
    inp = su["session"]["audio"]["input"]
    assert inp["format"] == {"type": "audio/pcm", "rate": 24000}
    assert inp["transcription"] == {"model": "gpt-live-transcribe", "languages": ["ko"], "delay": "low"}
    assert "language" not in inp["transcription"]
    assert inp["turn_detection"] is None  # server_vad / semantic_vad 를 보내지 않음
    app = next(m for m in received if m["type"] == "input_audio_buffer.append")
    assert base64.b64decode(app["audio"]) == b"\x01\x00" * 480
    assert headers_seen[0] == "Bearer sk-fake"
    finals = [e for e in events if e.type == "final"]
    assert len(finals) == 2  # 중복 completed 무시
    assert finals[0].local_segment == "v1" and finals[1].local_segment == "v2"
    assert finals[0].segment_id != finals[1].segment_id  # 연결 번호 포함으로 ID 충돌 없음
    partials = [e.text for e in events if e.type == "partial"]
    assert partials[:2] == ["다음 ", "다음 슬라이드"]
    assert any(e.type == "status" and e.state == "reconnecting" for e in events)
    assert conn_count == 2


@pytest.mark.asyncio
async def test_openai_stt_not_ready_without_ack(monkeypatch):
    async def handler(ws):
        async for _ in ws:
            pass  # session.updated 를 보내지 않음

    server, port = await _start_fake(handler)
    events = []

    async def on_event(ev):
        events.append(ev)

    p = _provider(monkeypatch, port, ack_timeout=0.5)
    with pytest.raises(openai_stt.SttSessionError):
        await p.start(on_event)
    states = [e.state for e in events if e.type == "status"]
    assert "ready" not in states and states[-1] == "error"
    assert "session.updated" in events[-1].message
    server.close()


@pytest.mark.asyncio
async def test_openai_stt_rejected_config_is_error(monkeypatch):
    async def handler(ws):
        async for raw in ws:
            if json.loads(raw)["type"] == "session.update":
                await ws.send(json.dumps({"type": "error", "error": {
                    "type": "invalid_request_error", "code": "invalid_value", "message": "Invalid model"}}))

    server, port = await _start_fake(handler)
    events = []

    async def on_event(ev):
        events.append(ev)

    p = _provider(monkeypatch, port)
    with pytest.raises(openai_stt.SttSessionError) as ei:
        await p.start(on_event)
    assert "거부" in str(ei.value) and "Invalid model" in str(ei.value)
    assert [e.state for e in events if e.type == "status"][-1] == "error"
    server.close()


@pytest.mark.asyncio
async def test_openai_stt_mismatched_effective_session_is_error(monkeypatch):
    async def handler(ws):
        async for raw in ws:
            msg = json.loads(raw)
            if msg["type"] == "session.update":
                msg["session"]["audio"]["input"]["turn_detection"] = {"type": "server_vad"}
                await ws.send(_ack(msg))

    server, port = await _start_fake(handler)
    p = _provider(monkeypatch, port)

    async def on_event(ev):
        pass

    with pytest.raises(openai_stt.SttSessionError) as ei:
        await p.start(on_event)
    assert "turn_detection" in str(ei.value)
    server.close()


@pytest.mark.asyncio
async def test_openai_stt_failed_segment_and_lost_on_disconnect(monkeypatch):
    async def handler(ws):
        n = 0
        async for raw in ws:
            msg = json.loads(raw)
            if msg["type"] == "session.update":
                await ws.send(_ack(msg))
            elif msg["type"] == "input_audio_buffer.commit":
                n += 1
                item = f"it{n}"
                await ws.send(json.dumps({"type": "input_audio_buffer.committed", "item_id": item}))
                if n == 1:
                    await ws.send(json.dumps({"type": "conversation.item.input_audio_transcription.failed", "item_id": item,
                                              "error": {"message": "x"}}))
                else:
                    await ws.close()  # 결과 없이 끊김 → 이 구간은 잃음

    server, port = await _start_fake(handler)
    events = []

    async def on_event(ev):
        events.append(ev)

    p = _provider(monkeypatch, port)
    p.max_reconnects = 0
    await p.start(on_event)
    await p.commit("v1")
    await p.commit("v2")
    await _until(lambda: sum(1 for e in events if e.type == "segment_failed") >= 2)
    failed = [e.local_segment for e in events if e.type == "segment_failed"]
    assert failed[:2] == ["v1", "v2"]
    await p.close()
    server.close()


# ------------------------------------------------------------------ HTTP 스텁 (Messages / Images)


class Stub:
    def __init__(self):
        self.requests: list[tuple[str, dict, dict]] = []
        self.responses: list[tuple[int, dict]] = []
        stub = self

        class H(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                stub.requests.append((self.path, {k.lower(): v for k, v in self.headers.items()}, body))
                code, resp = stub.responses.pop(0)
                data = json.dumps(resp).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *a):
                pass

        self.httpd = HTTPServer(("127.0.0.1", 0), H)
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()


@pytest.fixture
def stub():
    s = Stub()
    yield s
    s.close()


def _msg(text, stop="end_turn"):
    return {"id": "msg_1", "type": "message", "role": "assistant", "model": "claude-opus-5-5", "stop_reason": stop,
            "stop_sequence": None, "content": [{"type": "text", "text": text}] if text is not None else [],
            "usage": {"input_tokens": 321, "output_tokens": 123}}


@pytest.mark.asyncio
async def test_anthropic_adapter_request_shape_and_errors(stub, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-fake")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", f"http://127.0.0.1:{stub.port}")
    from app.providers.anthropic_text import AnthropicTextProvider
    p = AnthropicTextProvider("claude-opus-5-5", effort="low", timeout_s=10, use_fallbacks=True)
    stub.responses.append((200, _msg('{"title":"x"}')))
    res = await p.complete_json("SYS", "USER", {"type": "object"})
    path, headers, body = stub.requests[-1]
    assert path.startswith("/v1/messages")
    assert body["model"] == "claude-opus-5-5"
    assert body["output_config"] == {"effort": "low", "format": {"type": "json_schema", "schema": {"type": "object"}}}
    assert body["fallbacks"] == "default"
    assert "server-side-fallback-2026-07-01" in headers.get("anthropic-beta", "")
    assert "thinking" not in body and "temperature" not in body
    assert res.raw_text == '{"title":"x"}' and res.usage.input_tokens == 321 and res.usage.output_tokens == 123
    stub.responses.append((200, _msg(None, stop="refusal")))
    with pytest.raises(ProviderError) as e:
        await p.complete_json("S", "U", {})
    assert e.value.code == "refused" and e.value.usage.input_tokens == 321
    stub.responses.append((401, {"type": "error", "error": {"type": "authentication_error", "message": "bad key"}}))
    with pytest.raises(ProviderError) as e:
        await p.complete_json("S", "U", {})
    assert e.value.code == "auth"


@pytest.mark.asyncio
async def test_openai_image_adapter_request_shape_and_validation(stub, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")
    monkeypatch.setenv("OPENAI_BASE_URL", f"http://127.0.0.1:{stub.port}/v1")
    from app.providers.openai_image import OpenAIImageProvider
    p = OpenAIImageProvider("gpt-image-2", "1536x864", "medium", "png", timeout_s=10, max_bytes=20_000_000)
    good = base64.b64encode(render_mock_png("a", "1536x864")).decode()
    usage = {"input_tokens": 50, "output_tokens": 4000, "total_tokens": 4050,
             "input_tokens_details": {"text_tokens": 50, "image_tokens": 0}}
    stub.responses.append((200, {"created": 1, "data": [{"b64_json": good}], "usage": usage}))
    img = await p.generate("PROMPT")
    path, headers, body = stub.requests[-1]
    assert path == "/v1/images/generations"
    assert body["model"] == "gpt-image-2" and body["size"] == "1536x864" and body["quality"] == "medium"
    assert body["output_format"] == "png" and body["n"] == 1
    assert headers["authorization"] == "Bearer sk-fake"
    assert (img.width, img.height, img.mime) == (1536, 864, "image/png") and img.usage.output_tokens == 4000
    # 이미지 없음
    stub.responses.append((200, {"created": 1, "data": [], "usage": usage}))
    with pytest.raises(ProviderError) as e:
        await p.generate("P")
    assert e.value.code == "no_image" and e.value.usage is not None
    # 잘못된 형식 (텍스트를 base64 로)
    stub.responses.append((200, {"created": 1, "data": [{"b64_json": base64.b64encode(b"<html>" * 400).decode()}]}))
    with pytest.raises(ProviderError) as e:
        await p.generate("P")
    assert e.value.code == "bad_format"
    # 안전 정책 거절
    stub.responses.append((400, {"error": {"message": "Your request was rejected by the safety system.",
                                           "type": "image_generation_user_error", "code": "moderation_blocked"}}))
    with pytest.raises(ProviderError) as e:
        await p.generate("P")
    assert e.value.code == "refused"
    # 서버 오류 → 재시도 가능
    stub.responses.append((503, {"error": {"message": "unavailable", "type": "server_error"}}))
    with pytest.raises(ProviderError) as e:
        await p.generate("P")
    assert e.value.retryable


@pytest.mark.asyncio
async def test_anthropic_haiku_sends_only_supported_options(stub, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-fake")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", f"http://127.0.0.1:{stub.port}")
    from app.providers.anthropic_text import AnthropicTextProvider
    p = AnthropicTextProvider("claude-haiku-5-5", effort="low", timeout_s=10, use_fallbacks=True)
    stub.responses.append((200, _msg('{"title":"x"}')))
    await p.complete_json("SYS", "USER", {"type": "object"})
    path, headers, body = stub.requests[-1]
    assert body["model"] == "claude-haiku-5-5"
    assert "fallbacks" not in body  # Haiku 5.5: 서버 측 fallback 없음
    assert "server-side-fallback" not in headers.get("anthropic-beta", "")
    assert "thinking" not in body and body["output_config"]["effort"] == "low"
    p2 = AnthropicTextProvider("claude-haiku-5-5", effort="low", timeout_s=10, thinking="disabled")
    stub.responses.append((200, _msg('{"title":"x"}')))
    await p2.complete_json("SYS", "USER", {"type": "object"})
    assert stub.requests[-1][2]["thinking"] == {"type": "disabled"}


def test_request_options_reject_invalid_combinations():
    from app.providers.anthropic_text import request_options
    assert request_options("claude-opus-5-5", "low", "disabled", True) == {"fallbacks": True, "thinking": None}
    assert request_options("claude-haiku-5-5", "xhigh", "disabled", True) == {"fallbacks": False, "thinking": None}
    assert request_options("claude-haiku-5-5", "low", "disabled", False)["thinking"] == {"type": "disabled"}
    assert request_options("claude-sonnet-5-5", "low", "", True)["fallbacks"] is True


# ------------------------------------------------------------------ 승인 응답의 실제 설정 검증 (리뷰 2차 지적)


async def _start_with_ack_session(monkeypatch, session_payload, strict=True):
    async def handler(ws):
        async for raw in ws:
            if json.loads(raw)["type"] == "session.update":
                await ws.send(json.dumps({"type": "session.updated", "session": session_payload}))

    server, port = await _start_fake(handler)
    events = []

    async def on_event(ev):
        events.append(ev)

    p = _provider(monkeypatch, port)
    p.strict_session_check = strict
    try:
        await p.start(on_event)
        return p, events, None
    except openai_stt.SttSessionError as e:
        return p, events, e
    finally:
        server.close()


def _good_session():
    return {"type": "transcription", "audio": {"input": {
        "format": {"type": "audio/pcm", "rate": 24000},
        "transcription": {"model": "gpt-live-transcribe", "languages": ["ko"]}, "turn_detection": None}}}


@pytest.mark.asyncio
async def test_empty_ack_session_is_unverifiable(monkeypatch):
    p, events, err = await _start_with_ack_session(monkeypatch, {})
    assert err is not None and err.stage == "unverifiable" and err.server_responded is True
    assert set(p.session_check["missing"]) == {"session.type", "audio.input.transcription.model",
                                               "audio.input.format.type", "audio.input.format.rate"}
    assert "ready" not in [e.state for e in events if e.type == "status"]


@pytest.mark.asyncio
async def test_pcmu_format_in_ack_is_mismatch(monkeypatch):
    sess = _good_session()
    sess["audio"]["input"]["format"] = {"type": "audio/pcmu"}
    p, events, err = await _start_with_ack_session(monkeypatch, sess)
    assert err is not None and err.stage == "mismatch" and "audio/pcmu" in str(err)


@pytest.mark.asyncio
async def test_wrong_session_type_or_model_is_mismatch(monkeypatch):
    sess = _good_session()
    sess["type"] = "realtime"
    sess["audio"]["input"]["transcription"]["model"] = "gpt-transcribe"
    _, _, err = await _start_with_ack_session(monkeypatch, sess)
    assert err is not None and err.stage == "mismatch"
    assert "session.type" in str(err) and "gpt-transcribe" in str(err)


@pytest.mark.asyncio
async def test_full_ack_is_verified_and_non_strict_missing_warns(monkeypatch):
    p, events, err = await _start_with_ack_session(monkeypatch, _good_session())
    assert err is None and len(p.session_check["verified"]) == 5 and not p.session_check["missing"]
    await p.close()
    sess = _good_session()
    del sess["audio"]["input"]["format"]["rate"]
    p, events, err = await _start_with_ack_session(monkeypatch, sess, strict=False)
    assert err is None
    ready = [e for e in events if e.type == "status" and e.state == "ready"][-1]
    assert "미검증 항목" in ready.message and "audio.input.format.rate" in ready.message
    await p.close()


# ------------------------------------------------------------------ 점검 스크립트의 단계 구분 (리뷰 2차 지적)


def _load_check_providers():
    import importlib.util
    from pathlib import Path
    path = Path(__file__).resolve().parents[2] / "eval" / "check_providers.py"
    spec = importlib.util.spec_from_file_location("check_providers", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_outcome_levels():
    cp = _load_check_providers()
    assert cp.outcome(None, False) == {"server_responded": False, "request_accepted": False, "result_valid": False,
                                       "http_status": None}
    assert cp.outcome(429, False)["server_responded"] and not cp.outcome(429, False)["request_accepted"]
    assert cp.outcome(200, False) == {"server_responded": True, "request_accepted": True, "result_valid": False,
                                      "http_status": 200}


@pytest.mark.asyncio
async def test_check_image_does_not_report_errors_as_success(stub, monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")
    monkeypatch.setenv("OPENAI_BASE_URL", f"http://127.0.0.1:{stub.port}/v1")
    cp = _load_check_providers()
    from app.config import Settings
    s = Settings()
    s.image_provider, s.openai_image_model, s.image_size, s.image_format = "openai", "gpt-image-2", "1536x864", "png"
    cases = [
        (429, {"error": {"message": "rate limit", "type": "requests", "code": "rate_limit_exceeded"}}, (True, False, False)),
        (400, {"error": {"message": "Invalid size", "type": "invalid_request_error", "code": "invalid_value"}}, (True, False, False)),
        (503, {"error": {"message": "unavailable", "type": "server_error"}}, (True, False, False)),
        (200, {"created": 1, "data": []}, (True, True, False)),
        (200, {"created": 1, "data": [{"b64_json": base64.b64encode(render_mock_png("a", "1536x864")).decode()}],
               "usage": {"input_tokens": 50, "output_tokens": 3000, "total_tokens": 3050}}, (True, True, True)),
    ]
    for code, body, want in cases:
        stub.responses.append((code, body))
        r = await cp.check_image(s, tmp_path)
        got = (r["server_responded"], r["request_accepted"], r["result_valid"])
        assert got == want, (code, body, r["status"])
        assert r["http_status"] == code
