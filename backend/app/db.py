"""SQLite 저장소. 원시 음성은 저장하지 않는다(확정 텍스트만)."""
from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Iterable, Optional

from .schemas import ACTIVE_JOB_STATUSES, JobStatus

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  audience TEXT NOT NULL,
  current_slide_id TEXT,
  auto_advance INTEGER NOT NULL DEFAULT 0,
  presenting INTEGER NOT NULL DEFAULT 0,
  created_at REAL NOT NULL,
  updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS utterances (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL,
  segment_id TEXT NOT NULL,
  text TEXT NOT NULL,
  source TEXT NOT NULL,           -- stt | manual | simulated
  received_at REAL NOT NULL,      -- 서버 wall clock (같은 서버 시계끼리만 비교)
  UNIQUE(session_id, segment_id)
);
CREATE TABLE IF NOT EXISTS slides (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  position INTEGER NOT NULL,
  layout TEXT NOT NULL,
  status TEXT NOT NULL,
  title TEXT NOT NULL DEFAULT '',
  bullets TEXT NOT NULL DEFAULT '[]',
  image_path TEXT,
  image_alt TEXT,
  image_prompt TEXT,
  image_model TEXT,
  text_model TEXT,
  speaker_notes TEXT,
  precision_warning TEXT,
  job_id TEXT,
  error TEXT,
  created_at REAL NOT NULL,
  updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS jobs (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  slide_id TEXT,
  status TEXT NOT NULL,
  request_text TEXT NOT NULL,
  topic TEXT,
  source TEXT NOT NULL,           -- voice | manual | simulated | clarified
  trigger TEXT,                   -- completion | silence | force
  dedupe_key TEXT,
  context TEXT NOT NULL DEFAULT '{}',
  attempt INTEGER NOT NULL DEFAULT 0,
  error_code TEXT,
  error_message TEXT,
  clarification_reason TEXT,
  metrics TEXT NOT NULL DEFAULT '{}',
  created_at REAL NOT NULL,
  updated_at REAL NOT NULL,
  UNIQUE(session_id, dedupe_key)
);
CREATE TABLE IF NOT EXISTS usage_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT,
  job_id TEXT,
  kind TEXT NOT NULL,             -- text | image | stt
  provider TEXT NOT NULL,
  model TEXT NOT NULL,
  settings TEXT NOT NULL DEFAULT '{}',
  input_tokens INTEGER,
  output_tokens INTEGER,
  image_count INTEGER,
  audio_seconds REAL,
  cost_estimate_usd REAL,         -- 확인된 단가가 있을 때만. 실제 청구액 아님.
  outcome TEXT NOT NULL,          -- used | ignored_cancelled | ignored_stale | error
  created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_utt_session ON utterances(session_id, received_at);
CREATE INDEX IF NOT EXISTS idx_slides_session ON slides(session_id, position);
CREATE INDEX IF NOT EXISTS idx_jobs_session ON jobs(session_id, created_at);
"""


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


class Database:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(SCHEMA)
        self._migrate()

    def _migrate(self) -> None:
        """기존 DB 파일에 새 칼럼을 추가한다(데이터 유지)."""
        cols = {r["name"] for r in self._conn.execute("PRAGMA table_info(slides)").fetchall()}
        if "equations" not in cols:
            self._conn.execute("ALTER TABLE slides ADD COLUMN equations TEXT NOT NULL DEFAULT '[]'")
        if "visual" not in cols:
            self._conn.execute("ALTER TABLE slides ADD COLUMN visual TEXT NOT NULL DEFAULT 'null'")

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def _exec(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Cursor:
        with self._lock:
            return self._conn.execute(sql, tuple(params))

    def _one(self, sql: str, params: Iterable[Any] = ()) -> Optional[dict]:
        row = self._exec(sql, params).fetchone()
        return dict(row) if row else None

    def _all(self, sql: str, params: Iterable[Any] = ()) -> list[dict]:
        return [dict(r) for r in self._exec(sql, params).fetchall()]

    # ---------------- sessions ----------------
    def create_session(self, title: str, audience: str) -> dict:
        sid = new_id("ses")
        now = time.time()
        self._exec(
            "INSERT INTO sessions(id,title,audience,created_at,updated_at) VALUES(?,?,?,?,?)",
            (sid, title, audience, now, now),
        )
        cover = self.insert_slide(sid, layout="cover", status=JobStatus.ready.value, title=title,
                                  bullets=[f"대상: {audience}"], job_id=None)
        self.update_session(sid, current_slide_id=cover["id"])
        return self.get_session(sid)  # type: ignore[return-value]

    def get_session(self, sid: str) -> Optional[dict]:
        s = self._one("SELECT * FROM sessions WHERE id=?", (sid,))
        if s:
            s["auto_advance"] = bool(s["auto_advance"])
            s["presenting"] = bool(s["presenting"])
        return s

    def list_sessions(self) -> list[dict]:
        rows = self._all(
            "SELECT s.*, (SELECT COUNT(*) FROM slides sl WHERE sl.session_id=s.id AND sl.status!='cancelled') AS slide_count "
            "FROM sessions s ORDER BY updated_at DESC"
        )
        for r in rows:
            r["auto_advance"] = bool(r["auto_advance"])
            r["presenting"] = bool(r["presenting"])
        return rows

    def update_session(self, sid: str, **fields: Any) -> None:
        if not fields:
            return
        cols = []
        vals = []
        for k, v in fields.items():
            if k not in {"title", "audience", "current_slide_id", "auto_advance", "presenting"}:
                raise ValueError(k)
            cols.append(f"{k}=?")
            vals.append(int(v) if isinstance(v, bool) else v)
        cols.append("updated_at=?")
        vals.append(time.time())
        vals.append(sid)
        self._exec(f"UPDATE sessions SET {', '.join(cols)} WHERE id=?", vals)

    # ---------------- utterances ----------------
    def add_utterance(self, sid: str, segment_id: str, text: str, source: str, received_at: float) -> Optional[int]:
        """같은 segment_id 가 이미 있으면 None (중복)."""
        try:
            cur = self._exec(
                "INSERT INTO utterances(session_id,segment_id,text,source,received_at) VALUES(?,?,?,?,?)",
                (sid, segment_id, text, source, received_at),
            )
            return cur.lastrowid
        except sqlite3.IntegrityError:
            return None

    def recent_utterances(self, sid: str, since: float, until: Optional[float] = None, exclude_segments: Iterable[str] = ()) -> list[dict]:
        rows = self._all(
            "SELECT * FROM utterances WHERE session_id=? AND received_at>=? AND received_at<=? ORDER BY received_at, id",
            (sid, since, until if until is not None else 1e18),
        )
        ex = set(exclude_segments)
        return [r for r in rows if r["segment_id"] not in ex]

    def list_utterances(self, sid: str, limit: int = 200) -> list[dict]:
        rows = self._all("SELECT * FROM utterances WHERE session_id=? ORDER BY id DESC LIMIT ?", (sid, limit))
        return list(reversed(rows))

    # ---------------- slides ----------------
    def insert_slide(self, sid: str, *, layout: str, status: str, title: str = "", bullets: Optional[list[str]] = None,
                     job_id: Optional[str], **extra: Any) -> dict:
        slide_id = new_id("sld")
        now = time.time()
        pos_row = self._one("SELECT COALESCE(MAX(position), -1) AS p FROM slides WHERE session_id=?", (sid,))
        pos = (pos_row["p"] if pos_row else -1) + 1
        self._exec(
            "INSERT INTO slides(id,session_id,position,layout,status,title,bullets,job_id,image_alt,image_prompt,"
            "text_model,speaker_notes,precision_warning,equations,visual,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (slide_id, sid, pos, layout, status, title, json.dumps(bullets or [], ensure_ascii=False), job_id,
             extra.get("image_alt"), extra.get("image_prompt"), extra.get("text_model"), extra.get("speaker_notes"),
             extra.get("precision_warning"), json.dumps(extra.get("equations") or [], ensure_ascii=False),
             json.dumps(extra.get("visual"), ensure_ascii=False), now, now),
        )
        return self.get_slide(slide_id)  # type: ignore[return-value]

    def get_slide(self, slide_id: str) -> Optional[dict]:
        s = self._one("SELECT * FROM slides WHERE id=?", (slide_id,))
        if s:
            s["bullets"] = json.loads(s["bullets"])
            s["equations"] = json.loads(s.get("equations") or "[]")
            s["visual"] = json.loads(s.get("visual") or "null")
        return s

    def list_slides(self, sid: str, include_cancelled: bool = False) -> list[dict]:
        q = "SELECT * FROM slides WHERE session_id=?"
        if not include_cancelled:
            q += " AND status!='cancelled'"
        rows = self._all(q + " ORDER BY position", (sid,))
        for r in rows:
            r["bullets"] = json.loads(r["bullets"])
            r["equations"] = json.loads(r.get("equations") or "[]")
            r["visual"] = json.loads(r.get("visual") or "null")
        return rows

    def update_slide(self, slide_id: str, **fields: Any) -> None:
        allowed = {"status", "title", "bullets", "image_path", "image_alt", "image_prompt", "image_model",
                   "text_model", "speaker_notes", "precision_warning", "error", "layout", "equations", "visual"}
        cols, vals = [], []
        for k, v in fields.items():
            if k not in allowed:
                raise ValueError(k)
            cols.append(f"{k}=?")
            vals.append(json.dumps(v, ensure_ascii=False) if k in ("bullets", "equations", "visual") else v)
        cols.append("updated_at=?")
        vals.append(time.time())
        vals.append(slide_id)
        self._exec(f"UPDATE slides SET {', '.join(cols)} WHERE id=?", vals)

    def update_slide_if_job_attempt(self, slide_id: str, job_id: str, attempt: int, **fields: Any) -> bool:
        """늦게 도착한 결과 방어: 작업이 취소되지 않았고, 시도 번호가 현재와 같을 때만 슬라이드를 갱신."""
        with self._lock:
            job = self._one("SELECT status, attempt FROM jobs WHERE id=?", (job_id,))
            slide = self._one("SELECT job_id FROM slides WHERE id=?", (slide_id,))
            if not job or not slide or slide["job_id"] != job_id:
                return False
            if job["status"] == JobStatus.cancelled.value or job["attempt"] != attempt:
                return False
            self.update_slide(slide_id, **fields)
            return True

    # ---------------- jobs ----------------
    def insert_job(self, sid: str, *, request_text: str, topic: Optional[str], source: str, trigger: str,
                   dedupe_key: Optional[str], context: dict, status: str, metrics: Optional[dict] = None,
                   clarification_reason: Optional[str] = None) -> Optional[dict]:
        jid = new_id("job")
        now = time.time()
        try:
            self._exec(
                "INSERT INTO jobs(id,session_id,status,request_text,topic,source,trigger,dedupe_key,context,metrics,"
                "clarification_reason,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (jid, sid, status, request_text, topic, source, trigger, dedupe_key,
                 json.dumps(context, ensure_ascii=False), json.dumps(metrics or {}), clarification_reason, now, now),
            )
        except sqlite3.IntegrityError:
            return None  # 같은 dedupe_key (같은 확정 발화) → 중복 생성 방지
        return self.get_job(jid)

    def get_job(self, jid: str) -> Optional[dict]:
        j = self._one("SELECT * FROM jobs WHERE id=?", (jid,))
        if j:
            j["context"] = json.loads(j["context"])
            j["metrics"] = json.loads(j["metrics"])
        return j

    def list_jobs(self, sid: Optional[str] = None, limit: int = 50) -> list[dict]:
        if sid:
            rows = self._all("SELECT * FROM jobs WHERE session_id=? ORDER BY created_at DESC LIMIT ?", (sid, limit))
        else:
            rows = self._all("SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,))
        for r in rows:
            r["context"] = json.loads(r["context"])
            r["metrics"] = json.loads(r["metrics"])
        return rows

    def update_job(self, jid: str, **fields: Any) -> None:
        allowed = {"status", "slide_id", "error_code", "error_message", "attempt", "clarification_reason",
                   "request_text", "topic", "context", "source"}
        cols, vals = [], []
        for k, v in fields.items():
            if k not in allowed:
                raise ValueError(k)
            cols.append(f"{k}=?")
            vals.append(json.dumps(v, ensure_ascii=False) if k == "context" else v)
        cols.append("updated_at=?")
        vals.append(time.time())
        vals.append(jid)
        self._exec(f"UPDATE jobs SET {', '.join(cols)} WHERE id=?", vals)

    def merge_job_metrics(self, jid: str, **m: Any) -> None:
        with self._lock:
            j = self._one("SELECT metrics FROM jobs WHERE id=?", (jid,))
            if not j:
                return
            cur = json.loads(j["metrics"])
            cur.update(m)
            self._exec("UPDATE jobs SET metrics=? WHERE id=?", (json.dumps(cur), jid))

    def mark_interrupted_jobs(self) -> int:
        """서버 재시작 시: 진행 중이던 작업을 failed(interrupted) 로 표시해 재시도할 수 있게 한다."""
        active = tuple(s.value for s in ACTIVE_JOB_STATUSES)
        with self._lock:
            rows = self._all(f"SELECT id, slide_id FROM jobs WHERE status IN ({','.join('?'*len(active))})", active)
            for r in rows:
                self.update_job(r["id"], status=JobStatus.failed.value, error_code="interrupted",
                                error_message="서버 재시작으로 작업이 중단되었습니다. 재시도할 수 있습니다.")
                if r["slide_id"]:
                    self.update_slide(r["slide_id"], status=JobStatus.failed.value, error="interrupted")
        return len(rows)

    # ---------------- usage ----------------
    def log_usage(self, *, session_id: Optional[str], job_id: Optional[str], kind: str, provider: str, model: str,
                  settings: dict, outcome: str, input_tokens: Optional[int] = None, output_tokens: Optional[int] = None,
                  image_count: Optional[int] = None, audio_seconds: Optional[float] = None,
                  cost_estimate_usd: Optional[float] = None) -> None:
        self._exec(
            "INSERT INTO usage_log(session_id,job_id,kind,provider,model,settings,input_tokens,output_tokens,image_count,"
            "audio_seconds,cost_estimate_usd,outcome,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (session_id, job_id, kind, provider, model, json.dumps(settings), input_tokens, output_tokens, image_count,
             audio_seconds, cost_estimate_usd, outcome, time.time()),
        )

    def list_usage(self, sid: Optional[str] = None) -> list[dict]:
        if sid:
            return self._all("SELECT * FROM usage_log WHERE session_id=? ORDER BY id", (sid,))
        return self._all("SELECT * FROM usage_log ORDER BY id")
