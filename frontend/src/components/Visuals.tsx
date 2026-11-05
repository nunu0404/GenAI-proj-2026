import type { ChartVisual, ComparisonVisual, TableVisual } from "../api";
import { MathText } from "./SlideView";

/* 비교·표·그래프는 모두 구조화된 데이터 → 고정 컴포넌트로 그린다 (모델이 만든 HTML/이미지 사용 안 함). */

export function ComparisonPanel({ v }: { v: ComparisonVisual }) {
  return (
    <div className="cmp">
      {(["left", "right"] as const).map((side, i) => (
        <section key={side} className={`cmp-card cmp-${side}`}>
          <h3 className="cmp-title">
            <span className={`cmp-swatch s${i + 1}`} aria-hidden />
            <MathText text={v[side].title} />
          </h3>
          <ul className="cmp-points">
            {v[side].points.map((p, k) => (
              <li key={k}>
                <MathText text={p} />
              </li>
            ))}
          </ul>
        </section>
      ))}
      <div className="cmp-vs" aria-hidden>
        VS
      </div>
    </div>
  );
}

export function TablePanel({ v }: { v: TableVisual }) {
  return (
    <table className="stable">
      <thead>
        <tr>
          {v.columns.map((c, i) => (
            <th key={i}>
              <MathText text={c} />
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {v.rows.map((r, i) => (
          <tr key={i}>
            {r.map((c, k) => (
              <td key={k}>
                <MathText text={c} />
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

// ------------------------------------------------------------------ 그래프 (SVG)
const W = 1040;
const H = 430;
const M = { l: 70, r: 118, t: 34, b: 58 };
const PW = W - M.l - M.r;
const PH = H - M.t - M.b;

/** 1·2·5 × 10^k 간격의 보기 좋은 눈금 */
function niceTicks(lo: number, hi: number, count = 5): number[] {
  if (!(hi > lo)) {
    hi = lo + 1;
  }
  const raw = (hi - lo) / count;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => (hi - lo) / s <= count + 0.5) ?? 10 * mag;
  const start = Math.floor(lo / step + 1e-9) * step;
  const end = Math.ceil(hi / step - 1e-9) * step; // 최댓값을 덮는 다음 눈금까지
  const out: number[] = [];
  for (let k = 0; start + k * step <= end + step * 1e-9; k++) out.push(Math.round((start + k * step) / step) * step);
  return out;
}

const fmt = (n: number) => {
  const a = Math.abs(n);
  if (a !== 0 && (a >= 1e5 || a < 1e-3)) return n.toExponential(1);
  return String(Math.round(n * 1000) / 1000);
};

export function ChartPanel({ v }: { v: ChartVisual }) {
  const isFn = v.kind === "function";
  const series = isFn
    ? (v.computed ?? []).map((c) => ({ name: c.label, pts: c.points.map((p) => [Number(p[0]), p[1] ?? null] as [number, number | null]) }))
    : v.series.map((s) => ({ name: s.name, pts: s.values.map((y, i) => [i, y] as [number, number | null]) }));
  const ys = series.flatMap((s) => s.pts.map((p) => p[1]).filter((y): y is number => y !== null));
  let yLo = Math.min(...ys);
  let yHi = Math.max(...ys);
  if (v.kind === "bar") {
    yLo = Math.min(0, yLo);
    yHi = Math.max(0, yHi);
  }
  if (yHi - yLo < 1e-9) {
    yLo -= 1;
    yHi += 1;
  }
  const yt = niceTicks(yLo, yHi);
  const y0 = Math.min(yt[0], yLo);
  const y1 = Math.max(yt[yt.length - 1], yHi);
  const sy = (y: number) => M.t + PH - ((y - y0) / (y1 - y0)) * PH;

  const n = v.categories.length;
  const xLo = isFn ? (v.x_min ?? 0) : 0;
  const xHi = isFn ? (v.x_max ?? 1) : Math.max(1, n - 1);
  const band = n ? PW / n : PW;
  const sx = (x: number) =>
    isFn ? M.l + ((x - xLo) / (xHi - xLo)) * PW : v.kind === "bar" ? M.l + band * (x + 0.5) : M.l + (n > 1 ? (x / (n - 1)) * PW : PW / 2);
  const xt = isFn ? niceTicks(xLo, xHi, 6).filter((t) => t >= xLo - 1e-9 && t <= xHi + 1e-9) : [];

  const pathOf = (pts: [number, number | null][]) => {
    let d = "";
    let pen = false;
    for (const p of pts) {
      if (p[1] === null || p[1] < y0 - (y1 - y0) || p[1] > y1 + (y1 - y0)) {
        pen = false;
        continue;
      }
      d += `${pen ? "L" : "M"}${sx(p[0]).toFixed(1)},${sy(p[1]).toFixed(1)}`;
      pen = true;
    }
    return d;
  };

  const zeroInside = y0 < 0 && y1 > 0;
  const groupW = band * 0.72;
  const barW = series.length ? (groupW - 2 * (series.length - 1)) / series.length : groupW;

  return (
    <figure className="chart">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${v.y_label || "값"} 그래프`}>
        {series.length >= 2 && (
          <g className="ch-legend" transform={`translate(${M.l},14)`}>
            {series.map((s, i) => (
              <g key={i} transform={`translate(${i * 170},0)`}>
                <rect x={0} y={-9} width={14} height={14} rx={3} className={`fill-s${i + 1}`} />
                <text x={20} y={2}>
                  {s.name}
                </text>
              </g>
            ))}
          </g>
        )}
        {yt.map((t) => (
          <g key={`y${t}`}>
            <line x1={M.l} x2={M.l + PW} y1={sy(t)} y2={sy(t)} className="ch-grid" />
            <text x={M.l - 10} y={sy(t) + 5} className="ch-tick" textAnchor="end">
              {fmt(t)}
            </text>
          </g>
        ))}
        {zeroInside && <line x1={M.l} x2={M.l + PW} y1={sy(0)} y2={sy(0)} className="ch-zero" />}
        {isFn && xLo < 0 && xHi > 0 && <line x1={sx(0)} x2={sx(0)} y1={M.t} y2={M.t + PH} className="ch-zero" />}
        <line x1={M.l} x2={M.l + PW} y1={M.t + PH} y2={M.t + PH} className="ch-axis" />
        {isFn
          ? xt.map((t) => (
              <text key={`x${t}`} x={sx(t)} y={M.t + PH + 22} className="ch-tick" textAnchor="middle">
                {fmt(t)}
              </text>
            ))
          : v.categories.map((c, i) => (
              <text key={`c${i}`} x={sx(i)} y={M.t + PH + 22} className="ch-tick" textAnchor="middle">
                {c}
              </text>
            ))}
        {v.x_label && (
          <text x={M.l + PW / 2} y={H - 8} className="ch-label" textAnchor="middle">
            {v.x_label}
          </text>
        )}
        {v.y_label && (
          <text transform={`translate(18,${M.t + PH / 2}) rotate(-90)`} className="ch-label" textAnchor="middle">
            {v.y_label}
          </text>
        )}

        {v.kind === "bar"
          ? series.map((s, si) =>
              s.pts.map(([x, y]) => {
                if (y === null) return null;
                const left = sx(x) - groupW / 2 + si * (barW + 2);
                const top = sy(Math.max(0, y));
                const bottom = sy(Math.min(0, y));
                const h = Math.max(1, bottom - top);
                const r = Math.min(4, barW / 2, h);
                // 데이터 쪽 끝만 둥글게 (기준선 쪽은 직각)
                const d =
                  y >= 0
                    ? `M${left},${bottom}V${top + r}Q${left},${top} ${left + r},${top}H${left + barW - r}Q${left + barW},${top} ${left + barW},${top + r}V${bottom}Z`
                    : `M${left},${top}V${bottom - r}Q${left},${bottom} ${left + r},${bottom}H${left + barW - r}Q${left + barW},${bottom} ${left + barW},${bottom - r}V${top}Z`;
                return (
                  <path key={`${si}-${x}`} d={d} className={`fill-s${si + 1} ch-bar`}>
                    <title>{`${s.name} · ${v.categories[x]}: ${fmt(y)}`}</title>
                  </path>
                );
              }),
            )
          : series.map((s, si) => (
              <g key={si}>
                <path d={pathOf(s.pts)} className={`ch-line stroke-s${si + 1}`} />
                {(isFn ? s.pts.filter((_, k) => k % 12 === 0) : s.pts).map(([x, y], k) =>
                  y === null ? null : (
                    <circle
                      key={k}
                      cx={sx(x)}
                      cy={sy(y)}
                      r={isFn ? 9 : 5.5}
                      className={isFn ? "ch-hit" : `ch-dot fill-s${si + 1}`}
                    >
                      <title>{`${s.name} · ${isFn ? `x=${fmt(x)}` : v.categories[x]}: ${fmt(y)}`}</title>
                    </circle>
                  ),
                )}
              </g>
            ))}

        {/* 선 끝 직접 라벨: 본문 색 글자. 끝점이 가까우면 세로로 벌려 겹치지 않게 한다 */}
        {v.kind !== "bar" &&
          series.length <= 4 &&
          (() => {
            const labels = series
              .map((s, si) => {
                const last = [...s.pts].reverse().find((p) => p[1] !== null && p[1] >= y0 && p[1] <= y1);
                return last && last[1] !== null ? { si, name: s.name, x: sx(last[0]), y: sy(last[1]), ly: sy(last[1]) } : null;
              })
              .filter((l): l is { si: number; name: string; x: number; y: number; ly: number } => l !== null)
              .sort((a, b) => a.y - b.y);
            for (let i = 1; i < labels.length; i++) labels[i].ly = Math.max(labels[i].ly, labels[i - 1].ly + 22);
            return labels.map((l) => (
              <g key={`lbl${l.si}`}>
                {isFn && <circle cx={l.x + 12} cy={l.ly} r={4} className={`fill-s${l.si + 1}`} />}
                <text x={l.x + (isFn ? 20 : 12)} y={l.ly + 5} className="ch-direct">
                  {l.name}
                </text>
              </g>
            ));
          })()}
      </svg>
      {v.note && <figcaption className="ch-note">{v.note}</figcaption>}
    </figure>
  );
}
