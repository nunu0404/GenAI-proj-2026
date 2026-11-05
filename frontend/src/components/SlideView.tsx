import { useEffect, useLayoutEffect, useRef, useState } from "react";
import type { Slide } from "../api";
import { STATUS_LABEL } from "../api";

interface Props {
  slide: Slide;
  /** 발표자 화면에서만 true: 생성 상태·경고 표시 */
  presenterHints?: boolean;
  onOverflow?: (overflow: boolean) => void;
  onRendered?: (slideId: string) => void;
  className?: string;
}

/**
 * 구조화된 슬라이드 데이터 → 미리 구현한 템플릿. AI 가 만든 HTML/JS 는 렌더링하지 않는다
 * (모든 텍스트는 React 텍스트 노드로만 출력).
 * 크기는 컨테이너 너비 기준(cqw)으로 계산해 어떤 크기의 16:9 프레임에서도 같은 배치를 유지한다.
 */
export function SlideView({ slide, presenterHints, onOverflow, onRendered, className }: Props) {
  const textRef = useRef<HTMLDivElement>(null);
  const titleRef = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(1);
  const [overflow, setOverflow] = useState(false);

  // 텍스트가 넘치면 글자 크기를 단계적으로 줄이고(최소 80%), 그래도 넘치면 경고 표시
  useEffect(() => setScale(1), [slide.id, slide.title, slide.bullets.join("\n")]);
  useLayoutEffect(() => {
    const els = [textRef.current, titleRef.current].filter(Boolean) as HTMLElement[];
    if (!els.length) return;
    const over = els.some((el) => el.scrollHeight > el.clientHeight + 1 || el.scrollWidth > el.clientWidth + 1);
    if (over && scale > 0.8) {
      setScale((s) => Math.round((s - 0.05) * 100) / 100);
      return;
    }
    setOverflow(over);
    onOverflow?.(over);
  }, [scale, slide.title, slide.bullets, onOverflow]);

  const hasImage = !!slide.image_url;
  useEffect(() => {
    if (!onRendered) return;
    if (slide.status !== "ready") return;
    if (!hasImage) requestAnimationFrame(() => onRendered(slide.id));
  }, [slide.id, slide.status, hasImage, onRendered]);

  const style = { ["--fit" as any]: scale } as React.CSSProperties;

  if (slide.layout === "cover") {
    return (
      <div className={`slide slide-cover ${className ?? ""}`} style={style}>
        <div className="cover-band" />
        <div className="cover-text" ref={textRef}>
          <h1 className="cover-title">{slide.title}</h1>
          {slide.bullets.map((b, i) => (
            <p className="cover-sub" key={i}>
              {b}
            </p>
          ))}
        </div>
      </div>
    );
  }

  const pending = slide.status !== "ready";
  return (
    <div className={`slide slide-tbi ${className ?? ""}`} style={style}>
      <div className="tbi-head" ref={titleRef}>
        <h2 className="tbi-title">{slide.title || (presenterHints ? "제목 생성 중…" : "")}</h2>
      </div>
      <div className="tbi-text" ref={textRef}>
        <ul className="tbi-bullets">
          {slide.bullets.map((b, i) => (
            <li key={i}>{b}</li>
          ))}
        </ul>
      </div>
      <div className="tbi-image">
        {hasImage ? (
          <img
            src={slide.image_url!}
            alt={slide.image_alt}
            draggable={false}
            onLoad={() => onRendered && requestAnimationFrame(() => onRendered(slide.id))}
          />
        ) : presenterHints ? (
          <div className={`img-placeholder ${slide.status === "generating_image" ? "shimmer" : ""}`}>
            <span>
              {slide.status === "failed"
                ? "이미지 생성 실패"
                : slide.status === "ready"
                  ? "이미지 없음"
                  : STATUS_LABEL[slide.status] ?? slide.status}
            </span>
          </div>
        ) : (
          <div className="img-placeholder quiet" />
        )}
      </div>
      {presenterHints && (pending || overflow || slide.is_mock) && (
        <div className="slide-hints">
          {pending && <span className={`chip st-${slide.status}`}>{STATUS_LABEL[slide.status]}</span>}
          {overflow && <span className="chip warn">텍스트 넘침</span>}
          {slide.is_mock && <span className="chip mock">MOCK</span>}
        </div>
      )}
    </div>
  );
}

/** 16:9 고정 비율 프레임. 슬라이드 전환 시 짧은 페이드. */
export function SlideFrame({ slide, presenterHints, onRendered, animate = true, onOverflow }: {
  slide: Slide | null | undefined;
  presenterHints?: boolean;
  onRendered?: (id: string) => void;
  animate?: boolean;
  onOverflow?: (o: boolean) => void;
}) {
  return (
    <div className="frame">
      {slide ? (
        <div key={slide.id} className={animate ? "frame-anim" : "frame-static"}>
          <SlideView slide={slide} presenterHints={presenterHints} onRendered={onRendered} onOverflow={onOverflow} />
        </div>
      ) : (
        <div className="frame-empty" />
      )}
    </div>
  );
}
