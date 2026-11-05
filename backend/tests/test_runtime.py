"""작업 대기열·실패·취소·동시성·복원 테스트 (mock 제공자 주입)."""
import asyncio
import json

import pytest

from app.db import Database
from app.providers.base import ProviderError
from app.providers.mock import MockImageProvider, MockTextProvider
from conftest import wait_for

REQ = "다음 슬라이드에서는 과적합을 시험 문제를 외운 학생에 비유해서 설명하겠습니다."


def job_status(rt, jid):
    return rt.db.get_job(jid)["status"]


def latest_job(rt):
    jobs = rt.db.list_jobs(rt.sid)
    return jobs[0] if jobs else None


@pytest.mark.asyncio
async def test_request_flow_ready_and_context_frozen(make_rt):
    gate = asyncio.Event()
    rt = make_rt(image=MockImageProvider(delay_ms=0, gate=gate))
    await rt.handle_final("u1", "과적합은 학습 데이터에 지나치게 맞춰지는 현상입니다.", "stt")
    await rt.handle_final("u2", REQ, "stt", speech_end_mono=None)
    job = latest_job(rt)
    assert job is not None and job["source"] == "voice"
    await wait_for(lambda: job_status(rt, job["id"]) == "generating_image")
    # 생성 도중 추가된 발화는 이미 고정된 맥락에 섞이지 않는다
    await rt.handle_final("u3", "이 문장은 요청 이후에 나온 발화입니다.", "stt")
    gate.set()
    await wait_for(lambda: job_status(rt, job["id"]) == "ready")
    ctx = rt.db.get_job(job["id"])["context"]
    assert "과적합은 학습 데이터" in ctx["transcript"]
    assert "요청 이후" not in ctx["transcript"]
    assert ctx["current_slide"]["title"] == "머신러닝 기초"
    slides = rt.db.list_slides(rt.sid)
    assert [s["status"] for s in slides] == ["ready", "ready"]
    assert slides[1]["image_path"] and slides[1]["layout"] == "title_bullets_image"
    # 현재 발표 중인 장은 바뀌지 않음 (자동 전환 OFF 기본)
    assert rt.db.get_session(rt.sid)["current_slide_id"] == slides[0]["id"]
    m = rt.db.get_job(job["id"])["metrics"]
    assert m["confirm_to_text_ready_ms"] >= 0 and m["confirm_to_ready_ms"] >= m["confirm_to_text_ready_ms"]
    # 텍스트가 먼저 준비된 뒤 이미지가 도착 (상태 순서)
    statuses = [e["data"]["status"] for e in rt.hub.of("job.updated") if e["job_id"] == job["id"]]
    assert statuses.index("text_ready") < statuses.index("generating_image") < statuses.index("ready")


@pytest.mark.asyncio
async def test_duplicate_final_events_create_one_job(make_rt):
    rt = make_rt()
    for _ in range(3):
        await rt.handle_final("item_7", REQ, "stt")
    await asyncio.sleep(0.05)
    assert len(rt.db.list_jobs(rt.sid)) == 1


@pytest.mark.asyncio
async def test_image_failure_keeps_existing_slides_and_retry(make_rt):
    rt = make_rt(image=MockImageProvider(delay_ms=0, fail_times=1))
    before = rt.db.list_slides(rt.sid)
    await rt.manual_input(REQ, "force")
    job = latest_job(rt)
    await wait_for(lambda: job_status(rt, job["id"]) == "failed")
    slides = rt.db.list_slides(rt.sid)
    assert slides[0] == before[0]  # 기존 장 그대로
    failed = slides[1]
    assert failed["status"] == "failed" and failed["title"] and not failed["image_path"]  # 텍스트 초안 유지
    assert rt.db.get_session(rt.sid)["current_slide_id"] == before[0]["id"]
    # 실패한 장으로는 이동 불가
    res = await rt.navigate(slide_id=failed["id"])
    assert not res["ok"]
    # 재시도 → 이미지만 다시 생성
    assert (await rt.retry(job["id"]))["ok"]
    await wait_for(lambda: job_status(rt, job["id"]) == "ready")
    assert rt.db.get_slide(failed["id"])["status"] == "ready"
    assert rt.text.calls == 1  # 기획은 다시 하지 않음


@pytest.mark.asyncio
async def test_text_failure_adds_no_slide(make_rt):
    rt = make_rt(text=MockTextProvider(delay_ms=0, fail_times=1))
    await rt.manual_input(REQ, "force")
    job = latest_job(rt)
    await wait_for(lambda: job_status(rt, job["id"]) == "failed")
    assert len(rt.db.list_slides(rt.sid)) == 1
    assert (await rt.retry(job["id"]))["ok"]
    await wait_for(lambda: job_status(rt, job["id"]) == "ready")
    assert len(rt.db.list_slides(rt.sid)) == 2


@pytest.mark.asyncio
async def test_retryable_image_error_is_retried_bounded(make_rt):
    class Flaky(MockImageProvider):
        async def generate(self, prompt):
            self.calls += 1
            raise ProviderError("timeout", "t/o", retryable=True)
    img = Flaky(delay_ms=0)
    rt = make_rt(image=img)
    await rt.manual_input(REQ, "force")
    job = latest_job(rt)
    await wait_for(lambda: job_status(rt, job["id"]) == "failed")
    assert img.calls == 1 + rt.s.image_max_retries
    assert rt.db.get_job(job["id"])["error_code"] == "timeout"


@pytest.mark.asyncio
async def test_cancelled_late_result_is_ignored(make_rt):
    gate = asyncio.Event()
    img = MockImageProvider(delay_ms=0, gate=gate)
    rt = make_rt(image=img)
    await rt.manual_input(REQ, "force")
    job = latest_job(rt)
    await wait_for(lambda: job_status(rt, job["id"]) == "generating_image")
    slide_id = rt.db.get_job(job["id"])["slide_id"]
    assert (await rt.cancel(job["id"]))["ok"]
    # 취소 직후 다음 요청은 바로 진행 가능해야 함 (작업자가 막히지 않음)
    gate2_job = await rt.submit(request_text="다음 슬라이드에서는 정규화를 설명하겠습니다", topic="정규화", source="manual",
                                trigger="force", dedupe_key=None, segment_ids=[], t_last=None, context_prefix="")
    gate.set()  # 늦게 도착하는 첫 결과
    await wait_for(lambda: job_status(rt, gate2_job["id"]) == "ready")
    await asyncio.sleep(0.05)
    assert job_status(rt, job["id"]) == "cancelled"
    s = rt.db.get_slide(slide_id)
    assert s["status"] == "cancelled" and s["image_path"] is None
    assert slide_id not in [x["id"] for x in rt.db.list_slides(rt.sid)]
    outcomes = [u["outcome"] for u in rt.db.list_usage(rt.sid) if u["job_id"] == job["id"]]
    assert "ignored_cancelled" in outcomes  # 이미 발생한 사용량은 기록


@pytest.mark.asyncio
async def test_speech_events_processed_during_generation(make_rt):
    gate = asyncio.Event()
    rt = make_rt(image=MockImageProvider(delay_ms=0, gate=gate))
    await rt.handle_final("a1", REQ, "stt")
    first = latest_job(rt)
    await wait_for(lambda: job_status(rt, first["id"]) == "generating_image")
    # 이미지 생성 중에도 자막·감지 처리
    await rt.handle_partial("p1", "정규화는")
    await rt.handle_final("a2", "정규화는 모델이 너무 복잡해지지 않게 막는 방법입니다.", "stt")
    await rt.handle_final("a3", "다음 슬라이드에서는 정규화를 설명하겠습니다.", "stt")
    assert len(rt.hub.of("transcript.final")) == 3
    assert len(rt.hub.of("transcript.partial")) == 1
    jobs = rt.db.list_jobs(rt.sid)
    assert len(jobs) == 2 and jobs[0]["status"] == "queued"
    gate.set()
    await wait_for(lambda: all(j["status"] == "ready" for j in rt.db.list_jobs(rt.sid)))


@pytest.mark.asyncio
async def test_queue_limit(make_rt):
    gate = asyncio.Event()
    rt = make_rt(image=MockImageProvider(delay_ms=0, gate=gate))
    accepted = []
    for i in range(5):
        r = await rt.manual_input(f"다음 슬라이드에서는 주제{i}번을 설명하겠습니다", "force")
        accepted.append(r["accepted"])
        await asyncio.sleep(0.03)
    # 1개 실행 + 3개 대기 = 4개 접수, 5번째 거부
    assert accepted == [True, True, True, True, False]
    assert len(rt.hub.of("queue.rejected")) == 1
    gate.set()
    await wait_for(lambda: all(j["status"] == "ready" for j in rt.db.list_jobs(rt.sid)), timeout=10)


@pytest.mark.asyncio
async def test_unclear_request_needs_input_then_clarify(make_rt):
    rt = make_rt()
    await rt.handle_final("q1", "다음 슬라이드에서는 이거 설명하겠습니다.", "stt")
    job = latest_job(rt)
    assert job["status"] == "needs_input" and job["clarification_reason"]
    assert rt.waiting == []  # 대기열 미점유
    assert (await rt.clarify(job["id"], "편향과 분산의 트레이드오프"))["ok"]
    await wait_for(lambda: job_status(rt, job["id"]) == "ready")


@pytest.mark.asyncio
async def test_negated_and_quoted_do_not_create_jobs(make_rt):
    rt = make_rt()
    await rt.handle_final("n1", "다음 슬라이드는 만들지 마세요.", "stt")
    await rt.handle_final("n2", "여러분이 '다음 슬라이드에서는 과적합을 설명하겠습니다'라고 말하면 슬라이드가 생깁니다.", "stt")
    await asyncio.sleep(0.4)
    assert rt.db.list_jobs(rt.sid) == []
    reasons = [e["data"].get("reason") for e in rt.hub.of("detector") if e["data"]["kind"] == "ignored"]
    assert reasons == ["negated", "quoted"]


@pytest.mark.asyncio
async def test_model_requests_clarification(make_rt):
    out = {"title": "", "bullets": [], "visual_intent": "", "image_prompt": "", "speaker_notes": "",
           "needs_clarification": True, "clarification_reason": "주제가 모호합니다", "precision_warning": None}
    rt = make_rt(text=MockTextProvider(delay_ms=0, raw_override=[json.dumps(out, ensure_ascii=False)]))
    await rt.manual_input("다음 슬라이드", "force")
    job = latest_job(rt)
    await wait_for(lambda: job_status(rt, job["id"]) == "needs_input")
    assert len(rt.db.list_slides(rt.sid)) == 1


@pytest.mark.asyncio
async def test_auto_advance_only_when_enabled_and_presenting(make_rt):
    rt = make_rt()
    cover = rt.db.get_session(rt.sid)["current_slide_id"]
    await rt.manual_input(REQ, "force")
    await wait_for(lambda: latest_job(rt)["status"] == "ready")
    assert rt.db.get_session(rt.sid)["current_slide_id"] == cover  # 기본 OFF
    rt.db.update_session(rt.sid, auto_advance=True)  # 켜도 발표 중이 아니면 전환 안 함
    await rt.manual_input("다음 슬라이드에서는 정규화를 설명하겠습니다", "force")
    await wait_for(lambda: latest_job(rt)["status"] == "ready")
    assert rt.db.get_session(rt.sid)["current_slide_id"] == cover
    await rt.navigate(direction="next")
    await rt.navigate(direction="next")
    rt.db.update_session(rt.sid, presenting=True)
    await rt.manual_input("다음 슬라이드에서는 드롭아웃을 설명하겠습니다", "force")
    await wait_for(lambda: latest_job(rt)["status"] == "ready")
    newest = rt.db.list_slides(rt.sid)[-1]["id"]
    assert rt.db.get_session(rt.sid)["current_slide_id"] == newest


@pytest.mark.asyncio
async def test_session_restore_marks_interrupted(settings, make_rt):
    gate = asyncio.Event()
    rt = make_rt(image=MockImageProvider(delay_ms=0, gate=gate))
    await rt.manual_input(REQ, "force")
    job = latest_job(rt)
    await wait_for(lambda: job_status(rt, job["id"]) == "generating_image")
    rt._worker.cancel()  # 서버 프로세스 종료를 흉내
    # 새 프로세스: 같은 DB 파일을 다시 연다
    db2 = Database(settings.db_path)
    assert db2.mark_interrupted_jobs() == 1
    j = db2.get_job(job["id"])
    assert j["status"] == "failed" and j["error_code"] == "interrupted"
    slides = db2.list_slides(rt.sid)
    assert len(slides) == 2 and slides[1]["title"]  # 텍스트 초안 보존
    sess = db2.get_session(rt.sid)
    assert sess["title"] == "머신러닝 기초"
    assert db2.list_utterances(rt.sid) is not None
    db2.close()


@pytest.mark.asyncio
async def test_edit_and_navigation(make_rt):
    from app.schemas import SlideEdit
    rt = make_rt()
    await rt.manual_input(REQ, "force")
    await wait_for(lambda: latest_job(rt)["status"] == "ready")
    sl = rt.db.list_slides(rt.sid)[1]
    await rt.edit_slide(sl["id"], SlideEdit(title="새 제목", bullets=["첫 문장", "둘째 문장"]))
    assert rt.db.get_slide(sl["id"])["title"] == "새 제목"
    with pytest.raises(ValueError):
        SlideEdit(title="가" * 41)
    r = await rt.navigate(direction="next")
    assert r["current_slide_id"] == sl["id"]
    r = await rt.navigate(direction="next")  # 끝에서 더 가지 않음
    assert r["current_slide_id"] == sl["id"]
    r = await rt.navigate(direction="prev")
    assert r["current_slide_id"] == rt.db.list_slides(rt.sid)[0]["id"]


@pytest.mark.asyncio
async def test_equation_and_text_slides_skip_image(make_rt):
    img = MockImageProvider(delay_ms=0)
    rt = make_rt(image=img)
    await rt.manual_input("다음 슬라이드에서는 경사하강법 갱신 규칙을 수식으로 보여주세요", "force")
    await wait_for(lambda: latest_job(rt)["status"] == "ready")
    eq = rt.db.list_slides(rt.sid)[-1]
    assert eq["layout"] == "title_bullets_equation" and eq["status"] == "ready" and not eq["image_path"]
    assert eq["equations"] and "\\theta" in eq["equations"][0]["latex"]
    m = latest_job(rt)["metrics"]
    assert m["visual_type"] == "equation" and m["image_skipped"] and m["confirm_to_ready_ms"] == m["confirm_to_text_ready_ms"]
    await rt.manual_input("다음 슬라이드에서는 오늘 수업의 목차를 정리하겠습니다", "force")
    await wait_for(lambda: latest_job(rt)["status"] == "ready")
    tx = rt.db.list_slides(rt.sid)[-1]
    assert tx["layout"] == "title_bullets" and tx["equations"] == []
    assert img.calls == 0  # 이미지 API 호출 없음
    from app.hub import serialize_slide
    assert serialize_slide(eq, audience=True)["equations"] == eq["equations"]
    # 수식 편집
    from app.schemas import SlideEdit
    await rt.edit_slide(eq["id"], SlideEdit(equations=[{"latex": "y = wx + b", "caption": "선형 모델"}]))
    assert rt.db.get_slide(eq["id"])["equations"] == [{"latex": "y = wx + b", "caption": "선형 모델"}]
    with pytest.raises(ValueError):
        SlideEdit(equations=[{"latex": "\\href{http://x}{y}", "caption": ""}])


def test_old_database_is_migrated(tmp_path):
    import sqlite3
    from app.db import SCHEMA
    p = tmp_path / "old.sqlite3"
    con = sqlite3.connect(p)
    con.executescript(SCHEMA.replace("  equations TEXT NOT NULL DEFAULT '[]',\n", ""))
    con.execute("INSERT INTO sessions(id,title,audience,created_at,updated_at) VALUES('ses_000000000001','t','a',0,0)")
    con.execute("INSERT INTO slides(id,session_id,position,layout,status,created_at,updated_at) "
                "VALUES('sld_1','ses_000000000001',0,'cover','ready',0,0)")
    con.commit()
    con.close()
    db = Database(p)
    s = db.list_slides("ses_000000000001")
    assert s[0]["equations"] == [] and s[0]["layout"] == "cover"
    db.close()
