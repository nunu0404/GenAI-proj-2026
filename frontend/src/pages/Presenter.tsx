import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, STATUS_LABEL, type Job, type Slide } from "../api";
import { MicError, startMic, TARGET_RATE, type MicHandle } from "../audio/mic";
import { SlideFrame, SlideView } from "../components/SlideView";
import { isTypingTarget } from "../keys";
import { useSessionSocket } from "../useSessionSocket";

const ACTIVE = new Set(["queued", "planning", "text_ready", "generating_image"]);

export function Presenter({ sid }: { sid: string }) {
  const micRef = useRef<MicHandle | null>(null);
  const onOpen = useCallback((ws: WebSocket) => {
    // 재연결 시 서버 측 STT 스트림이 끊겼으므로 마이크가 켜져 있으면 다시 선언
    if (micRef.current)
      ws.send(JSON.stringify({ type: "mic_start", sample_rate: TARGET_RATE, encoding: "pcm_s16le", channels: 1, input_rate: micRef.current.inputRate }));
  }, []);
  const { state, conn, sendJson, sendBinary, notify, subscribe } = useSessionSocket(sid, "presenter", onOpen);
  const { session, slides, jobs, config } = state;

  const [micOn, setMicOn] = useState(false);
  const [micStarting, setMicStarting] = useState(false);
  const [micErr, setMicErr] = useState<string | null>(null);
  const [inputText, setInputText] = useState("");
  const [busy, setBusy] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [editing, setEditing] = useState<Slide | null>(null);
  const [presentMode, setPresentMode] = useState(false);
  const [metrics, setMetrics] = useState<Record<string, any> | null>(null);
  const [clarify, setClarify] = useState<Record<string, string>>({});
  const [previewOverflow, setPreviewOverflow] = useState(false);
  const presentRef = useRef<HTMLDivElement>(null);

  // ------------------------------------------------ 파생 상태
  const curIdx = slides.findIndex((s) => s.id === session?.current_slide_id);
  const current = curIdx >= 0 ? slides[curIdx] : slides.find((s) => s.status === "ready");
  const nextSlide = curIdx >= 0 ? slides[curIdx + 1] : undefined;
  const preview = (selectedId && slides.find((s) => s.id === selectedId)) || nextSlide;
  const readySlides = slides.filter((s) => s.status === "ready");
  const readyIdx = current ? readySlides.findIndex((s) => s.id === current.id) : -1;
  const canPrev = readyIdx > 0;
  const canNext = readyIdx >= 0 && readyIdx < readySlides.length - 1;
  const jobById = useMemo(() => new Map(jobs.map((j) => [j.id, j])), [jobs]);
  const anyMock = !!config && (config.mock.stt || config.mock.text || config.mock.image);

  // ------------------------------------------------ 이동
  const go = useCallback(
    async (direction: "prev" | "next") => {
      try {
        await api.navigate(sid, { direction });
      } catch (e) {
        notify("error", String((e as Error).message));
      }
    },
    [sid, notify],
  );
  const goTo = useCallback(
    async (slide: Slide) => {
      if (slide.status !== "ready") {
        setSelectedId(slide.id);
        return;
      }
      setSelectedId(null);
      await api.navigate(sid, { slide_id: slide.id }).catch((e) => notify("error", String(e.message)));
    },
    [sid, notify],
  );

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (isTypingTarget(e.target) || e.altKey || e.ctrlKey || e.metaKey) return;
      if (["ArrowRight", "PageDown", " "].includes(e.key)) {
        e.preventDefault();
        void go("next");
      } else if (["ArrowLeft", "PageUp"].includes(e.key)) {
        e.preventDefault();
        void go("prev");
      } else if (e.key === "Escape" && presentMode) {
        void exitPresent();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [go, presentMode]);

  // ------------------------------------------------ 발표 모드 (전체 화면)
  const enterPresent = async () => {
    setPresentMode(true);
    if (session && !session.presenting) void api.patchSession(sid, { presenting: true });
    requestAnimationFrame(() => presentRef.current?.requestFullscreen?.().catch(() => undefined));
  };
  const exitPresent = async () => {
    setPresentMode(false);
    if (document.fullscreenElement) await document.exitFullscreen().catch(() => undefined);
  };
  useEffect(() => {
    const h = () => {
      if (!document.fullscreenElement) setPresentMode(false);
    };
    document.addEventListener("fullscreenchange", h);
    return () => document.removeEventListener("fullscreenchange", h);
  }, []);

  // ------------------------------------------------ 클라이언트 렌더링 지연 (브라우저 단일 시계)
  const pendingRender = useRef(new Map<string, { t0: number; jobId: string }>());
  useEffect(
    () =>
      subscribe((m) => {
        if (m.type === "job.updated" && m.data.status === "ready" && m.data.slide_id)
          pendingRender.current.set(m.data.slide_id, { t0: performance.now(), jobId: m.data.id });
      }),
    [subscribe],
  );
  const onRendered = useCallback(
    (slideId: string) => {
      const p = pendingRender.current.get(slideId);
      if (!p) return;
      pendingRender.current.delete(slideId);
      void api.renderMetric(sid, p.jobId, slideId, performance.now() - p.t0).catch(() => undefined);
    },
    [sid],
  );

  // ------------------------------------------------ 마이크
  const stopMic = useCallback(() => {
    micRef.current?.stop();
    micRef.current = null;
    setMicOn(false);
    sendJson({ type: "mic_stop" });
  }, [sendJson]);
  const startMicClick = async () => {
    setMicErr(null);
    if (conn !== "open") {
      setMicErr("서버와 연결되지 않았습니다. 재연결 후 다시 시도해 주세요.");
      return;
    }
    setMicStarting(true);
    try {
      const h = await startMic(
        (pcm) => sendBinary(pcm),
        (msg) => {
          setMicErr(msg);
          stopMic();
        },
      );
      micRef.current = h;
      setMicOn(true);
      sendJson({ type: "mic_start", sample_rate: TARGET_RATE, encoding: "pcm_s16le", channels: 1, input_rate: h.inputRate });
    } catch (e) {
      setMicErr(e instanceof MicError ? e.message : String(e));
    } finally {
      setMicStarting(false);
    }
  };
  useEffect(() => () => micRef.current?.stop(), []);
  useEffect(() => {
    if (micOn && conn === "closed") setMicErr("서버 연결이 끊겼습니다. 재연결되면 음성 인식이 자동으로 다시 시작됩니다.");
    if (micOn && conn === "open") setMicErr(null);
  }, [conn, micOn]);
  useEffect(() => {
    if (state.stt.state === "error" && micOn) setMicErr(state.stt.message);
  }, [state.stt, micOn]);

  // ------------------------------------------------ 텍스트 입력
  const submitText = async (mode: "detect" | "force") => {
    const text = inputText.trim();
    if (!text) return;
    setBusy(true);
    setInputText(""); // 제출 즉시 비움 (응답 대기 중 새로 입력한 내용을 지우지 않도록)
    try {
      const r = await api.input(sid, text, mode);
      if (mode === "force" && !r.accepted) notify("rejected", "대기열이 가득 차서 요청이 접수되지 않았습니다.");
    } catch (e) {
      setInputText((cur) => cur || text);
      notify("error", String((e as Error).message));
    } finally {
      setBusy(false);
    }
  };

  const act = async (fn: () => Promise<unknown>) => {
    try {
      await fn();
    } catch (e) {
      notify("error", String((e as Error).message));
    }
  };

  const loadMetrics = async () => setMetrics(await api.metrics(sid));

  if (!state.loaded || !session)
    return <div className="center-msg">{conn === "closed" ? "서버에 연결할 수 없습니다. 재연결 중…" : "세션 불러오는 중…"}</div>;

  const visibleJobs = jobs
    .filter((j) => ACTIVE.has(j.status) || j.status === "needs_input" || j.status === "failed")
    .slice(0, 12);
  const recentDone = jobs.filter((j) => j.status === "ready" || j.status === "cancelled").slice(0, 3);
  const previewJob = preview?.job_id ? jobById.get(preview.job_id) : undefined;
  const pendingNoSlide = jobs.filter((j) => (j.status === "queued" || j.status === "planning") && !j.slide_id);

  return (
    <div className="presenter">
      <header className="p-header">
        <div className="p-title">
          <a href="#/" className="home-link" title="세션 목록">
            NextSlide
          </a>
          <strong>{session.title}</strong>
          <span className="muted">· {session.audience}</span>
        </div>
        <div className="p-badges">
          {config && (
            <>
              <ProviderBadge label="STT" mock={config.mock.stt} model={config.stt.model} />
              <ProviderBadge label="텍스트" mock={config.mock.text} model={config.text.model} />
              <ProviderBadge label="이미지" mock={config.mock.image} model={config.image.model} />
            </>
          )}
          <span className={`conn conn-${conn}`}>{conn === "open" ? "연결됨" : conn === "connecting" ? "연결 중" : "끊김"}</span>
        </div>
        <div className="p-actions">
          <button onClick={() => window.open(`#/s/${sid}/audience`, `nextslide-aud-${sid}`, "popup,width=1280,height=760")}>청중 화면 열기</button>
          <button className="primary" onClick={enterPresent}>
            전체 화면 발표
          </button>
        </div>
      </header>
      {anyMock && (
        <div className="banner mock-banner">
          모의 실행(MOCK) 중입니다: {[config!.mock.stt && "음성 인식", config!.mock.text && "슬라이드 기획", config!.mock.image && "이미지 생성"].filter(Boolean).join(", ")}.
          이 결과는 실제 API 호출 결과가 아닙니다.
        </div>
      )}
      {state.credentialProblems.length > 0 && <div className="banner error-banner">{state.credentialProblems.join(" ")}</div>}

      <main className="p-main">
        <section className="stage-col">
          <div className="stage-label">
            현재 슬라이드 {readyIdx >= 0 ? `${readyIdx + 1} / ${readySlides.length}` : ""}
          </div>
          <SlideFrame slide={current} presenterHints />
          <div className="nav-row">
            <button onClick={() => go("prev")} disabled={!canPrev} aria-label="이전 장">
              ◀ 이전
            </button>
            <button onClick={() => go("next")} disabled={!canNext} className="primary" aria-label="다음 장">
              다음 ▶
            </button>
            <label className="toggle" title="발표 중일 때만 자동 전환됩니다">
              <input type="checkbox" checked={session.presenting} onChange={(e) => act(() => api.patchSession(sid, { presenting: e.target.checked }))} />
              발표 중
            </label>
            <label className="toggle" title="이미지까지 준비된 새 장으로 자동 이동 (현재 장이 바로 앞 장일 때만)">
              <input type="checkbox" checked={session.auto_advance} onChange={(e) => act(() => api.patchSession(sid, { auto_advance: e.target.checked }))} />
              생성 완료 시 자동 전환
            </label>
            {current && current.layout !== "cover" && (
              <button className="ghost" onClick={() => setEditing(current)}>
                현재 장 수정
              </button>
            )}
          </div>
          {current?.speaker_notes && <div className="notes"><b>발표자 노트</b> {current.speaker_notes}</div>}

          <div className="strip" aria-label="슬라이드 목록">
            {slides.map((s, i) => (
              <button
                key={s.id}
                className={`thumb ${s.id === current?.id ? "is-current" : ""} ${s.id === selectedId ? "is-selected" : ""} st-${s.status}`}
                onClick={() => goTo(s)}
                title={`${i + 1}. ${s.title} (${STATUS_LABEL[s.status]})`}
              >
                <div className="thumb-frame">
                  <div className="frame">
                    <SlideView slide={s} onRendered={onRendered} />
                  </div>
                </div>
                <span className="thumb-label">
                  {i + 1} {s.status !== "ready" && <em>{STATUS_LABEL[s.status]}</em>}
                </span>
              </button>
            ))}
            {pendingNoSlide.map((j) => (
              <div key={j.id} className="thumb ghost-thumb">
                <div className="thumb-frame placeholder-thumb">{STATUS_LABEL[j.status]}</div>
                <span className="thumb-label">{j.topic ?? "요청"}</span>
              </div>
            ))}
          </div>
        </section>

        <aside className="side-col">
          <Panel title={selectedId ? "선택한 장" : "다음 장 미리보기"} extra={selectedId && <button className="link" onClick={() => setSelectedId(null)}>다음 장 보기</button>}>
            {preview ? (
              <>
                <SlideFrame slide={preview} presenterHints animate={false} onOverflow={setPreviewOverflow} />
                <div className="preview-meta">
                  <span className={`chip st-${preview.status}`}>{STATUS_LABEL[preview.status]}</span>
                  {previewOverflow && <span className="chip warn">텍스트 넘침 — 수정 권장</span>}
                  {preview.is_mock && <span className="chip mock">MOCK 결과</span>}
                  {preview.precision_warning && <span className="chip warn">{preview.precision_warning}</span>}
                  {preview.error && <span className="err">{preview.error}</span>}
                </div>
                <div className="btn-row">
                  {previewJob && ACTIVE.has(previewJob.status) && <button onClick={() => act(() => api.cancel(sid, previewJob.id))}>생성 취소</button>}
                  {previewJob?.status === "failed" && <button onClick={() => act(() => api.retry(sid, previewJob.id))}>재시도</button>}
                  {preview.status === "failed" && preview.title && (
                    <button onClick={() => act(() => api.finalizeWithoutImage(sid, preview.id))}>이미지 없이 완료</button>
                  )}
                  {preview.title && preview.layout !== "cover" && <button className="ghost" onClick={() => setEditing(preview)}>제목·본문 수정</button>}
                  {preview.status === "ready" && <button className="primary" onClick={() => goTo(preview)}>이 장 표시</button>}
                </div>
              </>
            ) : pendingNoSlide.length > 0 ? (
              <div className="empty">다음 장 기획 중… ({STATUS_LABEL[pendingNoSlide[0].status]})</div>
            ) : (
              <div className="empty">아직 다음 장이 없습니다. “다음 슬라이드에서는 …을 설명하겠습니다”라고 말해 보세요.</div>
            )}
          </Panel>

          <Panel title="음성 인식">
            <div className="mic-row">
              {micOn ? (
                <button className="danger" onClick={stopMic}>
                  ■ 마이크 중지
                </button>
              ) : (
                <button className="primary" onClick={startMicClick} disabled={micStarting}>
                  {micStarting ? "마이크 준비 중…" : "● 마이크 시작"}
                </button>
              )}
              <span className={`vad ${state.vadSpeaking ? "on" : ""}`} title="음성 구간 감지">
                {!micOn
                  ? "꺼짐"
                  : state.stt.state === "connecting" || state.stt.state === "reconnecting"
                    ? "STT 연결 중"
                    : state.stt.state === "error"
                      ? "STT 오류"
                      : state.vadSpeaking
                        ? "말하는 중"
                        : state.stt.state === "degraded"
                          ? "STT 경고"
                          : "듣는 중"}
              </span>
              <span className="muted small">{state.stt.message}</span>
            </div>
            {micErr && <div className="err">{micErr}</div>}
            <div className="transcript" aria-live="polite">
              {state.utterances.slice(-10).map((u) => (
                <p key={`${u.id}-${u.segment_id}`} className={`${u.source === "simulated" ? "sim" : ""} ${u.late ? "late" : ""}`}
                  title={u.late ? "순서가 어긋나 늦게 도착한 구간 — 요청 감지에는 사용하지 않음" : undefined}>
                  {u.text}
                </p>
              ))}
              {state.partial && <p className="partial">{state.partial}</p>}
              {state.detectorPending && <p className="pending-flag">요청 문장 감지 중…</p>}
            </div>
          </Panel>

          <Panel title="생성 요청">
            {visibleJobs.length === 0 && recentDone.length === 0 && <div className="empty">대기 중인 요청이 없습니다.</div>}
            {[...visibleJobs, ...recentDone].map((j) => (
              <JobCard
                key={j.id}
                job={j}
                clarifyText={clarify[j.id] ?? ""}
                setClarifyText={(t) => setClarify((c) => ({ ...c, [j.id]: t }))}
                onCancel={() => act(() => api.cancel(sid, j.id))}
                onRetry={() => act(() => api.retry(sid, j.id))}
                onClarify={() => act(async () => {
                  await api.clarify(sid, j.id, clarify[j.id] ?? "");
                  setClarify((c) => ({ ...c, [j.id]: "" }));
                })}
                onDismiss={() => act(() => api.dismiss(sid, j.id))}
              />
            ))}
          </Panel>

          <Panel title="텍스트 입력 (복구·시연용)">
            <textarea
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              rows={3}
              placeholder="예) 다음 슬라이드에서는 과적합을 시험 문제를 외운 학생에 비유해서 설명하겠습니다.  ( | 로 STT 구간 분할 시뮬레이션)"
              onKeyDown={(e) => {
                if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) void submitText("detect");
              }}
            />
            <div className="btn-row">
              <button disabled={busy} onClick={() => submitText("detect")} title="확정 발화로 넣어 요청 감지를 거칩니다 (Ctrl/⌘+Enter)">
                발화로 입력
              </button>
              <button disabled={busy} className="primary" onClick={() => submitText("force")} title="감지 없이 이 텍스트로 바로 다음 장을 생성합니다">
                현재 입력으로 생성
              </button>
            </div>
          </Panel>

          <Panel title="감지·시스템 로그">
            <ul className="log">
              {state.notices.slice(-8).reverse().map((n) => (
                <li key={n.id} className={`log-${n.kind}`}>
                  {n.text}
                </li>
              ))}
            </ul>
          </Panel>

          <Panel title="성능 지표" extra={<button className="link" onClick={loadMetrics}>새로고침</button>}>
            {metrics ? <MetricsView m={metrics} /> : <div className="empty">새로고침을 누르면 이 세션의 측정값을 불러옵니다.</div>}
          </Panel>
        </aside>
      </main>

      {editing && <EditDialog sid={sid} slide={editing} onClose={() => setEditing(null)} />}

      {presentMode && (
        <div className="present" ref={presentRef} onDoubleClick={exitPresent}>
          <SlideFrame slide={current} />
          <div className="present-ctrl">
            <button onClick={() => go("prev")} disabled={!canPrev}>◀</button>
            <span>{readyIdx + 1} / {readySlides.length}</span>
            <button onClick={() => go("next")} disabled={!canNext}>▶</button>
            {nextSlide && nextSlide.status !== "ready" && <span className="chip st-generating_image">다음 장 {STATUS_LABEL[nextSlide.status]}</span>}
            <button onClick={exitPresent}>나가기 (Esc)</button>
          </div>
        </div>
      )}
    </div>
  );
}

function ProviderBadge({ label, mock, model }: { label: string; mock: boolean; model: string }) {
  return (
    <span className={`badge ${mock ? "badge-mock" : "badge-real"}`} title={model}>
      {label}: {mock ? "MOCK" : model}
    </span>
  );
}

function Panel({ title, children, extra }: { title: string; children: React.ReactNode; extra?: React.ReactNode }) {
  return (
    <section className="panel">
      <div className="panel-head">
        <h3>{title}</h3>
        {extra}
      </div>
      {children}
    </section>
  );
}

function JobCard(props: {
  job: Job;
  clarifyText: string;
  setClarifyText: (t: string) => void;
  onCancel: () => void;
  onRetry: () => void;
  onClarify: () => void;
  onDismiss: () => void;
}) {
  const { job } = props;
  return (
    <div className={`job st-${job.status}`}>
      <div className="job-head">
        <span className={`chip st-${job.status}`}>{STATUS_LABEL[job.status]}</span>
        <span className="muted small">
          {job.source === "voice" ? "음성" : job.source === "simulated" ? "발화 입력" : job.source === "clarified" ? "보완" : "텍스트"}
          {job.trigger === "silence" ? " · 침묵 확정" : ""}
          {job.attempt > 1 ? ` · ${job.attempt}회차` : ""}
        </span>
      </div>
      <div className="job-text">{job.topic ? <b>{job.topic}</b> : null} <span className="muted">{job.request_text.split("\n")[0]}</span></div>
      {job.clarification_reason && <div className="warn-text">{job.clarification_reason}</div>}
      {job.error_message && <div className="err">{job.error_message}</div>}
      <div className="btn-row">
        {ACTIVE.has(job.status) && <button onClick={props.onCancel}>취소</button>}
        {job.status === "failed" && <button onClick={props.onRetry}>재시도</button>}
      </div>
      {job.status === "needs_input" && (
        <div className="clarify">
          <input
            value={props.clarifyText}
            onChange={(e) => props.setClarifyText(e.target.value)}
            placeholder="다룰 주제를 입력 (예: 편향과 분산의 트레이드오프)"
            onKeyDown={(e) => {
              if (e.key === "Enter" && props.clarifyText.trim()) props.onClarify();
            }}
          />
          <button className="primary" disabled={!props.clarifyText.trim()} onClick={props.onClarify}>
            생성
          </button>
          <button className="ghost" onClick={props.onDismiss}>
            무시
          </button>
        </div>
      )}
    </div>
  );
}

function EditDialog({ sid, slide, onClose }: { sid: string; slide: Slide; onClose: () => void }) {
  const [title, setTitle] = useState(slide.title);
  const [bullets, setBullets] = useState(slide.bullets.join("\n"));
  const [err, setErr] = useState<string | null>(null);
  const save = async () => {
    try {
      await api.editSlide(sid, slide.id, { title, bullets: bullets.split("\n").map((b) => b.trim()).filter(Boolean) });
      onClose();
    } catch (e) {
      setErr(String((e as Error).message));
    }
  };
  return (
    <div className="modal-back" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()} role="dialog" aria-label="슬라이드 수정">
        <h3>제목·본문 수정</h3>
        <label>
          제목 <span className="muted small">{title.length}/40</span>
          <input value={title} maxLength={40} onChange={(e) => setTitle(e.target.value)} />
        </label>
        <label>
          핵심 문장 (한 줄에 하나, 최대 3개, 각 70자)
          <textarea rows={4} value={bullets} onChange={(e) => setBullets(e.target.value)} />
        </label>
        {err && <div className="err">{err}</div>}
        <div className="btn-row">
          <button className="ghost" onClick={onClose}>
            취소
          </button>
          <button className="primary" onClick={save}>
            저장
          </button>
        </div>
      </div>
    </div>
  );
}

function MetricsView({ m }: { m: Record<string, any> }) {
  const d = m.durations_ms as Record<string, any>;
  return (
    <div className="metrics">
      <table>
        <thead>
          <tr>
            <th>구간</th>
            <th>n</th>
            <th>평균</th>
            <th>중앙값</th>
            <th>p95</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(d).map(([k, v]) => (
            <tr key={k}>
              <td>{v.label}</td>
              <td>{v.n}</td>
              <td>{v.mean ?? "–"}</td>
              <td>{v.median ?? "–"}</td>
              <td>{v.p95 ?? "–"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="small">
        단위 ms. 작업 {m.jobs_total}건, 상태 {JSON.stringify(m.status_counts)}. 실패율{" "}
        {m.failure_rate.rate === null ? "–" : `${(m.failure_rate.rate * 100).toFixed(1)}%`} ({m.failure_rate.failed}/{m.failure_rate.finished}).
        텍스트 입력 경로 {m.speech_end_not_computable_jobs}건은 발화 종료 기준 지연을 계산할 수 없습니다.
      </p>
      <p className="small muted">
        비용 추정: {m.usage.cost_estimate_usd === null ? "단가 미설정 또는 MOCK → 계산하지 않음" : `$${m.usage.cost_estimate_usd}`} · {m.usage.cost_note}
      </p>
    </div>
  );
}
