"""명시적 데이터 스키마 (Pydantic). 웹 렌더링·저장·LLM 출력 검증이 모두 이 스키마를 공유한다."""
from __future__ import annotations

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

SlideLayout = Literal["cover", "title_bullets_image"]

# 슬라이드 텍스트 길이 상한 (16:9 템플릿에서 넘치지 않도록 템플릿과 함께 정한 값)
TITLE_MAX = 40
BULLET_MAX = 70
BULLETS_MIN, BULLETS_MAX = 2, 3


class SlideSpec(BaseModel):
    """LLM이 반환해야 하는 슬라이드 명세. 필드 타입·개수·길이를 검증한다."""

    title: str = ""
    bullets: list[str] = Field(default_factory=list)
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
            return [b.strip().lstrip("-•· ").strip() if isinstance(b, str) else b for b in v]
        return v

    @model_validator(mode="after")
    def _check(self) -> "SlideSpec":
        if self.needs_clarification:
            if not (self.clarification_reason or "").strip():
                raise ValueError("needs_clarification=true 이면 clarification_reason 이 필요합니다")
            return self
        if not (1 <= len(self.title) <= TITLE_MAX):
            raise ValueError(f"title 길이는 1~{TITLE_MAX}자여야 합니다 (현재 {len(self.title)})")
        if not (BULLETS_MIN <= len(self.bullets) <= BULLETS_MAX):
            raise ValueError(f"bullets 는 {BULLETS_MIN}~{BULLETS_MAX}개여야 합니다 (현재 {len(self.bullets)})")
        for i, b in enumerate(self.bullets):
            if not (1 <= len(b) <= BULLET_MAX):
                raise ValueError(f"bullets[{i}] 길이는 1~{BULLET_MAX}자여야 합니다 (현재 {len(b)})")
        if not (1 <= len(self.visual_intent) <= 300):
            raise ValueError("visual_intent 길이는 1~300자여야 합니다")
        if not (10 <= len(self.image_prompt) <= 1200):
            raise ValueError("image_prompt 길이는 10~1200자여야 합니다")
        if len(self.speaker_notes) > 800:
            raise ValueError("speaker_notes 는 800자 이하여야 합니다")
        return self


# LLM structured output 에 넘기는 JSON 스키마 (길이 제약은 Pydantic 쪽에서 검증)
SLIDE_SPEC_JSON_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "bullets": {"type": "array", "items": {"type": "string"}},
        "visual_intent": {"type": "string"},
        "image_prompt": {"type": "string"},
        "speaker_notes": {"type": "string"},
        "needs_clarification": {"type": "boolean"},
        "clarification_reason": {"type": ["string", "null"]},
        "precision_warning": {"type": ["string", "null"]},
    },
    "required": [
        "title", "bullets", "visual_intent", "image_prompt", "speaker_notes",
        "needs_clarification", "clarification_reason", "precision_warning",
    ],
    "additionalProperties": False,
}


class SlideEdit(BaseModel):
    title: Optional[str] = None
    bullets: Optional[list[str]] = None

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
        return self


class SessionCreate(BaseModel):
    title: str = Field(min_length=1, max_length=80)
    audience: str = Field(min_length=1, max_length=80)


class SessionPatch(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=80)
    audience: Optional[str] = Field(default=None, min_length=1, max_length=80)
    auto_advance: Optional[bool] = None
    presenting: Optional[bool] = None


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
