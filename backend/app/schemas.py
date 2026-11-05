"""명시적 데이터 스키마 (Pydantic). 웹 렌더링·저장·LLM 출력 검증이 모두 이 스키마를 공유한다."""
from __future__ import annotations

import re
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class JobStatus(str, Enum):
    queued = "queued"
    planning = "planning"
    text_ready = "text_ready"
    generating_image = "generating_image"
    ready = "ready"
    failed = "failed"
    cancelled = "cancelled"
    # 요청은 감지됐지만 주제가 불충분해 사용자 보완을 기다리는 상태 (대기열 미점유)
    needs_input = "needs_input"


ACTIVE_JOB_STATUSES = {JobStatus.queued, JobStatus.planning, JobStatus.text_ready, JobStatus.generating_image}
TERMINAL_JOB_STATUSES = {JobStatus.ready, JobStatus.failed, JobStatus.cancelled}

SlideLayout = Literal["cover", "title_bullets_image", "title_bullets_equation", "title_bullets",
                      "title_comparison", "title_table", "title_chart"]
VisualType = Literal["illustration", "equation", "text", "comparison", "table", "chart"]
LAYOUT_BY_VISUAL = {"illustration": "title_bullets_image", "equation": "title_bullets_equation", "text": "title_bullets",
                    "comparison": "title_comparison", "table": "title_table", "chart": "title_chart"}
STRUCTURED_VISUALS = ("comparison", "table", "chart")
EQUATIONS_MAX = 3
LATEX_MAX = 300
EQ_CAPTION_MAX = 80
# KaTeX 는 trust=false 로 렌더링하지만, 링크·외부 리소스 명령은 저장 단계에서도 거부한다
_LATEX_FORBIDDEN = ("\\href", "\\url", "\\includegraphics", "\\htmlClass", "\\htmlId", "\\htmlStyle", "\\htmlData")


# JSON 이스케이프 손상 복구: 모델이 LaTeX 백슬래시를 잘못 이스케이프하면 '\theta'→탭+'heta', '\beta'→백스페이스+'eta',
# '\nabla'→줄바꿈+'abla', '\frac'→폼피드+'rac', '\(' → NUL+'(' 처럼 제어 문자가 섞인다. 원래 명령으로 되돌린다.
_ESC_REPAIR = {"\x00": "\\", "\x08": "\\b", "\x0c": "\\f", "\t": "\\t", "\r": "\\r"}


def repair_escapes(text: str) -> str:
    if not isinstance(text, str):
        return text
    for bad, good in _ESC_REPAIR.items():
        text = text.replace(bad, good)
    text = re.sub(r"\n(?=[a-zA-Z])", r"\\n", text)  # '\nabla', '\neq', '\nu'
    text = re.sub(r"\\\\(?=[a-zA-Z])", r"\\", text)  # 이중 이스케이프 '\\eta' → '\eta' (글자 앞 줄바꿈 명령은 의도가 아님)
    # 짝이 깨진 인라인 수식 '\(\theta_t)' → '$\theta_t$'
    text = re.sub(r"\\\(([^()]{1,60}?)\)(?<!\\\))", r"$\1$", text)
    return re.sub(r"[\x01-\x07\x0b\x0e-\x1f]", "", text)


def validate_latex(latex: str) -> str:
    latex = repair_escapes(latex)
    latex = (latex or "").strip().strip("$").strip()
    if not (1 <= len(latex) <= LATEX_MAX):
        raise ValueError(f"수식(LaTeX)은 1~{LATEX_MAX}자여야 합니다")
    if any(cmd in latex for cmd in _LATEX_FORBIDDEN):
        raise ValueError("수식에 허용되지 않는 명령이 있습니다")
    depth = 0
    for ch in latex.replace("\\{", "").replace("\\}", ""):
        depth += ch == "{"
        depth -= ch == "}"
        if depth < 0:
            break
    if depth != 0:
        raise ValueError("수식의 중괄호 짝이 맞지 않습니다")
    return latex


class EquationItem(BaseModel):
    latex: str
    caption: str = ""

    @model_validator(mode="after")
    def _check(self) -> "EquationItem":
        self.latex = validate_latex(self.latex)
        self.caption = repair_escapes(self.caption or "").strip()
        if any(cmd in self.caption for cmd in _LATEX_FORBIDDEN):
            raise ValueError("수식 설명에 허용되지 않는 명령이 있습니다")
        if len(self.caption) > EQ_CAPTION_MAX:
            raise ValueError(f"수식 설명은 {EQ_CAPTION_MAX}자 이하여야 합니다")
        return self

# 슬라이드 텍스트 길이 상한 (16:9 템플릿에서 넘치지 않도록 템플릿과 함께 정한 값)
TITLE_MAX = 40
BULLET_MAX = 70
BULLETS_MIN, BULLETS_MAX = 2, 3


def _clean(t: Any) -> Any:
    return repair_escapes(t).strip() if isinstance(t, str) else t


def _chk_len(name: str, t: str, lo: int, hi: int) -> None:
    if not (lo <= len(t) <= hi):
        raise ValueError(f"{name} 길이는 {lo}~{hi}자여야 합니다 (현재 {len(t)})")


class CompareSide(BaseModel):
    title: str
    points: list[str]

    @model_validator(mode="after")
    def _check(self) -> "CompareSide":
        self.title = _clean(self.title)
        self.points = [_clean(p) for p in self.points if _clean(p)]
        _chk_len("비교 제목", self.title, 1, 24)
        if not (1 <= len(self.points) <= 4):
            raise ValueError("비교 항목은 한쪽에 1~4개여야 합니다")
        for p in self.points:
            _chk_len("비교 항목", p, 1, 50)
        return self


class ComparisonSpec(BaseModel):
    left: CompareSide
    right: CompareSide


class TableSpec(BaseModel):
    columns: list[str]
    rows: list[list[str]]

    @model_validator(mode="after")
    def _check(self) -> "TableSpec":
        self.columns = [_clean(c) for c in self.columns]
        self.rows = [[_clean(c) for c in r] for r in self.rows]
        if not (2 <= len(self.columns) <= 4):
            raise ValueError("표의 열은 2~4개여야 합니다")
        if not (2 <= len(self.rows) <= 6):
            raise ValueError("표의 행은 2~6개여야 합니다")
        for c in self.columns:
            _chk_len("열 제목", c, 1, 20)
        for r in self.rows:
            if len(r) != len(self.columns):
                raise ValueError("각 행의 칸 수는 열 수와 같아야 합니다")
            for c in r:
                _chk_len("표 칸", c, 1, 40)
        return self


class FunctionCurve(BaseModel):
    expr: str
    label: str


class ChartSeries(BaseModel):
    name: str
    values: list[float]


class ChartSpec(BaseModel):
    kind: Literal["function", "line", "bar"]
    x_label: str = ""
    y_label: str = ""
    functions: list[FunctionCurve] = Field(default_factory=list)
    x_min: Optional[float] = None
    x_max: Optional[float] = None
    categories: list[str] = Field(default_factory=list)
    series: list[ChartSeries] = Field(default_factory=list)
    note: str = ""

    @model_validator(mode="after")
    def _check(self) -> "ChartSpec":
        from .chartmath import ExprError, sample  # 지연 import (순환 방지)
        self.x_label, self.y_label, self.note = _clean(self.x_label), _clean(self.y_label), _clean(self.note)
        _chk_len("x축 이름", self.x_label, 0, 24)
        _chk_len("y축 이름", self.y_label, 0, 24)
        _chk_len("그래프 주석", self.note, 0, 60)
        if self.kind == "function":
            if not (1 <= len(self.functions) <= 3):
                raise ValueError("함수 그래프는 함수식이 1~3개여야 합니다")
            if self.x_min is None or self.x_max is None or not (self.x_min < self.x_max) or self.x_max - self.x_min > 1e4:
                raise ValueError("함수 그래프는 x_min < x_max 인 x 범위가 필요합니다")
            for f in self.functions:
                f.label = _clean(f.label)
                _chk_len("곡선 이름", f.label, 1, 24)
                try:
                    sample(f.expr, self.x_min, self.x_max)
                except ExprError as e:
                    raise ValueError(str(e)) from e
            self.categories, self.series = [], []
        else:
            if not (2 <= len(self.categories) <= 10):
                raise ValueError("막대/선 그래프는 항목(categories)이 2~10개여야 합니다")
            self.categories = [_clean(c) for c in self.categories]
            for c in self.categories:
                _chk_len("항목 이름", c, 1, 14)
            if not (1 <= len(self.series) <= 3):
                raise ValueError("막대/선 그래프는 계열(series)이 1~3개여야 합니다")
            for sr in self.series:
                sr.name = _clean(sr.name)
                _chk_len("계열 이름", sr.name, 1, 20)
                if len(sr.values) != len(self.categories):
                    raise ValueError("계열 값 개수는 항목 수와 같아야 합니다")
                if any(not (abs(v) < 1e9) for v in sr.values):
                    raise ValueError("그래프 값이 너무 큽니다")
            if not self.note:
                raise ValueError("막대/선 그래프는 note 에 수치 출처(강의에서 언급한 값) 또는 '설명용 예시 값'을 적어야 합니다")
            self.functions, self.x_min, self.x_max = [], None, None
        return self


class SlideSpec(BaseModel):
    """LLM이 반환해야 하는 슬라이드 명세. 필드 타입·개수·길이를 검증한다."""

    title: str = ""
    bullets: list[str] = Field(default_factory=list)
    visual_type: VisualType = "illustration"
    equations: list[EquationItem] = Field(default_factory=list)
    comparison: Optional[ComparisonSpec] = None
    table: Optional[TableSpec] = None
    chart: Optional[ChartSpec] = None
    visual_intent: str = ""
    image_prompt: str = ""
    speaker_notes: str = ""
    needs_clarification: bool = False
    clarification_reason: Optional[str] = None
    precision_warning: Optional[str] = None  # 정확한 그래프/수식 등 이미지 범위를 넘는 요청 표시

    @field_validator("title", "visual_intent", "image_prompt", "speaker_notes", mode="before")
    @classmethod
    def _strip(cls, v: Any) -> Any:
        return v.strip() if isinstance(v, str) else v

    @field_validator("bullets", mode="before")
    @classmethod
    def _strip_bullets(cls, v: Any) -> Any:
        if isinstance(v, list):
            return [repair_escapes(b).strip().lstrip("-•· ").strip() if isinstance(b, str) else b for b in v]
        return v

    @model_validator(mode="after")
    def _check(self) -> "SlideSpec":
        texts = [self.title, self.speaker_notes, *self.bullets, *(e.latex for e in self.equations),
                 *(e.caption for e in self.equations)]
        if any(("[?]" in t) or ("\ufffd" in t) for t in texts):
            raise ValueError("깨진 기호('[?]' 또는 U+FFFD)가 있습니다. 기호는 유니코드 문자로 쓰세요")
        if self.needs_clarification:
            if not (self.clarification_reason or "").strip():
                raise ValueError("needs_clarification=true 이면 clarification_reason 이 필요합니다")
            return self
        if not (1 <= len(self.title) <= TITLE_MAX):
            raise ValueError(f"title 길이는 1~{TITLE_MAX}자여야 합니다 (현재 {len(self.title)})")
        lo = 1 if self.visual_type in STRUCTURED_VISUALS else BULLETS_MIN  # 비교·표·그래프는 핵심 문장 1개부터
        if not (lo <= len(self.bullets) <= BULLETS_MAX):
            raise ValueError(f"bullets 는 {lo}~{BULLETS_MAX}개여야 합니다 (현재 {len(self.bullets)})")
        for i, b in enumerate(self.bullets):
            if any(cmd in b for cmd in _LATEX_FORBIDDEN):
                raise ValueError(f"bullets[{i}] 에 허용되지 않는 명령이 있습니다")
            if not (1 <= len(b) <= BULLET_MAX):
                raise ValueError(f"bullets[{i}] 길이는 1~{BULLET_MAX}자여야 합니다 (현재 {len(b)})")
        if len(self.visual_intent) > 300:
            raise ValueError("visual_intent 는 300자 이하여야 합니다")
        if self.visual_type == "illustration":
            if not (1 <= len(self.visual_intent) <= 300):
                raise ValueError("그림형(illustration)은 visual_intent 가 필요합니다")
            if not (10 <= len(self.image_prompt) <= 1200):
                raise ValueError("그림형(illustration)은 image_prompt 가 10~1200자여야 합니다")
        elif self.visual_type == "equation":
            if not (1 <= len(self.equations) <= EQUATIONS_MAX):
                raise ValueError(f"수식형(equation)은 equations 가 1~{EQUATIONS_MAX}개여야 합니다 (현재 {len(self.equations)})")
        elif self.visual_type in STRUCTURED_VISUALS and getattr(self, self.visual_type) is None:
            raise ValueError(f"{self.visual_type} 형태는 {self.visual_type} 데이터가 필요합니다")
        for vt in STRUCTURED_VISUALS:
            if self.visual_type != vt:
                setattr(self, vt, None)
        if self.visual_type != "equation":
            self.equations = []
        if self.visual_type != "illustration":
            self.image_prompt = ""
        if len(self.speaker_notes) > 800:
            raise ValueError("speaker_notes 는 800자 이하여야 합니다")
        return self


# LLM structured output 에 넘기는 JSON 스키마 (길이 제약은 Pydantic 쪽에서 검증)
SLIDE_SPEC_JSON_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "bullets": {"type": "array", "items": {"type": "string"}},
        "visual_type": {"type": "string", "enum": ["illustration", "equation", "text", "comparison", "table", "chart"]},
        "equations": {"type": "array", "items": {
            "type": "object",
            "properties": {"latex": {"type": "string"}, "caption": {"type": "string"}},
            "required": ["latex", "caption"], "additionalProperties": False}},
        "comparison": {"anyOf": [{"type": "null"}, {
            "type": "object",
            "properties": {side: {"type": "object", "properties": {"title": {"type": "string"},
                                                                    "points": {"type": "array", "items": {"type": "string"}}},
                                  "required": ["title", "points"], "additionalProperties": False}
                           for side in ("left", "right")},
            "required": ["left", "right"], "additionalProperties": False}]},
        "table": {"anyOf": [{"type": "null"}, {
            "type": "object",
            "properties": {"columns": {"type": "array", "items": {"type": "string"}},
                           "rows": {"type": "array", "items": {"type": "array", "items": {"type": "string"}}}},
            "required": ["columns", "rows"], "additionalProperties": False}]},
        "chart": {"anyOf": [{"type": "null"}, {
            "type": "object",
            "properties": {
                "kind": {"type": "string", "enum": ["function", "line", "bar"]},
                "x_label": {"type": "string"}, "y_label": {"type": "string"},
                "functions": {"type": "array", "items": {
                    "type": "object", "properties": {"expr": {"type": "string"}, "label": {"type": "string"}},
                    "required": ["expr", "label"], "additionalProperties": False}},
                "x_min": {"type": ["number", "null"]}, "x_max": {"type": ["number", "null"]},
                "categories": {"type": "array", "items": {"type": "string"}},
                "series": {"type": "array", "items": {
                    "type": "object", "properties": {"name": {"type": "string"},
                                                     "values": {"type": "array", "items": {"type": "number"}}},
                    "required": ["name", "values"], "additionalProperties": False}},
                "note": {"type": "string"}},
            "required": ["kind", "x_label", "y_label", "functions", "x_min", "x_max", "categories", "series", "note"],
            "additionalProperties": False}]},
        "visual_intent": {"type": "string"},
        "image_prompt": {"type": "string"},
        "speaker_notes": {"type": "string"},
        "needs_clarification": {"type": "boolean"},
        "clarification_reason": {"type": ["string", "null"]},
        "precision_warning": {"type": ["string", "null"]},
    },
    "required": [
        "title", "bullets", "visual_type", "equations", "comparison", "table", "chart",
        "visual_intent", "image_prompt", "speaker_notes",
        "needs_clarification", "clarification_reason", "precision_warning",
    ],
    "additionalProperties": False,
}


class SlideEdit(BaseModel):
    title: Optional[str] = None
    bullets: Optional[list[str]] = None
    equations: Optional[list[EquationItem]] = None
    comparison: Optional[ComparisonSpec] = None
    table: Optional[TableSpec] = None

    @model_validator(mode="after")
    def _check(self) -> "SlideEdit":
        if self.title is not None:
            self.title = self.title.strip()
            if not (1 <= len(self.title) <= TITLE_MAX):
                raise ValueError(f"제목은 1~{TITLE_MAX}자여야 합니다")
        if self.bullets is not None:
            self.bullets = [b.strip() for b in self.bullets if b.strip()]
            if not (1 <= len(self.bullets) <= BULLETS_MAX):
                raise ValueError(f"핵심 문장은 1~{BULLETS_MAX}개여야 합니다")
            for b in self.bullets:
                if len(b) > BULLET_MAX:
                    raise ValueError(f"핵심 문장은 {BULLET_MAX}자 이하여야 합니다")
        if self.equations is not None and len(self.equations) > EQUATIONS_MAX:
            raise ValueError(f"수식은 최대 {EQUATIONS_MAX}개입니다")
        return self


class SessionCreate(BaseModel):
    title: str = Field(min_length=1, max_length=80)
    audience: str = Field(min_length=1, max_length=80)


class SessionPatch(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=80)
    audience: Optional[str] = Field(default=None, min_length=1, max_length=80)
    auto_advance: Optional[bool] = None
    presenting: Optional[bool] = None
    show_before_image: Optional[bool] = None


class ManualInput(BaseModel):
    text: str = Field(min_length=1, max_length=1000)
    # detect: 확정 발화처럼 감지기로 보냄('|' 로 STT 구간 분할 시뮬레이션), force: 현재 입력으로 바로 생성
    mode: Literal["detect", "force"] = "detect"


class ClarifyInput(BaseModel):
    text: str = Field(min_length=1, max_length=500)


class NavigateInput(BaseModel):
    slide_id: Optional[str] = None
    direction: Optional[Literal["prev", "next"]] = None


class RenderMetric(BaseModel):
    job_id: str
    slide_id: str
    render_ms: float = Field(ge=0, le=600_000)
