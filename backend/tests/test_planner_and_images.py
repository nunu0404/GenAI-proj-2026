import base64
import io
import json

import pytest
from PIL import Image

from app.planner import PlanError, build_user_prompt, compose_image_prompt, plan_slide
from app.providers.base import ProviderError
from app.providers.image_validation import validate_image
from app.providers.mock import MockTextProvider, render_mock_png

GOOD = {
    "title": "과적합: 시험 문제만 외운 학생",
    "bullets": ["기출문제만 외운 학생은 새 문제에 약하다", "모델도 학습 데이터만 외우면 일반화에 실패한다"],
    "visual_intent": "외운 답만 쓰는 학생이 새로운 문제 앞에서 당황하는 모습",
    "image_prompt": "A student confidently answering a familiar worksheet, then puzzled by a new unfamiliar exam sheet",
    "speaker_notes": "학생 비유로 과적합을 설명합니다.",
    "needs_clarification": False, "clarification_reason": None, "precision_warning": None,
}
CTX = {"lecture_title": "머신러닝 기초", "audience": "대학 신입생", "transcript": "과적합은 학습 데이터에 지나치게 맞춰지는 현상입니다.",
       "current_slide": {"title": "머신러닝 기초", "bullets": ["대상: 대학 신입생"]}}


@pytest.mark.asyncio
async def test_valid_output_parses():
    p = MockTextProvider(delay_ms=0, raw_override=[json.dumps(GOOD, ensure_ascii=False)])
    res = await plan_slide(p, CTX, "다음 슬라이드에서는 과적합을 설명하겠습니다", max_repair=1)
    assert res.spec.title.startswith("과적합") and res.repairs == 0 and p.calls == 1


@pytest.mark.asyncio
async def test_invalid_then_valid_repairs_once():
    bad = dict(GOOD, bullets=["하나뿐"])
    p = MockTextProvider(delay_ms=0, raw_override=[json.dumps(bad, ensure_ascii=False), json.dumps(GOOD, ensure_ascii=False)])
    res = await plan_slide(p, CTX, "요청", max_repair=1)
    assert res.repairs == 1 and p.calls == 2


@pytest.mark.asyncio
async def test_repair_is_bounded():
    p = MockTextProvider(delay_ms=0, raw_override=["not json", "{\"title\": 3}", json.dumps(GOOD)])
    with pytest.raises(PlanError) as ei:
        await plan_slide(p, CTX, "요청", max_repair=1)
    assert ei.value.code == "invalid_output"
    assert p.calls == 2  # 1회 + 재요청 1회, 무한 재시도 없음


@pytest.mark.asyncio
async def test_too_many_bullets_locally_truncated():
    many = dict(GOOD, bullets=["a문장", "b문장", "c문장", "d문장"])
    p = MockTextProvider(delay_ms=0, raw_override=[json.dumps(many, ensure_ascii=False)])
    res = await plan_slide(p, CTX, "요청")
    assert len(res.spec.bullets) == 3 and res.local_fixes


@pytest.mark.asyncio
async def test_overlong_title_rejected():
    long = dict(GOOD, title="가" * 41)
    p = MockTextProvider(delay_ms=0, raw_override=[json.dumps(long), json.dumps(long)])
    with pytest.raises(PlanError):
        await plan_slide(p, CTX, "요청", max_repair=1)


@pytest.mark.asyncio
async def test_needs_clarification_output():
    out = {k: "" for k in ("title", "visual_intent", "image_prompt", "speaker_notes")}
    out.update(bullets=[], needs_clarification=True, clarification_reason="무엇을 설명할지 알 수 없습니다", precision_warning=None)
    p = MockTextProvider(delay_ms=0, raw_override=[json.dumps(out, ensure_ascii=False)])
    res = await plan_slide(p, CTX, "다음 슬라이드에서는 그거 설명하겠습니다")
    assert res.spec.needs_clarification


def test_prompt_context_toggle_and_data_tags():
    with_ctx = build_user_prompt(CTX, "요청", include_context=True)
    without = build_user_prompt(CTX, "요청", include_context=False)
    assert "<recent_lecture_transcript>" in with_ctx and "과적합은 학습 데이터" in with_ctx
    assert "<recent_lecture_transcript>" not in without and "과적합은 학습 데이터" not in without
    assert "<next_slide_request>\n요청\n</next_slide_request>" in with_ctx


def test_image_prompt_forbids_text():
    p = compose_image_prompt("a student")
    assert "Do not include any text" in p and "Scene: a student" in p


def _png(w, h):
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (200, 100, 50)).save(buf, "PNG")
    return buf.getvalue()


def test_image_validation():
    data = render_mock_png("x", "1536x864")
    assert validate_image(data, 10_000_000, "1536x864") == ("image/png", 1536, 864)
    with pytest.raises(ProviderError) as e:
        validate_image(b"GIF89a" + b"0" * 2000, 10_000_000)
    assert e.value.code == "bad_format"
    with pytest.raises(ProviderError):
        validate_image(b"", 10_000_000)
    with pytest.raises(ProviderError):  # 비율 불일치 (정사각형 vs 16:9 요청)
        validate_image(_png(1024, 1024), 10_000_000, "1536x864")
    with pytest.raises(ProviderError):  # 크기 초과
        validate_image(data, 1000, None)
    with pytest.raises(ProviderError):  # 매직은 PNG 지만 깨진 데이터
        validate_image(b"\x89PNG\r\n\x1a\n" + b"\x00" * 3000, 10_000_000)
    assert base64  # noqa


def test_repair_json_escaped_latex():
    from app.schemas import EquationItem, SlideSpec, repair_escapes
    B = "\\"
    # 실제 응답에서 관찰된 손상: '\(' 가 NUL+'(' 로, 닫는 쪽은 ')' 로 남음
    assert repair_escapes("위치 \x00(" + B + "theta_t)에서 기울기 \x00(g_t)") == "위치 $" + B + "theta_t$에서 기울기 $g_t$"
    assert repair_escapes("정상 " + B + "(" + B + "hat{y}" + B + ") 유지") == "정상 " + B + "(" + B + "hat{y}" + B + ") 유지"
    e = EquationItem(latex="\theta = \beta \nabla L \frac{1}{n}", caption="\x08eta 설명")
    assert e.latex == B + "theta = " + B + "beta " + B + "nabla L " + B + "frac{1}{n}" and e.caption.startswith(B + "beta")
    s = SlideSpec(title="t", bullets=["학습률 \x00(" + B + "eta)", "둘째"], visual_type="text")
    assert s.bullets[0] == "학습률 $" + B + "eta$"


@pytest.mark.asyncio
async def test_repeated_equations_trigger_one_diversity_retry():
    B = "\\"
    eq = {"latex": B + "theta_{t+1}=" + B + "theta_t-" + B + "eta g_t", "caption": "갱신"}
    base = dict(GOOD, visual_type="equation", image_prompt="", visual_intent="")
    same = json.dumps(dict(base, equations=[eq]), ensure_ascii=False)
    other = json.dumps(dict(base, equations=[{"latex": B + "Delta" + B + "theta=-" + B + "eta g", "caption": "이동량"}]),
                       ensure_ascii=False)
    ctx = dict(CTX, previous_slides=[{"title": "경사하강법 갱신식", "equations": [eq["latex"].replace("=", " = ")]}])
    p = MockTextProvider(delay_ms=0, raw_override=[same, other])
    res = await plan_slide(p, ctx, "다음 슬라이드에서는 수식을 풀어서 설명하겠습니다")
    assert p.calls == 2 and res.diversity_retry and "Delta" in res.spec.equations[0].latex
    # 다시 받아도 같으면 받아들인다 (무한 재시도 없음)
    p2 = MockTextProvider(delay_ms=0, raw_override=[same, same])
    res2 = await plan_slide(p2, ctx, "요청")
    assert p2.calls == 2 and res2.spec.equations[0].latex.startswith(B + "theta")
    # 앞 장과 다르면 재요청 없음
    p3 = MockTextProvider(delay_ms=0, raw_override=[other])
    assert (await plan_slide(p3, ctx, "요청")).diversity_retry is False and p3.calls == 1


@pytest.mark.asyncio
async def test_placeholder_symbol_triggers_repair():
    bad = dict(GOOD, bullets=["학습률 $[?]$를 곱합니다.", "둘째 문장"])
    p = MockTextProvider(delay_ms=0, raw_override=[json.dumps(bad, ensure_ascii=False), json.dumps(GOOD, ensure_ascii=False)])
    res = await plan_slide(p, CTX, "요청", max_repair=1)
    assert res.repairs == 1 and p.calls == 2 and "[?]" not in "".join(res.spec.bullets)
