import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import type { Job, PresenterSnapshot, Session, Slide, Utterance } from "./api";

export interface Notice {
  id: number;
  kind: string;
  text: string;
  at: number;
}

export interface SessionState {
  loaded: boolean;
  session: Session | null;
  slides: Slide[];
  jobs: Job[];
  utterances: Utterance[];
  partial: string;
  notices: Notice[];
  config: PresenterSnapshot["config"] | null;
  credentialProblems: string[];
  stt: { state: string; message: string };
  vadSpeaking: boolean;
  detectorPending: boolean;
  /** 서버가 받은 마이크 입력 음량 (200ms 최대 RMS, int16) */
  level: { rms: number; threshold: number; at: number; recentMax: number[] };
}

const initial: SessionState = {
  loaded: false,
  session: null,
  slides: [],
  jobs: [],
  utterances: [],
  partial: "",
  notices: [],
  config: null,
  credentialProblems: [],
  stt: { state: "stopped", message: "" },
  vadSpeaking: false,
  detectorPending: false,
  level: { rms: 0, threshold: 0, at: 0, recentMax: [] },
};

type Msg = { type: string; session_id: string; job_id?: string; data: any };
let noticeSeq = 0;

function upsert<T extends { id: string }>(list: T[], item: T, sort?: (a: T, b: T) => number): T[] {
  const i = list.findIndex((x) => x.id === item.id);
  const next = i >= 0 ? list.map((x, k) => (k === i ? { ...x, ...item } : x)) : [...list, item];
  return sort ? next.sort(sort) : next;
}

function addNotice(s: SessionState, kind: string, text: string): Notice[] {
  return [...s.notices, { id: ++noticeSeq, kind, text, at: Date.now() }].slice(-30);
}

function reducer(s: SessionState, m: Msg | { type: "local.notice"; kind: string; text: string }): SessionState {
  if (m.type === "local.notice") return { ...s, notices: addNotice(s, (m as any).kind, (m as any).text) };
  const msg = m as Msg;
  const d = msg.data;
  switch (msg.type) {
    case "snapshot":
      return {
        ...s,
        loaded: true,
        session: d.session,
        slides: d.slides ?? [],
        jobs: d.jobs ?? s.jobs,
        utterances: d.utterances ?? s.utterances,
        config: d.config ?? s.config,
        credentialProblems: d.credential_problems ?? s.credentialProblems,
        detectorPending: !!d.detector_pending,
      };
    case "session.updated":
      return { ...s, session: s.session ? { ...s.session, ...d } : d };
    case "slide.updated":
      return { ...s, slides: upsert(s.slides, d as Slide, (a, b) => a.position - b.position) };
    case "slide.removed":
      return { ...s, slides: s.slides.filter((x) => x.id !== d.slide_id) };
    case "job.updated":
      return { ...s, jobs: upsert(s.jobs, d as Job, (a, b) => b.created_at - a.created_at) };
    case "transcript.partial":
      return { ...s, partial: d.text ?? "" };
    case "transcript.final": {
      if (d.empty) return { ...s, partial: "" };
      const u: Utterance = { id: d.utterance_id, segment_id: d.segment_id, text: d.text, source: d.source, received_at: Date.now() / 1000, late: !!d.late };
      return { ...s, partial: "", utterances: [...s.utterances, u].slice(-80) };
    }
    case "detector": {
      const label: Record<string, string> = {
        candidate: "요청 감지 중… (완료 표현 또는 침묵을 기다림)",
        request: `생성 요청 확정: ${d.topic ?? d.text}`,
        needs_input: "입력 보완이 필요한 요청",
        ignored: d.message ?? "무시됨",
        duplicate: "중복 요청이라 무시함",
      };
      return {
        ...s,
        detectorPending: d.kind === "candidate",
        notices: addNotice(s, d.kind, `${label[d.kind] ?? d.kind}${d.kind !== "request" ? ` — “${d.text}”` : ""}`),
      };
    }
    case "queue.rejected":
      return { ...s, notices: addNotice(s, "rejected", `${d.reason} — “${d.text}”`) };
    case "stt.status":
      return { ...s, stt: { state: d.state, message: d.message ?? "" }, vadSpeaking: d.state === "ready" ? s.vadSpeaking : false };
    case "stt.notice":
      return { ...s, notices: addNotice(s, d.level === "error" ? "stt_error" : "stt", d.message) };
    case "stt.vad":
      return { ...s, vadSpeaking: !!d.speaking };
    case "stt.level":
      return {
        ...s,
        level: { rms: d.rms, threshold: d.threshold, at: Date.now(), recentMax: [...s.level.recentMax, d.rms].slice(-25) },
      };
    default:
      return s;
  }
}

export type ConnState = "connecting" | "open" | "closed";

export function useSessionSocket(sid: string, role: "presenter" | "audience", onOpen?: (ws: WebSocket) => void) {
  const [state, dispatch] = useReducer(reducer, initial);
  const [conn, setConn] = useState<ConnState>("connecting");
  const wsRef = useRef<WebSocket | null>(null);
  const onOpenRef = useRef(onOpen);
  onOpenRef.current = onOpen;
  const listeners = useRef(new Set<(m: Msg) => void>());

  useEffect(() => {
    let closed = false;
    let retry = 0;
    let timer: number | undefined;
    const connect = () => {
      setConn("connecting");
      const proto = location.protocol === "https:" ? "wss" : "ws";
      const ws = new WebSocket(`${proto}://${location.host}/ws/sessions/${sid}?role=${role}`);
      ws.binaryType = "arraybuffer";
      wsRef.current = ws;
      ws.onopen = () => {
        retry = 0;
        setConn("open");
        onOpenRef.current?.(ws);
      };
      ws.onmessage = (ev) => {
        try {
          const m = JSON.parse(ev.data as string) as Msg;
          dispatch(m);
          listeners.current.forEach((fn) => fn(m));
        } catch {
          /* noop */
        }
      };
      ws.onclose = () => {
        if (wsRef.current === ws) wsRef.current = null;
        setConn("closed");
        if (closed) return;
        retry += 1;
        timer = window.setTimeout(connect, Math.min(500 * 2 ** (retry - 1), 8000));
      };
    };
    connect();
    const ping = window.setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) wsRef.current.send(JSON.stringify({ type: "ping" }));
    }, 20000);
    return () => {
      closed = true;
      window.clearTimeout(timer);
      window.clearInterval(ping);
      wsRef.current?.close();
    };
  }, [sid, role]);

  const sendJson = useCallback((obj: unknown) => {
    const ws = wsRef.current;
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(obj));
      return true;
    }
    return false;
  }, []);
  const sendBinary = useCallback((buf: ArrayBuffer) => {
    const ws = wsRef.current;
    if (ws?.readyState === WebSocket.OPEN && ws.bufferedAmount < 2_000_000) {
      ws.send(buf);
      return true;
    }
    return false;
  }, []);
  const notify = useCallback((kind: string, text: string) => dispatch({ type: "local.notice", kind, text }), []);
  const subscribe = useCallback((fn: (m: Msg) => void) => {
    listeners.current.add(fn);
    return () => {
      listeners.current.delete(fn);
    };
  }, []);

  return { state, conn, sendJson, sendBinary, notify, subscribe };
}
