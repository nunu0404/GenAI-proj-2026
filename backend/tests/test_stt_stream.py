"""SttStream: 최소 발화 길이(잡음 제거)와 commit 순서 보정 테스트."""
import asyncio

import numpy as np
import pytest

from app.providers.base import SttEvent
from app.stt_stream import SttStream
from conftest import wait_for

SR = 24000


def tone(ms, amp=3000):
    t = np.arange(int(SR * ms / 1000)) / SR
    return (amp * np.sin(2 * np.pi * 220 * t)).astype("<i2").tobytes()


def silence(ms):
    return np.zeros(int(SR * ms / 1000), dtype="<i2").tobytes()


class FakeStt:
    name = "fake"
    model = "fake-stt"
    is_mock = True

    def __init__(self):
        self.sent = bytearray()
        self.commits: list[str] = []
        self.on = None
        self.audio_seconds_sent = 0.0

    async def start(self, on_event):
        self.on = on_event

    async def send_audio(self, pcm):
        self.sent += pcm

    async def commit(self, seg):
        self.commits.append(seg)

    async def close(self):
        pass

    async def final(self, seg, text):
        await self.on(SttEvent("final", segment_id=f"item-{seg}", text=text, local_segment=seg))


async def feed(stream, pcm, chunk_ms=100):
    step = int(SR * chunk_ms / 1000) * 2
    for i in range(0, len(pcm), step):
        await stream.on_audio(pcm[i:i + step])


@pytest.fixture
def stream_factory(make_rt, settings):
    def _make(**overrides):
        for k, v in overrides.items():
            setattr(settings, k, v)
        rt = make_rt()
        fake = FakeStt()
        st = SttStream(rt, fake, settings)
        rt.stt = st
        return rt, st, fake
    return _make


@pytest.mark.asyncio
async def test_short_noise_is_not_sent_or_committed(stream_factory):
    rt, st, fake = stream_factory()
    await st.start()
    await feed(st, silence(200) + tone(20, amp=20000) + silence(800))  # 20ms 큰 잡음 + 침묵
    assert fake.commits == [] and len(fake.sent) == 0
    assert st.discarded_short == 1
    await feed(st, tone(400) + silence(800))  # 실제 발화 길이
    assert fake.commits == ["v1"]
    sent_ms = len(fake.sent) / 2 / SR * 1000
    assert sent_ms >= 400  # 프리롤·후보 구간 보관분까지 전송
    await st.stop()


@pytest.mark.asyncio
async def test_noise_bursts_shorter_than_min_speech_never_reach_stt(stream_factory):
    rt, st, fake = stream_factory(vad_min_speech_ms=250)
    await st.start()
    await feed(st, (tone(40) + silence(760)) * 3)
    assert fake.commits == [] and len(fake.sent) == 0 and st.discarded_short == 3
    await st.stop()


@pytest.mark.asyncio
async def test_out_of_order_finals_are_delivered_in_commit_order(stream_factory):
    rt, st, fake = stream_factory()
    await st.start()
    await rt.handle_final("pre", "과적합은 새 데이터에 약해지는 현상입니다.", "stt")
    await feed(st, tone(400) + silence(800) + tone(400) + silence(800))
    assert fake.commits == ["v1", "v2"]
    await fake.final("v2", "과적합을 시험 문제를 외운 학생에 비유해서 설명하겠습니다.")  # 뒤 구간이 먼저 도착
    await asyncio.sleep(0.05)
    assert rt.db.list_jobs(rt.sid) == []  # 앞 구간을 기다림
    await fake.final("v1", "다음 슬라이드에서는")
    await wait_for(lambda: len(rt.db.list_jobs(rt.sid)) == 1)
    job = rt.db.list_jobs(rt.sid)[0]
    assert job["status"] != "needs_input" and "시험 문제" in job["topic"]
    texts = [u["text"] for u in rt.db.list_utterances(rt.sid)]
    assert texts[-2:] == ["다음 슬라이드에서는", "과적합을 시험 문제를 외운 학생에 비유해서 설명하겠습니다."]
    assert "과적합은 새 데이터" in job["context"]["transcript"]
    await st.stop()


@pytest.mark.asyncio
async def test_failed_head_segment_is_skipped_immediately(stream_factory):
    rt, st, fake = stream_factory()
    await st.start()
    await feed(st, tone(400) + silence(800) + tone(400) + silence(800))
    await fake.final("v2", "다음 슬라이드에서는 정규화를 설명하겠습니다.")
    await fake.on(SttEvent("segment_failed", local_segment="v1"))
    await wait_for(lambda: len(rt.db.list_jobs(rt.sid)) == 1)
    await st.stop()


@pytest.mark.asyncio
async def test_missing_head_times_out_and_late_result_skips_detection(stream_factory):
    rt, st, fake = stream_factory(stt_reorder_timeout_ms=300, stt_result_timeout_ms=5000)
    await st.start()
    await feed(st, tone(400) + silence(800) + tone(400) + silence(800))
    await fake.final("v2", "정규화는 모델을 단순하게 유지합니다.")
    await wait_for(lambda: any(u["text"].startswith("정규화는") for u in rt.db.list_utterances(rt.sid)), timeout=3)
    notices = [e for e in rt.hub.of("stt.notice") if "건너뛰었습니다" in e["data"]["message"]]
    assert notices
    # 건너뛴 앞 구간이 늦게 도착: 기록은 되지만 감지에는 쓰지 않음
    await fake.final("v1", "다음 슬라이드에서는 드롭아웃을 설명하겠습니다.")
    await asyncio.sleep(0.1)
    late = [e for e in rt.hub.of("transcript.final") if e["data"].get("late")]
    assert late and rt.db.list_jobs(rt.sid) == []
    await st.stop()


@pytest.mark.asyncio
async def test_hard_timeout_when_no_result_at_all(stream_factory):
    rt, st, fake = stream_factory(stt_reorder_timeout_ms=5000, stt_result_timeout_ms=300)
    await st.start()
    await feed(st, tone(400) + silence(800))
    await wait_for(lambda: not st._order, timeout=3)
    await st.stop()


@pytest.mark.asyncio
async def test_level_events_for_mic_diagnostics(stream_factory):
    rt, st, fake = stream_factory()
    await st.start()
    await feed(st, silence(400) + tone(400))
    levels = [e["data"] for e in rt.hub.of("stt.level")]
    assert len(levels) >= 3 and levels[0]["rms"] == 0 and max(l["rms"] for l in levels) > rt.s.vad_rms_threshold
    assert levels[0]["threshold"] == rt.s.vad_rms_threshold
    await st.stop()
