export type JobStatus =
  | "queued"
  | "planning"
  | "text_ready"
  | "generating_image"
  | "ready"
  | "failed"
  | "cancelled"
  | "needs_input";

export type Layout =
  | "cover"
  | "title_bullets_image"
  | "title_bullets_equation"
  | "title_bullets"
  | "title_comparison"
  | "title_table"
  | "title_chart";

export interface ComparisonVisual {
  type: "comparison";
  left: { title: string; points: string[] };
  right: { title: string; points: string[] };
}
export interface TableVisual {
  type: "table";
  columns: string[];
  rows: string[][];
}
export interface ChartVisual {
  type: "chart";
  kind: "function" | "line" | "bar";
  x_label: string;
  y_label: string;
  functions: { expr: string; label: string }[];
  x_min: number | null;
  x_max: number | null;
  categories: string[];
  series: { name: string; values: number[] }[];
  note: string;
  /** 함수 그래프: 서버가 계산한 좌표 */
  computed?: { label: string; points: (number | null)[][] }[];
}
export type Visual = ComparisonVisual | TableVisual | ChartVisual;

export interface Equation {
  latex: string;
  caption: string;
}

export interface Slide {
  id: string;
  session_id: string;
  position: number;
  layout: Layout;
  status: JobStatus;
  title: string;
  bullets: string[];
  image_url: string | null;
  image_alt: string;
  equations: Equation[];
  visual: Visual | null;
  // presenter 전용
  job_id?: string | null;
  image_prompt?: string | null;
  image_model?: string | null;
  text_model?: string | null;
  speaker_notes?: string | null;
  precision_warning?: string | null;
  error?: string | null;
  is_mock?: boolean;
}

export interface Job {
  id: string;
  job_id: string;
  session_id: string;
  slide_id: string | null;
  status: JobStatus;
  request_text: string;
  topic: string | null;
  source: string;
  trigger: string | null;
  attempt: number;
  error_code: string | null;
  error_message: string | null;
  clarification_reason: string | null;
  metrics: Record<string, unknown>;
  created_at: number;
  context_preview: { transcript_chars: number; current_slide_title: string | null };
}

export interface Session {
  id: string;
  title: string;
  audience: string;
  current_slide_id: string | null;
  auto_advance: boolean;
  presenting: boolean;
  /** 그림이 오기 전에도 텍스트가 준비된 그림형 장으로 넘길 수 있음 */
  show_before_image?: boolean;
  created_at: number;
  updated_at: number;
  slide_count?: number;
}

export interface Utterance {
  id: number;
  segment_id: string;
  text: string;
  source: string;
  received_at: number;
  late?: boolean;
}

export interface PublicConfig {
  stt: { provider: string; model: string; sample_rate: number; encoding: string; channels: number };
  text: { provider: string; model: string };
  image: { provider: string; model: string; size: string };
  mock: { stt: boolean; text: boolean; image: boolean };
  request_silence_ms: number;
  max_queue: number;
}

export interface PresenterSnapshot {
  session: Session;
  slides: Slide[];
  jobs: Job[];
  utterances: Utterance[];
  config: PublicConfig;
  credential_problems: string[];
  queue: { running: string | null; waiting: string[]; max: number };
  detector_pending: boolean;
  mic_active: boolean;
}

async function req<T>(method: string, url: string, body?: unknown): Promise<T> {
  const res = await fetch(url, {
    method,
    headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    let msg = `${res.status}`;
    try {
      const j = await res.json();
      msg = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail ?? j);
    } catch {
      /* noop */
    }
    throw new Error(msg);
  }
  return res.json() as Promise<T>;
}

export const api = {
  listSessions: () => req<Session[]>("GET", "/api/sessions"),
  createSession: (title: string, audience: string) => req<Session>("POST", "/api/sessions", { title, audience }),
  patchSession: (
    sid: string,
    body: Partial<Pick<Session, "title" | "audience" | "auto_advance" | "presenting" | "show_before_image">>,
  ) =>
    req<Session>("PATCH", `/api/sessions/${sid}`, body),
  input: (sid: string, text: string, mode: "detect" | "force") =>
    req<{ accepted: boolean; job_id?: string }>("POST", `/api/sessions/${sid}/input`, { text, mode }),
  cancel: (sid: string, jid: string) => req("POST", `/api/sessions/${sid}/jobs/${jid}/cancel`),
  retry: (sid: string, jid: string) => req("POST", `/api/sessions/${sid}/jobs/${jid}/retry`),
  clarify: (sid: string, jid: string, text: string) => req("POST", `/api/sessions/${sid}/jobs/${jid}/clarify`, { text }),
  dismiss: (sid: string, jid: string) => req("POST", `/api/sessions/${sid}/jobs/${jid}/dismiss`),
  editSlide: (
    sid: string,
    slideId: string,
    body: {
      title?: string;
      bullets?: string[];
      equations?: Equation[];
      comparison?: Omit<ComparisonVisual, "type">;
      table?: Omit<TableVisual, "type">;
    },
  ) =>
    req("PATCH", `/api/sessions/${sid}/slides/${slideId}`, body),
  finalizeWithoutImage: (sid: string, slideId: string) =>
    req("POST", `/api/sessions/${sid}/slides/${slideId}/finalize-without-image`),
  navigate: (sid: string, body: { slide_id?: string; direction?: "prev" | "next" }) =>
    req<{ ok: boolean; current_slide_id: string }>("POST", `/api/sessions/${sid}/navigate`, body),
  renderMetric: (sid: string, job_id: string, slide_id: string, render_ms: number) =>
    req("POST", `/api/sessions/${sid}/metrics/render`, { job_id, slide_id, render_ms }),
  metrics: (sid?: string) => req<Record<string, any>>("GET", `/api/metrics${sid ? `?session_id=${sid}` : ""}`),
};

const IMAGE_PENDING = new Set(["queued", "text_ready", "generating_image", "failed"]);

/** 서버 runtime.presentable 과 같은 규칙: 넘길 수 있는(청중에게 보일 수 있는) 장 */
export function presentable(s: Slide, session: Pick<Session, "show_before_image"> | null | undefined): boolean {
  if (s.status === "ready") return true;
  return !!(session?.show_before_image ?? true) && s.layout === "title_bullets_image" && IMAGE_PENDING.has(s.status) && !!s.title;
}

export const STATUS_LABEL: Record<JobStatus, string> = {
  queued: "대기 중",
  planning: "기획 중",
  text_ready: "텍스트 준비",
  generating_image: "이미지 생성 중",
  ready: "준비 완료",
  failed: "실패",
  cancelled: "취소됨",
  needs_input: "입력 보완 필요",
};
