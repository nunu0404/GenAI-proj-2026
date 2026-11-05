"""다음 슬라이드 생성 요청 감지기 (규칙 기반, LLM 호출 없음).

- 확정(final) STT 구간을 누적한다. 구간 하나가 문장 전체라고 가정하지 않는다.
- 완료 표현이 나오면 즉시, 없으면 설정한 침묵 시간 뒤에 판단한다.
- 부정 지시 / 인용된 지시 / 단순 장 넘김 발화는 생성하지 않는다.
- 같은 확정 구간(segment_id)이 다시 와도 한 번만 처리한다. 같은 주제를 나중에 다시 요청하는 것은 허용한다.
- 주제가 불충분하면 needs_input 이벤트로 입력 보완을 요청한다.

시간 인자 t 는 호출자가 넘기는 단조 시계(time.monotonic) 값이다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal, Optional

# ---------------------------------------------------------------- 패턴
R_NEXT = re.compile(r"다음\s*(?:슬라이드|장|페이지)\s*(?:에서는|에서|에는|에선|엔|은|는|에|를|을|로|으로)?")
R_MAKE = re.compile(
    r"(?:다음\s*)?슬라이드\s*(?:를|을|도|로)?\s*(?:하나\s*|한\s*장\s*)?"
    r"(?:(?:만들어|생성해|추가해)\s*(?:주세요|줘요|줘|주십시오|주실래요)|부탁\s*(?:해요|합니다|드려요|드립니다|드릴게요|할게요|해))"
)
# 약한 트리거: '(그)다음으로 X 를 설명하겠습니다' — 같은 문장 안에 완료 표현이 있을 때만 생성, 아니면 조용히 무시
R_NEXT_LOOSE = re.compile(r"(?<![가-힣])(?:그\s*)?다음으로\s*")

_STEMS = r"(?:설명|소개|정리|비교|이야기|얘기|요약|정의|시연|예시를\s*들어|예를\s*들어|비유|말씀)"
# '~하도록 하겠습니다 / ~드리도록 하겠습니다' (강의에서 흔한 공손 표현)
_DOROK = r"\s*도록\s*(?:하겠습니다|할게요|하겠어요|할\s*겁니다|합시다)"
R_COMPLETE = re.compile(
    rf"{_STEMS}\s*(?:하겠습니다|할게요|할\s*거예요|할\s*겁니다|합니다|해\s*보겠습니다|해\s*볼게요|드리겠습니다|드릴게요|"
    rf"해\s*드리겠습니다|해\s*드릴게요|해\s*주세요|해\s*줘)"
    rf"|{_STEMS}\s*(?:하|드리|해\s*드리|해\s*보){_DOROK}"
    rf"|(?:다루|살펴보|알아보|보여\s*드리|짚어\s*보|보){_DOROK}"
    # 어미 변형·STT 오인식 허용: '설명들도 하겠습니다', '설명을 좀 하겠습니다', '설명은 드릴게요'
    rf"|{_STEMS}[^\s.?!]{{0,4}}\s*(?:좀\s*)?(?:하겠습니다|할게요|드리겠습니다|드릴게요|해\s*드리겠습니다|하도록\s*하겠습니다)"
    # 구어체 예정 표현: '살펴볼 건데요', '설명할 거예요', '다룰 예정입니다'
    rf"|(?:{_STEMS}\s*(?:할|드릴|해\s*드릴|해\s*볼)|살펴볼|알아볼|다룰|다뤄\s*볼|짚어\s*볼|볼|보여\s*드릴)"
    r"\s*(?:건데요|거예요|겁니다|거거든요|예정입니다|생각입니다)"
    r"|다루겠습니다|다룰게요|다뤄\s*보겠습니다|다뤄\s*볼게요|살펴보겠습니다|살펴볼게요|알아보겠습니다|알아볼게요"
    r"|보여\s*주세요|보여\s*줘요?|보여\s*드리겠습니다|보여\s*드릴게요|보여\s*줄게요|넣어\s*주세요|그려\s*주세요|만들어\s*주세요"
)
# '슬라이드를 만들어 주세요. 주제는 X입니다.'
R_TOPIC_IS = re.compile(
    r"주제\s*(?:는|은)\s*(.+?)\s*(?:입니다|이에요|예요|이요|요|로\s*해\s*주세요|으로\s*해\s*주세요)(?=[\s.!?,]|$)"
)
R_PRE_TOPIC = re.compile(r"([^.?!]{2,60}?)\s*(?:에\s*대한|에\s*관한|관련(?:된)?|을\s*설명하는|를\s*설명하는)\s*$")

R_NEGATION = re.compile(
    r"(?:만들|생성하|생성|보여\s*주|넣|그리|설명하|추가하)\s*지\s*(?:마|말|않)"
    r"|안\s*(?:만들|보여|넣|그려|생성)|하지\s*마|필요\s*없|취소(?:해|할|하겠)|말아\s*주세요|만들\s*필요"
)
# 트리거 바로 뒤에 오면 생성 요청이 아니라 장 넘김/참조 발화로 본다
R_NON_REQUEST_AFTER = re.compile(
    r"^\s*(?:를|을|에서|에)?\s*(?:보시면|보면|보시죠|보세요|보겠습니다|볼게요|봅시다|보시다시피|보도록|볼까요|보기로|볼\s*건데요|볼\s*거예요|넘기|넘어|넘겨|가\s*보|가겠|갈게|"
    r"로\s*넘어|으로\s*넘어|로\s*가|으로\s*가)"
)
# 완료 표현 직후에 오면 '인용'
R_QUOTE_AFTER = re.compile(r"^\s*['\"”’」』]?\s*(?:라고|이라고|라는|란|하고\s*말|고\s*말|고\s*하|라고\s*하|하면|라고들)")
R_QUOTE_BEFORE = re.compile(r"(?:예를\s*들어|예컨대|가령|이를테면|만약)\s*['\"“‘「『]?\s*$")
QUOTE_OPEN = "\"“‘「『'"

DANGLING = re.compile(r"(?:의|와|과|및|그리고|하고|랑|이랑|를|을|에|에서|으로|로|에\s*대해서?|에\s*관해서?|는|은)\s*$")
DECLARATIVE_END = re.compile(r"(?:니다|어요|아요|에요|예요|해요|죠|다)\s*[.!?]?\s*$")

FILLERS = {
    "이거", "그거", "저거", "이것", "그것", "저것", "이", "그", "저", "뭔가", "무언가", "무엇", "어떤", "것", "거", "걸",
    "내용", "부분", "좀", "한번", "그냥", "음", "어", "아", "저기", "뭐", "그런", "이런", "저런", "아까", "방금", "앞에서",
    "말한", "얘기한", "이야기한", "했던", "하던", "지금", "여기", "거기", "이번", "다음", "슬라이드", "장", "주제", "얘기",
    "이야기", "설명", "그림", "something", "자", "그럼", "그러면", "이제", "그리고", "그래서", "일단", "우선",
}
PARTICLE_TAIL = re.compile(
    r"(?:에\s*대해서|에\s*대해|에\s*관해서|에\s*관해|을\s*가지고|를\s*가지고|으로|에서|에게|하고|이랑|까지|부터|"
    r"을|를|은|는|이|가|에|의|도|로|와|과|랑|만)$"
)


def normalize(text: str) -> str:
    text = text.replace(" ", " ")
    return re.sub(r"\s+", " ", text).strip()


def clean_topic(raw: str) -> str:
    t = normalize(raw).strip(" ,.!?\"'“”‘’")
    for _ in range(2):
        t = PARTICLE_TAIL.sub("", t).strip()
    return t


def strip_leading_fillers(text: str, max_tokens: int = 3) -> str:
    """'자 그럼 이제 경사하강법' → '경사하강법'. 직전 문장이 섞이지 않도록 마지막 max_tokens 어절만 남긴다."""
    toks = [t for t in re.split(r"[\s,]+", normalize(text)) if t]
    toks = toks[-max_tokens:]
    while toks and toks[0] in FILLERS:
        toks.pop(0)
    return " ".join(toks)


def topic_is_sufficient(topic: str) -> bool:
    """대명사·지시어·채움말만 있으면 불충분."""
    core_chars = 0
    for tok in re.split(r"[\s,.!?]+", topic):
        if not tok:
            continue
        base = tok
        for _ in range(2):
            base = PARTICLE_TAIL.sub("", base)
        if base in FILLERS or not base:
            continue
        core_chars += len(base)
    return core_chars >= 2


# ---------------------------------------------------------------- 이벤트
EventKind = Literal["candidate", "request", "needs_input", "ignored"]


@dataclass
class DetectorEvent:
    kind: EventKind
    text: str  # 요청 구간 원문
    segment_ids: list[str]
    topic: Optional[str] = None
    reason: Optional[str] = None  # ignored/needs_input 사유
    trigger: Optional[str] = None  # completion | silence
    dedupe_key: Optional[str] = None
    t_first: Optional[float] = None
    t_last: Optional[float] = None
    context_prefix: str = ""  # 요청이 시작된 STT 구간 안에서 트리거 앞에 있던 발화(맥락에 포함)


@dataclass
class _Seg:
    seg_id: str
    text: str
    t: float


@dataclass
class _Outcome:
    kind: EventKind | Literal["pending", "skip"]
    end: int  # J 상의 소비 끝 위치
    topic: Optional[str] = None
    reason: Optional[str] = None
    trigger: Optional[str] = None


@dataclass
class RequestDetector:
    silence_s: float = 2.5
    keep_tail_segments: int = 3
    max_buffer_age_s: float = 40.0
    _buf: list[_Seg] = field(default_factory=list)
    _seen_ids: set[str] = field(default_factory=set)
    _emitted_keys: set[str] = field(default_factory=set)
    _last_final: Optional[tuple[str, float]] = None
    pending_since: Optional[float] = None
    _last_activity: float = 0.0
    _candidate_key: Optional[str] = None

    # ---------------- 입력 ----------------
    def feed_final(self, seg_id: str, text: str, t: float) -> list[DetectorEvent]:
        text = normalize(text)
        if not text:
            return []
        if seg_id in self._seen_ids:
            return []  # 같은 확정 구간 재수신 → 무시
        # 다른 ID 로 같은 문장이 짧은 간격에 다시 오는 경우(재연결 중복 등)
        if self._last_final and self._last_final[0] == text and t - self._last_final[1] < 1.5:
            self._seen_ids.add(seg_id)
            return []
        self._seen_ids.add(seg_id)
        self._last_final = (text, t)
        self._buf.append(_Seg(seg_id, text, t))
        self._last_activity = t
        return self._scan(force=False, now=t)

    def feed_partial(self, t: float) -> None:
        """임시 결과는 생성 판단에 쓰지 않고, 말이 이어지는 중임을 알리는 용도로만 사용."""
        if self.pending_since is not None:
            self._last_activity = t

    def tick(self, now: float) -> list[DetectorEvent]:
        if self.pending_since is not None and now - self._last_activity >= self.silence_s:
            return self._scan(force=True, now=now)
        return []

    @property
    def has_pending(self) -> bool:
        return self.pending_since is not None

    # ---------------- 내부 ----------------
    def _join(self) -> tuple[str, list[tuple[int, int]]]:
        parts, offs, pos = [], [], 0
        for s in self._buf:
            if parts:
                pos += 1
            offs.append((pos, pos + len(s.text)))
            parts.append(s.text)
            pos += len(s.text)
        return " ".join(parts), offs

    def _segs_in(self, offs: list[tuple[int, int]], a: int, b: int) -> list[_Seg]:
        return [self._buf[i] for i, (s, e) in enumerate(offs) if s < max(b, a + 1) and e > a]

    def _key(self, offs: list[tuple[int, int]], a: int, b: int) -> str:
        segs = [i for i, (s, e) in enumerate(offs) if s < max(b, a + 1) and e > a]
        first = segs[0]
        return f"{self._buf[first].seg_id}@{a - offs[first][0]}..{self._buf[segs[-1]].seg_id}"

    def _prefix(self, offs: list[tuple[int, int]], start: int, consumed: int) -> str:
        J, _ = self._join()
        for (a, b) in offs:
            if a <= start < b + 1:
                return J[max(a, consumed):start].strip()
        return ""

    def _find_trigger(self, J: str, p: int) -> Optional[tuple[re.Match, str]]:
        found = [(m, k) for m, k in ((R_MAKE.search(J, p), "make"), (R_NEXT.search(J, p), "next"),
                                     (R_NEXT_LOOSE.search(J, p), "loose")) if m]
        if not found:
            return None
        order = {"make": 0, "next": 1, "loose": 2}
        return min(found, key=lambda x: (x[0].start(), order[x[1]]))

    def _is_quoted_before(self, J: str, start: int) -> bool:
        sent_start = max(J.rfind(".", 0, start), J.rfind("?", 0, start), J.rfind("!", 0, start)) + 1
        before = J[sent_start:start]
        if R_QUOTE_BEFORE.search(before):
            return True
        # 닫히지 않은 따옴표 안
        opens = sum(before.count(c) for c in "“‘「『")
        closes = sum(before.count(c) for c in "”’」』")
        straight = before.count('"')
        return opens > closes or straight % 2 == 1

    def _evaluate(self, J: str, m: re.Match, kind: str, force: bool) -> _Outcome:
        start, tend = m.start(), m.end()
        after = J[tend:]
        quoted_before = self._is_quoted_before(J, start)

        if kind == "next" and R_NON_REQUEST_AFTER.match(after):
            return _Outcome("skip", tend)

        if kind == "make":
            # (a) 앞쪽 주제: 'X에 대한 슬라이드를 만들어 주세요'
            sent_start = max(J.rfind(".", 0, start), J.rfind("?", 0, start), J.rfind("!", 0, start)) + 1
            pre = R_PRE_TOPIC.search(J[sent_start:start])
            comp_end: Optional[int] = None
            topic = None
            direct = None
            if not pre and not m.group(0).startswith("다음"):
                # (b) 'X 슬라이드 부탁해요 / 만들어 주세요' — 바로 앞 명사구(최대 3어절, 채움말 제외)를 주제로
                d = clean_topic(strip_leading_fillers(J[sent_start:start]))
                if d and topic_is_sufficient(d):
                    direct = d
            if pre:
                topic, comp_end = clean_topic(pre.group(1)), tend
            elif direct:
                topic, comp_end = direct, tend
            else:
                ti = R_TOPIC_IS.search(after)
                if ti:
                    topic, comp_end = clean_topic(ti.group(1)), tend + ti.end()
            span_txt = J[start:comp_end] if comp_end else J[start:]
            if R_NEGATION.search(span_txt) or R_NEGATION.search(J[sent_start:start]):
                return _Outcome("ignored", comp_end or len(J), reason="negated")
            if comp_end is not None:
                if quoted_before or R_QUOTE_AFTER.match(J[comp_end:]):
                    return _Outcome("ignored", comp_end, reason="quoted")
                if topic and topic_is_sufficient(topic):
                    return _Outcome("request", comp_end, topic=topic, trigger="completion")
                return _Outcome("needs_input", comp_end, topic=topic, reason="topic_unclear", trigger="completion")
            if not force:
                return _Outcome("pending", len(J))
            if quoted_before:
                return _Outcome("ignored", len(J), reason="quoted")
            return _Outcome("needs_input", len(J), topic=None, reason="topic_missing", trigger="silence")

        if kind == "loose":
            # 같은 문장(마침표·물음표·느낌표 전) 안에 완료 표현이 있어야 한다. 넘김 발화는 무시.
            if R_NON_REQUEST_AFTER.match(after):
                return _Outcome("skip", tend)
            sent_end = min([i for i in (after.find("."), after.find("?"), after.find("!")) if i >= 0] or [len(after)])
            c = R_COMPLETE.search(after[:sent_end + 1])
            if not c:
                if not force and sent_end == len(after):
                    return _Outcome("pending", len(J))  # 문장이 다음 STT 구간으로 이어질 수 있음
                return _Outcome("skip", tend + sent_end)  # 보완 카드 없이 조용히 무시
            comp_end = tend + c.end()
            if R_NEGATION.search(J[start:comp_end]):
                return _Outcome("ignored", comp_end, reason="negated")
            if quoted_before or R_QUOTE_AFTER.match(J[comp_end:]):
                return _Outcome("ignored", comp_end, reason="quoted")
            topic = clean_topic(after[: c.start()])
            if not topic_is_sufficient(topic):
                return _Outcome("skip", comp_end)
            return _Outcome("request", comp_end, topic=topic, trigger="completion")

        # kind == "next"
        # 트리거가 있는 문장 범위. 그 문장에 주제가 있으면 완료 표현도 그 문장 안에서만 찾는다
        # ('다음 슬라이드에서는.' 처럼 트리거만 있는 문장이면 다음 문장까지 허용 — STT 구두점 오류 대비).
        sent_end = min([i for i in (after.find("."), after.find("?"), after.find("!")) if i >= 0] or [len(after)])
        first_sentence = after[:sent_end]
        has_topic_in_sentence = topic_is_sufficient(clean_topic(first_sentence))
        c = R_COMPLETE.search(after[:sent_end + 1] if has_topic_in_sentence else after)
        sentence_closed = has_topic_in_sentence and sent_end < len(after) and bool(after[sent_end + 1:].strip())
        if c:
            comp_end = tend + c.end()
            span_txt = J[start:comp_end]
            if R_NEGATION.search(span_txt):
                return _Outcome("ignored", comp_end, reason="negated")
            if quoted_before or R_QUOTE_AFTER.match(J[comp_end:]):
                return _Outcome("ignored", comp_end, reason="quoted")
            topic = clean_topic(after[: c.start()])
            # '다음 슬라이드를 만들어 주세요. 주제는 X' 형태가 R_NEXT 로 잡힌 경우 보완
            if not topic_is_sufficient(topic):
                ti = R_TOPIC_IS.search(J[comp_end:])
                if ti:
                    return _Outcome("request", comp_end + ti.end(), topic=clean_topic(ti.group(1)), trigger="completion")
                if not force and not J[comp_end:].strip():
                    # '…만들어 주세요' 다음에 '주제는 …' 이 이어질 수 있으므로 잠시 기다림
                    return _Outcome("pending", len(J))
                return _Outcome("needs_input", comp_end, topic=topic or None, reason="topic_unclear", trigger="completion")
            return _Outcome("request", comp_end, topic=topic, trigger="completion")

        scope = first_sentence if has_topic_in_sentence else after
        scope_end = tend + (sent_end + 1 if has_topic_in_sentence and sent_end < len(after) else len(after))
        if R_NEGATION.search(scope):
            return _Outcome("ignored", scope_end, reason="negated")
        if not force and not sentence_closed:
            return _Outcome("pending", len(J))
        # 침묵으로 종료, 또는 문장이 끝나고 다음 문장이 시작됨 → 트리거 문장만으로 판단
        end_pos = scope_end if sentence_closed else len(J)
        trig = "silence" if not sentence_closed else "sentence_end"
        if quoted_before:
            return _Outcome("ignored", end_pos, reason="quoted")
        tail = normalize(scope)
        topic = clean_topic(tail)
        if not tail or not topic_is_sufficient(topic):
            return _Outcome("needs_input", end_pos, topic=topic or None, reason="cut_off", trigger=trig)
        if DANGLING.search(tail):
            return _Outcome("needs_input", end_pos, topic=topic, reason="cut_off", trigger=trig)
        if DECLARATIVE_END.search(tail):
            return _Outcome("needs_input", end_pos, topic=topic, reason="no_request_expression", trigger=trig)
        return _Outcome("request", end_pos, topic=topic, trigger=trig)

    def _scan(self, force: bool, now: float) -> list[DetectorEvent]:
        J, offs = self._join()
        events: list[DetectorEvent] = []
        p = 0
        consume_to = 0
        pending_start: Optional[int] = None
        while True:
            found = self._find_trigger(J, p)
            if not found:
                break
            m, kind = found
            out = self._evaluate(J, m, kind, force)
            if out.kind == "pending":
                pending_start = m.start()
                break
            if out.kind == "skip":
                p = out.end
                consume_to = max(consume_to, out.end)
                continue
            key = self._key(offs, m.start(), out.end)
            segs = self._segs_in(offs, m.start(), out.end)
            if key not in self._emitted_keys:
                self._emitted_keys.add(key)
                events.append(DetectorEvent(
                    kind=out.kind,  # type: ignore[arg-type]
                    text=J[m.start():out.end].strip(),
                    segment_ids=[s.seg_id for s in segs],
                    topic=out.topic, reason=out.reason, trigger=out.trigger, dedupe_key=key,
                    t_first=segs[0].t if segs else None, t_last=segs[-1].t if segs else None,
                    context_prefix=self._prefix(offs, m.start(), consume_to),
                ))
            p = out.end
            consume_to = max(consume_to, out.end)

        # 버퍼 정리
        keep: list[_Seg] = []
        for i, s in enumerate(self._buf):
            a, b = offs[i]
            if pending_start is not None and b > pending_start:
                keep.append(s)
                continue
            if b <= consume_to or a < consume_to:
                continue  # 처리된 요청에 속한 구간
            keep.append(s)
        if pending_start is None:
            keep = [s for s in keep if now - s.t <= self.max_buffer_age_s][-self.keep_tail_segments:]
        self._buf = keep

        if pending_start is not None:
            if self.pending_since is None:
                self.pending_since = now
            first = next((s for s in self._buf), None)
            ckey = first.seg_id if first else None
            if ckey != self._candidate_key:
                self._candidate_key = ckey
                events.append(DetectorEvent(kind="candidate", text=J[pending_start:].strip(),
                                            segment_ids=[s.seg_id for s in self._buf]))
        else:
            self.pending_since = None
            self._candidate_key = None
        return events
