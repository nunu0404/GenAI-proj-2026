import katex from "katex";
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import type { Equation, Slide } from "../api";
import { ChartPanel, ComparisonPanel, TablePanel } from "./Visuals";
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
  const eqRef = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(1);
  const [overflow, setOverflow] = useState(false);

  // 텍스트가 넘치면 글자 크기를 단계적으로 줄이고(최소 80%), 그래도 넘치면 경고 표시
  useEffect(() => setScale(1), [slide.id, slide.title, slide.bullets.join("\n"), JSON.stringify(slide.equations ?? [])]);
  useLayoutEffect(() => {
    const els = [textRef.current, titleRef.current, eqRef.current].filter(Boolean) as HTMLElement[];
    if (!els.length) return;
    const over = els.some((el) => el.scrollHeight > el.clientHeight + 1 || el.scrollWidth > el.clientWidth + 1);
    if (over && scale > 0.8) {
      setScale((s) => Math.round((s - 0.05) * 100) / 100);
      return;
    }
    setOverflow(over);
    onOverflow?.(over);
  }, [scale, slide.title, slide.bullets, slide.equations, slide.layout, onOverflow]);

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

  if ((slide.layout === "title_comparison" || slide.layout === "title_table" || slide.layout === "title_chart") && slide.visual) {
    const v = slide.visual;
    return (
      <div className={`slide slide-sv sv-${v.type} ${className ?? ""}`} style={style}>
        <div className="tbi-head" ref={titleRef}>
          <h2 className="tbi-title">{slide.title}</h2>
        </div>
        <div className="sv-main" ref={eqRef}>
          {v.type === "comparison" && <ComparisonPanel v={v} />}
          {v.type === "table" && <TablePanel v={v} />}
          {v.type === "chart" && <ChartPanel v={v} />}
        </div>
        <div className="sv-take" ref={textRef}>
          <ul className="tbi-bullets">
            {slide.bullets.map((b, i) => (
              <li key={i}>
                <MathText text={b} />
              </li>
            ))}
          </ul>
        </div>
        {presenterHints && (pending || overflow || slide.is_mock) && (
          <div className="slide-hints">
            {pending && <span className={`chip st-${slide.status}`}>{STATUS_LABEL[slide.status]}</span>}
            {overflow && <span className="chip warn">내용 넘침</span>}
            {slide.is_mock && <span className="chip mock">MOCK</span>}
          </div>
        )}
      </div>
    );
  }

  if (slide.layout === "title_bullets" || slide.layout === "title_bullets_equation") {
    const isEq = slide.layout === "title_bullets_equation";
    const hasEqError = isEq && (slide.equations ?? []).some((e) => latexError(e.latex));
    return (
      <div className={`slide ${isEq ? "slide-tbe" : "slide-tb"} ${className ?? ""}`} style={style}>
        <div className="tbi-head" ref={titleRef}>
          <h2 className="tbi-title">{slide.title}</h2>
        </div>
        <div className="tbi-text" ref={textRef}>
          <ul className="tbi-bullets">
            {slide.bullets.map((b, i) => (
              <li key={i}>
                <MathText text={b} />
              </li>
            ))}
          </ul>
        </div>
        {isEq && (
          <div className={`tbe-eqs ${(slide.equations ?? []).length > 1 ? "steps" : ""}`} ref={eqRef}>
            {(slide.equations ?? []).map((e, i, all) => (
              <div key={i} className="eq-step">
                {all.length > 1 && <span className="eq-step-no">{i + 1}</span>}
                <EquationBlock eq={e} />
              </div>
            ))}
          </div>
        )}
        {presenterHints && (pending || overflow || slide.is_mock || hasEqError) && (
          <div className="slide-hints">
            {pending && <span className={`chip st-${slide.status}`}>{STATUS_LABEL[slide.status]}</span>}
            {overflow && <span className="chip warn">텍스트 넘침</span>}
            {hasEqError && <span className="chip warn">수식 오류</span>}
            {slide.is_mock && <span className="chip mock">MOCK</span>}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className={`slide slide-tbi ${className ?? ""}`} style={style}>
      <div className="tbi-head" ref={titleRef}>
        <h2 className="tbi-title">{slide.title || (presenterHints ? "제목 생성 중…" : "")}</h2>
      </div>
      <div className="tbi-text" ref={textRef}>
        <ul className="tbi-bullets">
          {slide.bullets.map((b, i) => (
            <li key={i}>
              <MathText text={b} />
            </li>
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

const KATEX_OPTS = { displayMode: true, throwOnError: true, trust: false, strict: "ignore" as const };

function latexError(latex: string): string | null {
  try {
    katex.renderToString(latex, KATEX_OPTS);
    return null;
  } catch (e) {
    return String((e as Error).message ?? e);
  }
}

/**
 * LaTeX → KaTeX 렌더링 (trust=false: \href 등 외부 리소스·HTML 명령 비활성).
 * 모델이 만든 HTML 을 실행하는 것이 아니라, LaTeX 문자열을 KaTeX 가 조판한다. 오류면 원문을 그대로 보여 준다.
 */
export function EquationBlock({ eq }: { eq: Equation }) {
  const html = useMemo(() => {
    try {
      return katex.renderToString(eq.latex, KATEX_OPTS);
    } catch {
      return null;
    }
  }, [eq.latex]);
  return (
    <figure className="eq">
      {html ? (
        <div className="eq-math" dangerouslySetInnerHTML={{ __html: html }} />
      ) : (
        <code className="eq-raw">{eq.latex}</code>
      )}
      {eq.caption && (
        <figcaption className="eq-cap">
          <MathText text={eq.caption} />
        </figcaption>
      )}
    </figure>
  );
}

/** 글 속의 인라인 수식($…$, \(…\))만 KaTeX 로 렌더링하고 나머지는 일반 텍스트로 출력한다. */
export function MathText({ text }: { text: string }) {
  const parts = useMemo(() => {
    const out: { math: boolean; s: string; html?: string | null }[] = [];
    // 지원 형식: $…$, \(…\), 그리고 이스케이프가 깨져 남은 (\cmd…) 형태
    const re = /\$([^$\n]+?)\$|\\\((.+?)\\\)|\\?\((\\[a-zA-Z][^()]*)\)/g;
    let last = 0;
    let m: RegExpExecArray | null;
    while ((m = re.exec(text))) {
      if (m.index > last) out.push({ math: false, s: text.slice(last, m.index) });
      let html: string | null = null;
      try {
        const src = (m[1] ?? m[2] ?? m[3] ?? "").replace(/\\\\(?=[a-zA-Z])/g, "\\"); // 이중 이스케이프 보정
        // '$5와 $10' 같은 금액 표기는 수식으로 보지 않는다
        if (m[1] !== undefined && /^\d[\d.,]*\s/.test(src)) throw new Error("not math");
        html = katex.renderToString(src, { ...KATEX_OPTS, displayMode: false });
      } catch {
        html = null;
      }
      out.push({ math: true, s: m[0], html });
      last = m.index + m[0].length;
    }
    if (last < text.length) out.push({ math: false, s: text.slice(last) });
    return out;
  }, [text]);
  return (
    <>
      {parts.map((p, i) =>
        p.math && p.html ? <span key={i} className="mt-math" dangerouslySetInnerHTML={{ __html: p.html }} /> : <span key={i}>{p.s}</span>,
      )}
    </>
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
