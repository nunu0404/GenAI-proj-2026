import { useEffect, useState } from "react";
import { SlideFrame } from "../components/SlideView";
import { useSessionSocket } from "../useSessionSocket";

/** 청중 화면: 완성된 슬라이드만, 발표자가 고른 장을 16:9 로 표시. 자막·로그·API 상태는 노출하지 않는다. */
export function Audience({ sid }: { sid: string }) {
  const { state } = useSessionSocket(sid, "audience");
  const [idle, setIdle] = useState(false);

  useEffect(() => {
    let t: number | undefined;
    const wake = () => {
      setIdle(false);
      window.clearTimeout(t);
      t = window.setTimeout(() => setIdle(true), 2000);
    };
    wake();
    window.addEventListener("mousemove", wake);
    return () => {
      window.removeEventListener("mousemove", wake);
      window.clearTimeout(t);
    };
  }, []);

  useEffect(() => {
    if (state.session?.title) document.title = state.session.title;
  }, [state.session?.title]);

  // 서버가 청중에게 보낼 수 있는 장만 보내므로(완성 장 + 옵션에 따라 그림 준비 중인 그림형 장) id 로 찾는다
  const slide = state.slides.find((s) => s.id === state.session?.current_slide_id);
  return (
    <div
      className={`audience ${idle ? "idle" : ""}`}
      onDoubleClick={() => (document.fullscreenElement ? document.exitFullscreen() : document.documentElement.requestFullscreen()).catch(() => undefined)}
    >
      <div className="audience-stage">{slide ? <SlideFrame slide={slide} /> : <div className="audience-wait">{state.loaded ? "" : "연결 중…"}</div>}</div>
    </div>
  );
}
