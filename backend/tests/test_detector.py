"""요청 감지기 단위 테스트 (LLM·네트워크 없음)."""
from app.detector import RequestDetector, topic_is_sufficient


def feed(d, segs, t0=0.0, step=1.0, ids=None):
    evs, t = [], t0
    for i, s in enumerate(segs):
        t += step
        evs += d.feed_final(ids[i] if ids else f"s{t0}-{i}", s, t)
    return evs, t


def kinds(evs, exclude_candidate=True):
    return [e.kind for e in evs if not (exclude_candidate and e.kind == "candidate")]


def test_normal_speech_does_not_generate():
    d = RequestDetector(silence_s=2.5)
    evs, t = feed(d, ["과적합은 학습 데이터에 지나치게 맞춰져서 새로운 데이터에는 잘 대응하지 못하는 현상입니다.",
                      "그래서 검증 데이터가 중요합니다.", "다음 슬라이드를 보시면 그래프가 있습니다.",
                      "자 다음 장으로 넘어가겠습니다."])
    evs += d.tick(t + 10)
    assert kinds(evs) == []


def test_complete_instruction_generates_once():
    d = RequestDetector(silence_s=2.5)
    evs, t = feed(d, ["다음 슬라이드에서는 과적합을 시험 문제를 외운 학생에 비유해서 설명하겠습니다."])
    evs += d.tick(t + 10)
    reqs = [e for e in evs if e.kind == "request"]
    assert len(reqs) == 1
    assert "과적합" in reqs[0].topic and reqs[0].trigger == "completion"


def test_instruction_split_across_stt_segments():
    d = RequestDetector(silence_s=2.5)
    evs, _ = feed(d, ["다음", "슬라이드에서는 과적합을", "시험 문제를 외운 학생에 비유해서", "설명하겠습니다"])
    reqs = [e for e in evs if e.kind == "request"]
    assert len(reqs) == 1
    assert len(reqs[0].segment_ids) >= 3
    assert "시험 문제" in reqs[0].topic


def test_partial_request_waits_until_completion():
    d = RequestDetector(silence_s=2.5)
    evs, t = feed(d, ["다음 슬라이드에서는 과적합을"])
    assert kinds(evs) == []           # 앞부분만 → 기다림
    assert d.has_pending
    evs = d.tick(t + 1.0)             # 침묵 시간 전
    assert kinds(evs) == []
    evs = d.feed_final("x2", "학생에 비유해 설명하겠습니다", t + 1.5)
    assert kinds(evs) == ["request"]


def test_duplicate_final_event_generates_once():
    d = RequestDetector(silence_s=2.5)
    e1 = d.feed_final("item_1", "다음 슬라이드에서는 정규화를 설명하겠습니다.", 1.0)
    e2 = d.feed_final("item_1", "다음 슬라이드에서는 정규화를 설명하겠습니다.", 1.2)
    e3 = d.feed_final("item_1b", "다음 슬라이드에서는 정규화를 설명하겠습니다.", 1.4)  # 재연결로 인한 동일 문장 재전송
    assert kinds(e1) == ["request"] and e2 == [] and e3 == []


def test_same_topic_requested_again_later_is_allowed():
    d = RequestDetector(silence_s=2.5)
    a = d.feed_final("a", "다음 슬라이드에서는 정규화를 설명하겠습니다.", 1.0)
    b = d.feed_final("b", "중간 설명입니다.", 20.0)
    c = d.feed_final("c", "다음 슬라이드에서는 정규화를 설명하겠습니다.", 60.0)
    assert kinds(a) == ["request"] and kinds(b) == [] and kinds(c) == ["request"]


def test_negated_instruction_does_not_generate():
    d = RequestDetector(silence_s=2.5)
    for txt in ["다음 슬라이드는 만들지 마세요.", "다음 슬라이드에서는 과적합을 설명하지 않겠습니다.",
                "슬라이드를 만들지 말고 그냥 말로 설명하겠습니다."]:
        evs, t = feed(d, [txt], t0=hash(txt) % 1000)
        evs += d.tick(t + 10)
        assert "request" not in kinds(evs), txt


def test_quoted_instruction_does_not_generate():
    d = RequestDetector(silence_s=2.5)
    cases = [
        "여러분이 '다음 슬라이드에서는 과적합을 설명하겠습니다'라고 말하면 시스템이 슬라이드를 만듭니다.",
        "예를 들어 다음 슬라이드에서는 과적합을 설명하겠습니다 라고 하면 됩니다.",
    ]
    for i, txt in enumerate(cases):
        evs, t = feed(d, [txt], t0=100.0 * (i + 1))
        evs += d.tick(t + 10)
        assert kinds(evs) == ["ignored"], txt
        assert evs[-1].reason == "quoted"


def test_unclear_topic_needs_input():
    d = RequestDetector(silence_s=2.5)
    evs, _ = feed(d, ["다음 슬라이드에서는 이거 설명하겠습니다."])
    assert kinds(evs) == ["needs_input"]
    evs, _ = feed(d, ["다음 슬라이드에서는 아까 말한 거 설명할게요."], t0=50)
    assert kinds(evs) == ["needs_input"]


def test_cut_off_instruction_needs_input_after_silence():
    d = RequestDetector(silence_s=2.5)
    evs, t = feed(d, ["다음 슬라이드에서는"])
    assert kinds(evs) == []
    evs = d.tick(t + 3.0)
    assert kinds(evs) == ["needs_input"] and evs[0].reason == "cut_off"


def test_silence_confirms_sufficient_noun_topic():
    d = RequestDetector(silence_s=2.5)
    evs, t = feed(d, ["다음 슬라이드에서는 경사하강법"])
    evs = d.tick(t + 3.0)
    assert kinds(evs) == ["request"] and evs[0].trigger == "silence"


def test_partial_results_extend_silence_window():
    d = RequestDetector(silence_s=2.5)
    _, t = feed(d, ["다음 슬라이드에서는 과적합을"])
    d.feed_partial(t + 2.0)  # 아직 말하는 중
    assert kinds(d.tick(t + 3.0)) == []
    assert kinds(d.tick(t + 5.0)) == ["needs_input"]


def test_make_slide_with_topic_form():
    d = RequestDetector(silence_s=2.5)
    evs, _ = feed(d, ["슬라이드를 만들어 주세요.", "주제는 교차 검증입니다."])
    reqs = [e for e in evs if e.kind == "request"]
    assert len(reqs) == 1 and reqs[0].topic == "교차 검증"
    evs, _ = feed(d, ["드롭아웃에 대한 슬라이드를 만들어 주세요."], t0=100)
    assert [e.topic for e in evs if e.kind == "request"] == ["드롭아웃"]


def test_show_form():
    d = RequestDetector(silence_s=2.5)
    evs, _ = feed(d, ["다음 장에는 결정 트리 예시를 보여주세요."])
    assert [e.topic for e in evs if e.kind == "request"] == ["결정 트리 예시"]


def test_context_prefix_is_kept_for_context():
    d = RequestDetector(silence_s=2.5)
    evs = d.feed_final("a", "편향은 단순한 모델의 오차입니다. 다음 슬라이드에서는 분산을 설명하겠습니다.", 1.0)
    assert evs[0].kind == "request"
    assert "편향은 단순한 모델의 오차" in evs[0].context_prefix


def test_topic_sufficiency():
    assert topic_is_sufficient("과적합")
    assert not topic_is_sufficient("이거")
    assert not topic_is_sufficient("그 내용을")
    assert topic_is_sufficient("앞에서 말한 과적합을")


def test_added_expressions_generate():
    cases = {
        "다음으로 경사하강법을 설명하겠습니다.": "경사하강법",
        "그다음으로 정규화를 살펴보겠습니다.": "정규화",
        "경사하강법 슬라이드 부탁해요.": "경사하강법",
        "교차 검증 슬라이드 부탁드립니다.": "교차 검증",
        "자 그럼 이제 경사하강법 슬라이드 하나 만들어 주세요.": "경사하강법",
    }
    for text, topic in cases.items():
        d = RequestDetector(silence_s=2.5)
        evs = d.feed_final("a", text, 1.0) + d.tick(5.0)
        assert [e.topic for e in evs if e.kind == "request"] == [topic], text


def test_loose_next_without_completion_is_silently_ignored():
    for text in ["다음으로 넘어가겠습니다.", "다음으로 중요한 점은 데이터의 양입니다.", "그다음으로 넘어가 볼게요.",
                 "이 방법 다음으로 많이 쓰이는 것은 랜덤 포레스트입니다.", "다음으로 이거 설명할게요.",
                 "다음으로 경사하강법은 설명하지 않겠습니다.", "슬라이드 부탁드린 거 다들 받으셨나요?"]:
        d = RequestDetector(silence_s=2.5)
        evs = d.feed_final("a", text, 1.0) + d.tick(5.0)
        assert [e.kind for e in evs if e.kind != "candidate"] == [], text  # 보완 카드도 띄우지 않음


def test_loose_next_split_across_segments():
    d = RequestDetector(silence_s=2.5)
    evs, _ = feed(d, ["다음으로", "경사하강법을 설명하겠습니다."])
    assert [e.topic for e in evs if e.kind == "request"] == ["경사하강법"]


def test_polite_dorok_forms():
    ok = {"어, 다음 장에서는 우선 오늘 발표에 대한 목차를 설명드리도록 하겠습니다.": "목차",
          "다음 슬라이드에서는 과적합을 설명하도록 하겠습니다.": "과적합",
          "다음으로 정규화를 살펴보도록 하겠습니다.": "정규화",
          "다음 장에서는 활성화 함수에 대해 말씀드리겠습니다.": "활성화 함수"}
    for text, topic in ok.items():
        d = RequestDetector(silence_s=2.5)
        evs = d.feed_final("a", text, 1.0) + d.tick(5.0)
        reqs = [e for e in evs if e.kind == "request"]
        assert len(reqs) == 1 and topic in reqs[0].topic, text
    for text in ["지금부터 머신러닝 기초에 대한 수업을 시작하도록 하겠습니다.", "다음 슬라이드로 넘어가도록 하겠습니다.",
                 "다음 장을 보도록 하겠습니다."]:
        d = RequestDetector(silence_s=2.5)
        evs = d.feed_final("a", text, 1.0) + d.tick(5.0)
        assert [e.kind for e in evs if e.kind != "candidate"] == [], text
