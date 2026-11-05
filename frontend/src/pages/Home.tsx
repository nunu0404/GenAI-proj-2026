import { useEffect, useState } from "react";
import { api, type PublicConfig, type Session } from "../api";

export function Home() {
  const [sessions, setSessions] = useState<Session[] | null>(null);
  const [config, setConfig] = useState<(PublicConfig & { credential_problems: string[] }) | null>(null);
  const [title, setTitle] = useState("머신러닝 기초");
  const [audience, setAudience] = useState("대학 신입생");
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api.listSessions().then(setSessions).catch((e) => setErr(`서버 연결 실패: ${e.message}`));
    fetch("/api/config").then((r) => r.json()).then(setConfig).catch(() => undefined);
  }, []);

  const create = async () => {
    try {
      const s = await api.createSession(title.trim(), audience.trim());
      location.hash = `#/s/${s.id}`;
    } catch (e) {
      setErr(String((e as Error).message));
    }
  };

  return (
    <div className="home">
      <header className="home-head">
        <h1>NextSlide</h1>
        <p>말하면 만들어지는 다음 슬라이드</p>
      </header>
      {config && (config.mock.stt || config.mock.text || config.mock.image) && (
        <div className="banner mock-banner">
          모의 실행(MOCK) 구성: STT {config.mock.stt ? "MOCK" : config.stt.model} · 텍스트 {config.mock.text ? "MOCK" : config.text.model} · 이미지{" "}
          {config.mock.image ? "MOCK" : config.image.model}
        </div>
      )}
      {config?.credential_problems?.length ? <div className="banner error-banner">{config.credential_problems.join(" ")}</div> : null}
      <section className="panel home-card">
        <h3>새 강의 세션</h3>
        <label>
          강의 제목
          <input value={title} maxLength={80} onChange={(e) => setTitle(e.target.value)} />
        </label>
        <label>
          청중 수준
          <input value={audience} maxLength={80} onChange={(e) => setAudience(e.target.value)} />
        </label>
        <button className="primary" disabled={!title.trim() || !audience.trim()} onClick={create}>
          세션 시작
        </button>
        {err && <div className="err">{err}</div>}
      </section>
      <section className="panel home-card">
        <h3>저장된 세션</h3>
        {sessions === null ? (
          <div className="empty">불러오는 중…</div>
        ) : sessions.length === 0 ? (
          <div className="empty">저장된 세션이 없습니다.</div>
        ) : (
          <ul className="session-list">
            {sessions.map((s) => (
              <li key={s.id}>
                <div>
                  <b>{s.title}</b> <span className="muted">· {s.audience} · {s.slide_count ?? 0}장 · {new Date(s.updated_at * 1000).toLocaleString()}</span>
                </div>
                <div className="btn-row">
                  <a className="btn primary" href={`#/s/${s.id}`}>
                    발표자 화면
                  </a>
                  <a className="btn" href={`#/s/${s.id}/audience`} target="_blank" rel="noreferrer">
                    청중 화면
                  </a>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
