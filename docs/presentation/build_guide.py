"""NextSlide 해설서(HTML 한 파일) 생성.

실행: python3 docs/presentation/build_guide.py
결과: docs/presentation/NextSlide_guide.html (그림을 base64로 넣은 단일 파일, 오프라인에서도 열림)

- 수치는 모두 저장소의 실험 기록(docs/diffusion-experiments.md, docs/results.md, eval/results/…)에서 옮겼다.
- 발표 대본·시연·예상 질문은 script.md(= build_deck.js 가 만든 파일)를 읽어 넣는다.
"""
from __future__ import annotations

import base64
import html
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
OUT = HERE / "NextSlide_guide.html"


# ───────────────────────── 도우미 ─────────────────────────
def esc(s: str) -> str:
    return html.escape(s, quote=True)


def md_inline(s: str) -> str:
    s = esc(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)
    return s


def b64(path: Path) -> str:
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()


def figure(rel: str, alt: str, cap: str = "", cls: str = "") -> str:
    p = ROOT / rel
    c = f"<figcaption>{cap}</figcaption>" if cap else ""
    return f'<figure class="{cls}"><img src="{b64(p)}" alt="{esc(alt)}" decoding="async" data-zoom>{c}</figure>'


# ───────────────────────── 차트 (인라인 SVG) ─────────────────────────
def line_chart(title, cats, vals, lo=None, hi=None, ymin=0, ymax=1, fmt="{:.1f}", series_cls="s-teal",
               ytick=1.0, xlabel="CFG 스케일", tip=""):
    W, H, L, R, T, B = 480, 290, 46, 16, 34, 46
    pw, ph = W - L - R, H - T - B
    xs = [L + pw * (i + 0.5) / len(cats) for i in range(len(cats))]
    y = lambda v: T + ph * (1 - (v - ymin) / (ymax - ymin))  # noqa: E731
    o = [f'<svg class="chart" viewBox="0 0 {W} {H}" role="img" aria-label="{esc(title)}">',
         f'<text class="c-title" x="{L}" y="18">{esc(title)}</text>']
    v = ymin
    while v <= ymax + 1e-9:
        o.append(f'<line class="c-grid" x1="{L}" x2="{W-R}" y1="{y(v):.1f}" y2="{y(v):.1f}"/>'
                 f'<text class="c-tick" x="{L-8}" y="{y(v)+4:.1f}" text-anchor="end">{fmt.format(v)}</text>')
        v += ytick
    o.append(f'<line class="c-axis" x1="{L}" x2="{W-R}" y1="{T+ph}" y2="{T+ph}"/>')
    for i, c in enumerate(cats):
        o.append(f'<text class="c-tick" x="{xs[i]:.1f}" y="{T+ph+18}" text-anchor="middle">{esc(str(c))}</text>')
    o.append(f'<text class="c-tick" x="{L+pw/2:.1f}" y="{H-6}" text-anchor="middle">{esc(xlabel)}</text>')
    if lo:
        for i in range(len(cats)):
            o.append(f'<line class="c-ci {series_cls}" x1="{xs[i]:.1f}" x2="{xs[i]:.1f}" y1="{y(lo[i]):.1f}" y2="{y(hi[i]):.1f}"/>')
    pts = " ".join(f"{xs[i]:.1f},{y(vals[i]):.1f}" for i in range(len(cats)))
    o.append(f'<polyline class="c-line {series_cls}" points="{pts}"/>')
    for i, c in enumerate(cats):
        t = f"{xlabel} {c}: {fmt.format(vals[i])}" + (f" (95% CI {fmt.format(lo[i])}–{fmt.format(hi[i])})" if lo else "") + tip
        o.append(f'<g class="c-pt"><title>{esc(t)}</title><circle class="c-hit" cx="{xs[i]:.1f}" cy="{y(vals[i]):.1f}" r="14"/>'
                 f'<circle class="c-dot {series_cls}" cx="{xs[i]:.1f}" cy="{y(vals[i]):.1f}" r="5"/></g>')
        ly = y(hi[i]) - 7 if lo else y(vals[i]) - 10
        o.append(f'<text class="c-val" x="{xs[i]+(10 if lo else 0):.1f}" y="{ly:.1f}" text-anchor="{"start" if lo else "middle"}">{fmt.format(vals[i])}</text>')
    o.append("</svg>")
    return "".join(o)


def hbar_chart(title, rows, unit=" 초", vmax=12.0):
    """rows: (label, value, cls)"""
    W, L, R, T, rh = 560, 190, 60, 30, 40
    H = T + rh * len(rows) + 10
    pw = W - L - R
    o = [f'<svg class="chart" viewBox="0 0 {W} {H}" role="img" aria-label="{esc(title)}">',
         f'<text class="c-title" x="0" y="18">{esc(title)}</text>']
    for i, (lab, v, cls) in enumerate(rows):
        y0 = T + i * rh
        w = max(2.0, pw * v / vmax)
        o.append(f'<g><title>{esc(lab)}: {v}{unit}</title>'
                 f'<text class="c-tick" x="{L-10}" y="{y0+rh/2+4:.1f}" text-anchor="end">{esc(lab)}</text>'
                 f'<rect class="c-bar {cls}" x="{L}" y="{y0+8}" width="{w:.1f}" height="{rh-16}" rx="4"/>'
                 f'<text class="c-val" x="{L+w+6:.1f}" y="{y0+rh/2+4:.1f}">{v}{unit}</text></g>')
    o.append(f'<line class="c-axis" x1="{L}" x2="{L}" y1="{T}" y2="{T+rh*len(rows)}"/></svg>')
    return "".join(o)


def stacked_latency():
    rows = [("gpt-image-2 경로 (11-05)", [("기획", 5.7), ("그림", 14.3)], 20.0),
            ("로컬 SD-Turbo 경로 (11-17)", [("기획", 5.0), ("그림", 1.2)], 6.2)]
    W, L, R, T, rh, vmax = 600, 190, 70, 34, 46, 21.0
    pw = W - L - R
    H = T + rh * len(rows) + 40
    o = [f'<svg class="chart" viewBox="0 0 {W} {H}" role="img" aria-label="요청 확정부터 완성까지 걸린 시간">',
         '<text class="c-title" x="0" y="18">요청 확정 → 슬라이드 완성 (각 1회 측정, 텍스트 입력 경로)</text>']
    for i, (lab, segs, tot) in enumerate(rows):
        y0 = T + i * rh
        x = L
        o.append(f'<text class="c-tick" x="{L-10}" y="{y0+rh/2+4:.1f}" text-anchor="end">{esc(lab)}</text>')
        for name, v in segs:
            w = pw * v / vmax
            cls = "s-navy" if name == "기획" else "s-teal"
            o.append(f'<g><title>{esc(lab)} · {name} {v}초</title><rect class="c-bar {cls}" x="{x:.1f}" y="{y0+8}" '
                     f'width="{max(w-2,1):.1f}" height="{rh-16}" rx="4"/></g>')
            if w > 38:
                o.append(f'<text class="c-inbar" x="{x+w/2-1:.1f}" y="{y0+rh/2+4:.1f}" text-anchor="middle">{name} {v}</text>')
            x += w
        o.append(f'<text class="c-val" x="{x+6:.1f}" y="{y0+rh/2+4:.1f}"><tspan font-weight="700">{tot}초</tspan></text>')
    ly = T + rh * len(rows) + 22
    o.append(f'<rect class="c-bar s-navy" x="{L}" y="{ly-10}" width="12" height="12" rx="2"/><text class="c-tick" x="{L+18}" y="{ly}">기획 LLM (텍스트)</text>'
             f'<rect class="c-bar s-teal" x="{L+150}" y="{ly-10}" width="12" height="12" rx="2"/><text class="c-tick" x="{L+168}" y="{ly}">그림 생성</text></svg>')
    return "".join(o)


X4_ROWS = [  # 시나리오, A, B, B−A, 프롬프트 글 B−A  (eval/results/diffusion/x4_context_n42/summary.md)
    ("L01", 26.20, 27.63, 1.43, 4.11), ("L02", 23.23, 23.21, -0.01, -4.43), ("L05", 15.87, 19.11, 3.24, 15.96),
    ("L06", 16.42, 27.20, 10.78, 27.04), ("L07", 24.41, 24.25, -0.16, -5.52), ("L08", 29.70, 26.66, -3.03, -2.05),
    ("L11", 21.43, 22.94, 1.51, 12.29), ("L12", 18.38, 20.13, 1.75, -5.56), ("L13", 21.01, 25.90, 4.89, 21.27),
    ("L15", 24.02, 20.05, -3.98, 15.37), ("L16", 26.45, 30.44, 3.98, 1.52), ("L17", 27.62, 22.62, -5.00, 0.61),
    ("L18", 26.59, 26.38, -0.21, 3.30), ("L19", 28.29, 31.12, 2.84, 4.03), ("L21", 25.31, 24.66, -0.65, 4.19),
    ("L23", 27.26, 29.41, 2.16, 14.22), ("L24", 20.02, 26.23, 6.21, 16.16), ("L26", 16.73, 26.36, 9.62, 8.90),
    ("L28", 15.86, 22.59, 6.72, 9.46), ("L29", 18.19, 23.15, 4.96, -4.55), ("L30", 26.20, 24.67, -1.53, 2.14),
    ("S01", 22.42, 22.69, 0.27, 5.37), ("S02", 25.31, 26.88, 1.57, 1.67), ("S03", 17.35, 19.32, 1.97, -0.92),
    ("S04", 25.45, 25.24, -0.20, -5.50), ("S07", 26.10, 25.84, -0.26, -6.46), ("S09", 24.00, 34.82, 10.82, 27.64),
    ("S12", 26.84, 25.94, -0.90, 19.11),
]


def x4_chart():
    rows = sorted(X4_ROWS, key=lambda r: -r[3])
    W, L, R, T, rh = 640, 54, 70, 40, 19
    vmin, vmax = -6.0, 12.0
    pw = W - L - R
    H = T + rh * len(rows) + 30
    x = lambda v: L + pw * (v - vmin) / (vmax - vmin)  # noqa: E731
    o = [f'<svg class="chart" viewBox="0 0 {W} {H}" role="img" aria-label="시나리오별 맥락 효과 B−A">',
         '<text class="c-title" x="0" y="18">시나리오별 B − A (그림 ↔ 정답 장면 CLIP, 시드 2개 평균)</text>']
    for t in range(-6, 13, 3):
        o.append(f'<line class="c-grid" x1="{x(t):.1f}" x2="{x(t):.1f}" y1="{T-6}" y2="{T+rh*len(rows)}"/>'
                 f'<text class="c-tick" x="{x(t):.1f}" y="{T+rh*len(rows)+16}" text-anchor="middle">{t:+d}</text>')
    for i, (sid, a, b, d, pd) in enumerate(rows):
        y0 = T + i * rh
        cls = "s-teal" if d >= 0 else "s-coral"
        x1, x2 = sorted([x(0), x(d)])
        o.append(f'<g class="c-row"><title>{sid}: A {a:.2f} → B {b:.2f} (B−A {d:+.2f}) · 그림 프롬프트 글 B−A {pd:+.2f}</title>'
                 f'<rect class="c-hitrow" x="0" y="{y0}" width="{W}" height="{rh}"/>'
                 f'<text class="c-tick" x="{L-8}" y="{y0+rh/2+4:.1f}" text-anchor="end">{sid}</text>'
                 f'<rect class="c-bar {cls}" x="{x1:.1f}" y="{y0+3}" width="{max(x2-x1,1.5):.1f}" height="{rh-6}" rx="3"/>'
                 f'<text class="c-val sm" x="{(x(d)+5) if d >= 0 else (x(d)-5):.1f}" y="{y0+rh/2+4:.1f}" '
                 f'text-anchor="{"start" if d >= 0 else "end"}">{d:+.2f}</text></g>')
    o.append(f'<line class="c-axis" x1="{x(0):.1f}" x2="{x(0):.1f}" y1="{T-6}" y2="{T+rh*len(rows)}"/>')
    o.append(f'<line class="c-mean" x1="{x(2.10):.1f}" x2="{x(2.10):.1f}" y1="{T-10}" y2="{T+rh*len(rows)}"/>'
             f'<text class="c-val" x="{x(2.10)+5:.1f}" y="{T-12}">평균 +2.10</text>')
    o.append("</svg>")
    return "".join(o)


# ───────────────────────── script.md 읽기 ─────────────────────────
def parse_script():
    text = (HERE / "script.md").read_text()
    slides, demo_lines, qa = {}, [], []
    sec = re.split(r"^## ", text, flags=re.M)
    for chunk in sec[1:]:
        head, _, body = chunk.partition("\n")
        m = re.match(r"(\d+)\. (.+) \((\d+:\d+)\)", head)
        if m:
            en = re.search(r"^\*\*EN\*\* (.+)$", body, re.M)
            ko = re.search(r"^\*\*KO\*\* (.+)$", body, re.M)
            slides[int(m.group(1))] = {"title": m.group(2), "t": m.group(3),
                                       "en": en.group(1) if en else "", "ko": ko.group(1) if ko else ""}
            if "### 시연 대본" in body:
                demo_lines = body.split("### 시연 대본", 1)[1].split("\n", 1)[1].strip().splitlines()
        elif head.startswith("부록"):
            for bm in re.finditer(r"^### (\d+)\. (.+?)\n(.*?)(?=^### |\Z)", body, re.M | re.S):
                en = re.search(r"^\*\*EN\*\* (.+)$", bm.group(3), re.M)
                ko = re.search(r"^\*\*KO\*\* (.+)$", bm.group(3), re.M)
                slides[int(bm.group(1))] = {"title": bm.group(2), "t": "",
                                            "en": en.group(1) if en else "", "ko": ko.group(1) if ko else ""}
        elif head.startswith("예상 질문"):
            for q in re.split(r"^\*\*Q\d+\. ", body, flags=re.M)[1:]:
                qh, _, rest = q.partition("\n")
                q_en, _, q_ko = qh.partition("** (")
                a_en = re.search(r"^- EN: (.+)$", rest, re.M)
                a_ko = re.search(r"^- KO: (.+)$", rest, re.M)
                qa.append((q_en, q_ko.rstrip(")"), a_en.group(1) if a_en else "", a_ko.group(1) if a_ko else ""))
    return slides, demo_lines, qa


def demo_html(lines):
    out, in_list, depth = [], False, 0
    for ln in lines:
        if not ln.strip():
            if in_list:
                out.append("</ul>" * depth)
                in_list, depth = False, 0
            continue
        mm = re.match(r"^(\s*)- (.+)$", ln)
        if mm:
            d = 2 if mm.group(1) else 1
            if not in_list:
                out.append("<ul>")
                in_list, depth = True, 1
            if d > depth:
                out.append("<ul>")
                depth = d
            elif d < depth:
                out.append("</ul>")
                depth = d
            out.append(f"<li>{md_inline(mm.group(2))}</li>")
        else:
            out.append(f"<p>{md_inline(ln)}</p>")
    if in_list:
        out.append("</ul>" * depth)
    return "\n".join(out)


SLIDE_INFO = {  # 번호: (역할, 화면 구성, 뒷받침 근거)
    1: ("무엇을 만들었는지 한 문장으로 알립니다.",
        "제목, 한 줄 설명, 시스템이 실제로 만든 슬라이드 한 장(학습률이 클 때를 등산객에 비유).",
        "11-05 실제 API 점검의 결과 화면."),
    2: ("청자가 공감할 문제 상황을 그림으로 보여 줍니다(유용성).",
        "강의 시간 축 위에 미리 만든 장 1~4, 그 사이 즉석 비유가 나온 순간과 비어 있는 장.",
        "사용 시나리오."),
    3: ("해결 장면을 먼저 보여 줘서 무엇을 하는 시스템인지 바로 이해시킵니다.",
        "말한 한국어 문장과 영어 번역 → 실제로 만들어진 슬라이드(과적합을 시험 문제를 외운 학생에 비유).",
        "11-05 실제 API 전체 흐름(텍스트 입력 경로) 결과 화면."),
    4: ("동작을 세 단계(듣기·판단·만들기)로 설명합니다(구현).",
        "실제 발표자 화면 캡처 위에 세 영역(음성 인식·생성 요청·다음 장 미리보기)을 번호로 표시.",
        "감지 평가 56/60(놓친 요청 0), 맥락 고정(직전 90초)."),
    5: ("핵심 아이디어(강의 맥락을 조건으로 쓴다)를 구체적인 예로 보여 줍니다(창의성).",
        "역사 수업 발화와 요청 → 요청만 준 그림(현대 교실)과 맥락까지 준 그림(조선 과거 시험장).",
        "X4 시나리오 S09의 실제 생성 그림(시드 0)."),
    6: ("17강 내용(이미지 모델은 글자·개수·관계에 약하다)과 설계를 연결합니다(기술 이해).",
        "실제로 만든 그림형·수식형·비교형 슬라이드 3장.",
        "11-05 실제 API 점검 G·H."),
    7: ("시연으로 구현을 증명합니다.",
        "볼거리 네 가지(일반 발화 무시, 요청 시 글 먼저, 그림이 단계별로 만들어짐, 부정 지시 무시).",
        "시연 대본(아래 6-3)."),
    8: ("수업 개념(확산·DDIM·x̂₀)을 이미지 단계에 적용한 것을 보여 줍니다(기술 이해).",
        "25단계 중 4·12·22단계의 x̂₀ 예측과 완성 그림.",
        "디노이징 미리보기 구현·확인(5-12)."),
    9: ("실험 1: 실시간 강의에 쓸 만큼 빠른가.",
        "SD 1.5 25스텝 11.1초 대 SD-Turbo 2스텝 0.68초 막대, 그림 0.7초·전체 약 6초.",
        "X3, 로컬 E2E(n=1) (5-6, 5-11)."),
    10: ("실험 2: 가이던스 세기를 올리면 무엇이 바뀌나.",
         "같은 프롬프트·시드에서 가이던스 1·3·7.5·12 그림, 프롬프트 일치도와 다양성 그래프.",
         "X2, X1 (5-4, 5-5)."),
    11: ("실험 3(핵심): 강의 맥락이 정말 도움이 되나.",
         "실험 설계 세 줄, +2.1(p=0.010), 되묻기 7 → 0, 시나리오 28개의 B−A 막대.",
         "X4 확장 42개 (5-8)."),
    12: ("아직 안 되는 것을 정직하게 밝힙니다(실험·분석).",
         "가짜 글자가 생긴 실제 그림, 한계 세 가지(가짜 글자·CLIP 하나뿐·직접 만든 평가 세트), 다음 단계.",
         "X5, 글자 규칙 (5-7, 5-9)."),
    13: ("결론 세 문장과 질문 받기.",
         "정리 세 문장, Thank you · Questions?",
         "앞의 실험 전체."),
    14: ("부록: 기존 도구와의 차이를 물으면 씁니다.",
         "ZeroPrep 같은 실시간 발표 도구와 NextSlide 비교표.",
         "docs/qa-supplement-plan.md 2절(ZeroPrep README·코드 확인)."),
    15: ("부록: 감지기·테스트·속도를 물으면 씁니다.",
         "감지 56/60(놓친 요청 0·잘못 생성 1·불필요한 되묻기 3), 테스트 112개, 전체 흐름 시간표(로컬 6.2초, API 20.0초).",
         "감지 평가, pytest, 실제 API 점검과 로컬 E2E."),
    16: ("부록: 실험 방법을 물으면 씁니다.",
         "CLIP 점수 방식, 장면·시드 수, 신뢰구간·순열 검정, X1 결과, SD-Turbo 해석 주의, 77토큰 버그, 버린 지표.",
         "3장 실험 공통 원칙, 5장 실험별 상세."),
}


def slides_html(script):
    out = []
    for n in sorted(script):
        s = script[n]
        role, scr, ev = SLIDE_INFO[n]
        out.append(f'''<article class="slide-card" id="slide-{n}">
  {figure(f"docs/presentation/assets/slides/s{n:02d}.jpg", f"{n}번 슬라이드: {s['title']}")}
  <div class="slide-body">
    <h4><span class="badge-n">{n}</span>{esc(s['title'])} <span class="pill">{s['t'] or "부록"}</span></h4>
    <dl class="kv"><dt>역할</dt><dd>{esc(role)}</dd><dt>화면</dt><dd>{esc(scr)}</dd><dt>근거</dt><dd>{esc(ev)}</dd></dl>
    <details><summary>발표 대본 (영어 · 한국어)</summary>
      <p class="en" lang="en">{md_inline(s['en'])}</p><p class="ko">{md_inline(s['ko'])}</p></details>
  </div>
</article>''')
    return "\n".join(out)


def qa_html(qa):
    out = []
    for i, (qe, qk, ae, ak) in enumerate(qa, 1):
        out.append(f'<details class="qa"><summary><span class="badge-n">Q{i}</span>{esc(qk)} <span class="muted" lang="en">{esc(qe)}</span></summary>'
                   f'<p class="ko">{md_inline(ak)}</p><p class="en" lang="en">{md_inline(ae)}</p></details>')
    return "\n".join(out)


def x4_table():
    rows = "".join(f"<tr><td>{s}</td><td>{a:.2f}</td><td>{b:.2f}</td><td class=\"{'pos' if d >= 0 else 'neg'}\">{d:+.2f}</td>"
                   f"<td>{p:+.2f}</td></tr>" for s, a, b, d, p in X4_ROWS)
    return ('<div class="tbl"><table><thead><tr><th>시나리오</th><th>A 요청만</th><th>B 요청+맥락</th><th>B−A</th>'
            f'<th>그림 프롬프트(글) B−A</th></tr></thead><tbody>{rows}</tbody></table></div>')


SCENES = [
    ("P01", "A student memorizes the answers of old exam papers stacked on a desk, then looks confused at a brand-new question sheet", "과적합"),
    ("P02", "A hiker walking down a foggy mountain valley step by step toward the lowest point, small footprints along a curved path", "경사하강법"),
    ("P03", "Three balls rolling into a bowl-shaped valley: one with tiny steps, one smoothly reaching the bottom, one bouncing over the edge", "학습률"),
    ("P04", "A reader with a flashlight in a dark library, beams of light focusing more brightly on a few relevant books on the shelf", "어텐션"),
    ("P05", "Colorful clouds of points floating in a soft 2D space, neighboring clouds blending smoothly, a small arrow sampling a point from the middle", "VAE 잠재 공간"),
    ("P06", "A row of five picture frames showing a cat emerging step by step from heavy static noise to a clear cat", "확산 역과정"),
    ("P07", "An art forger painting a canvas while a detective with a magnifying glass inspects another painting, facing each other across a table", "GAN"),
    ("P08", "A student secretly peeking at the answer key hidden under the exam paper during a test", "데이터 누수"),
    ("P09", "A gardener trimming a wildly overgrown bush into a simple smooth rounded shape", "정규화"),
    ("P10", "A round pizza cut into five slices, one slice highlighted and set aside while the other four stay on the plate", "교차 검증"),
    ("P11", "A sculptor carving a block of stone while looking at a reference sketch of a cat pinned on the wall", "조건부 생성"),
    ("P12", "Four archery targets side by side with arrows clustered tightly off-center, scattered around the center, scattered off-center, and tightly at the bull", "편향·분산"),
]


def scenes_table():
    rows = "".join(f'<tr><td>{i}</td><td>{esc(k)}</td><td lang="en">{esc(s)}</td></tr>' for i, s, k in SCENES)
    return f'<div class="tbl"><table><thead><tr><th>ID</th><th>개념(참고)</th><th>장면 문장(영어, 프롬프트이자 CLIP 채점 기준)</th></tr></thead><tbody>{rows}</tbody></table></div>'


# ───────────────────────── 본문 ─────────────────────────
CSS = r"""
:root{--bg:#FFFFFF;--surface:#F3F6F8;--surface2:#E7F3F1;--ink:#1B2B3A;--heading:#1F3A5F;--muted:#5B6B7B;--line:#DCE3E9;
--teal:#2A9D8F;--teal-ink:#1D7A6E;--amber:#E9B949;--amber-bg:#FDF4DC;--coral:#E76F51;--coral-ink:#B5472E;--navy:#1F3A5F;--code:#EDF1F4;--fill-navy:#1F3A5F;--fill-teal:#2A9D8F;
--shadow:0 1px 2px rgba(27,43,58,.06),0 4px 14px rgba(27,43,58,.06)}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#0F1923;--surface:#16232F;--surface2:#132E2A;--ink:#E3EAF0;--heading:#A8C8E8;
--muted:#98A8B6;--line:#2A3A49;--teal:#3AB7A6;--teal-ink:#63D0C1;--amber:#F0C75E;--amber-bg:#2E2814;--coral:#EF8768;--coral-ink:#F5A58C;--navy:#6A93C4;--code:#1C2A37;--fill-navy:#24466E;--fill-teal:#1E7A6E;
--shadow:0 1px 2px rgba(0,0,0,.3)}}
:root[data-theme="dark"]{--bg:#0F1923;--surface:#16232F;--surface2:#132E2A;--ink:#E3EAF0;--heading:#A8C8E8;
--muted:#98A8B6;--line:#2A3A49;--teal:#3AB7A6;--teal-ink:#63D0C1;--amber:#F0C75E;--amber-bg:#2E2814;--coral:#EF8768;--coral-ink:#F5A58C;--navy:#6A93C4;--code:#1C2A37;--fill-navy:#24466E;--fill-teal:#1E7A6E;
--shadow:0 1px 2px rgba(0,0,0,.3)}
*{box-sizing:border-box}
html{scroll-behavior:smooth;-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.75 -apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Pretendard","Noto Sans KR","Malgun Gothic","Segoe UI",sans-serif;word-break:keep-all;overflow-wrap:break-word}
a{color:var(--teal-ink)}
code{overflow-wrap:anywhere;background:var(--code);padding:.1em .35em;border-radius:4px;font:.88em/1.5 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
pre{background:var(--code);padding:14px 16px;border-radius:10px;overflow-x:auto;font:13px/1.6 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;margin:12px 0}
pre code{background:none;padding:0}
.wrap{display:grid;grid-template-columns:230px minmax(0,1fr);gap:48px;max-width:1240px;margin:0 auto;padding:0 32px}
.toc{position:sticky;top:0;align-self:start;max-height:100vh;overflow:auto;padding:28px 0;font-size:14px}
.toc summary{font-weight:700;color:var(--heading);cursor:pointer;margin-bottom:8px}
.toc ol{list-style:none;margin:0;padding:0}
.toc li{margin:2px 0}.toc li li{padding-left:12px;font-size:13px}
.toc a{color:var(--muted);text-decoration:none;display:block;padding:3px 8px;border-radius:6px}
.toc a:hover{background:var(--surface);color:var(--ink)}
main{min-width:0;padding:24px 0 80px}
header.hero{padding:28px 0 8px}
.kicker{color:var(--teal-ink);font-weight:700;font-size:14px;letter-spacing:.02em}
h1{font-size:34px;line-height:1.3;margin:6px 0 10px;color:var(--heading)}
h2{font-size:26px;line-height:1.35;margin:64px 0 14px;color:var(--heading);padding-top:8px}
h3{font-size:20px;margin:40px 0 10px;color:var(--heading)}
h4{font-size:17px;margin:22px 0 6px}
p{margin:10px 0}
.lead{font-size:18px;color:var(--muted);max-width:820px}
.meta{font-size:13px;color:var(--muted)}
.muted{color:var(--muted)}
.note{background:var(--surface);border-radius:12px;padding:14px 18px;margin:16px 0;font-size:15px}
.warn{background:var(--amber-bg);border-radius:12px;padding:14px 18px;margin:16px 0;font-size:15px}
.good{background:var(--surface2);border-radius:12px;padding:14px 18px;margin:16px 0;font-size:15px}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:14px;margin:22px 0}
.stat{background:var(--surface);border-radius:14px;padding:16px 18px}
.stat b{display:block;font-size:32px;line-height:1.2;color:var(--heading);font-variant-numeric:tabular-nums}
.stat.hl b{color:var(--teal-ink)}
.stat span{font-size:14px;color:var(--muted);display:block;margin-top:4px;line-height:1.5}
.tbl{overflow-x:auto;margin:14px 0;border:1px solid var(--line);border-radius:10px}
table{border-collapse:collapse;width:100%;font-size:14.5px;line-height:1.55}
th,td{padding:9px 12px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
thead th{background:var(--surface);color:var(--heading);font-weight:700;white-space:nowrap}
tbody tr:last-child td{border-bottom:none}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
tbody td:first-child{min-width:5.5em}
td.pos{color:var(--teal-ink);font-weight:700}td.neg{color:var(--coral-ink);font-weight:700}
figure{margin:18px 0}
figure img{display:block;max-width:100%;height:auto;border-radius:10px;border:1px solid var(--line);cursor:zoom-in;background:#fff}
figcaption{font-size:13.5px;color:var(--muted);margin-top:6px}
figure.narrow img{max-width:520px;width:100%}
kbd{font:12px/1 ui-monospace,Menlo,monospace;border:1px solid var(--line);border-bottom-width:2px;border-radius:5px;padding:2px 6px;background:var(--surface)}
.grid2{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}
.grid3{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}
.card{border:1px solid var(--line);border-radius:14px;padding:6px 22px 14px;margin:22px 0;background:var(--bg);box-shadow:var(--shadow)}
.card>h3:first-child{margin-top:18px}
.tag{display:inline-block;font-size:12px;font-weight:700;padding:2px 9px;border-radius:999px;background:var(--surface);color:var(--muted);margin-right:6px;vertical-align:middle}
.tag.ok{background:var(--surface2);color:var(--teal-ink)}.tag.no{background:var(--amber-bg);color:var(--coral-ink)}
dl.kv{display:grid;grid-template-columns:72px minmax(0,1fr);gap:4px 12px;margin:10px 0;font-size:15px}
dl.kv dt{color:var(--muted);font-weight:700}dl.kv dd{margin:0}
.flow{display:flex;flex-wrap:wrap;align-items:stretch;gap:8px;margin:18px 0}
.flow .box{flex:1 1 0;min-width:104px;background:var(--surface);border-radius:12px;padding:10px 12px;font-size:14px;line-height:1.5}
.flow .box b{display:block;color:var(--heading);font-size:15px}
.flow .box.dark{background:var(--fill-navy);color:#fff}.flow .box.dark b{color:#fff}
.flow .arrow{align-self:center;color:var(--muted);font-weight:700}
.cond{display:grid;grid-template-columns:minmax(0,1fr) auto minmax(0,1fr);gap:14px;align-items:center;margin:18px 0}
.cond .chips{display:grid;gap:8px}
.chip{background:var(--surface2);border-radius:10px;padding:8px 14px;font-size:14.5px}
.chip b{color:var(--teal-ink)}
.chip.main{background:var(--fill-teal);color:#fff}.chip.main b{color:#fff}
.cond .to{font-size:24px;color:var(--muted)}
.cond .plan{background:var(--fill-navy);color:#fff;border-radius:12px;padding:14px 16px;font-size:14.5px}
.scen{background:var(--surface);border-radius:12px;padding:12px 16px;font-size:14.5px}
.scen .q{color:var(--teal-ink);font-weight:700}
.chart{width:100%;height:auto;display:block;font-family:inherit}
.c-title{font-size:14px;font-weight:700;fill:var(--ink)}
.c-tick{font-size:12px;fill:var(--muted)}
.c-val{font-size:12px;fill:var(--ink);font-variant-numeric:tabular-nums}.c-val.sm{font-size:11px}
.c-inbar{font-size:12px;fill:#fff;font-weight:700}
.c-grid{stroke:var(--line);stroke-width:1}
.c-axis{stroke:var(--muted);stroke-width:1}
.c-line{fill:none;stroke-width:2}
.c-ci{stroke-width:2;opacity:.45}
.c-dot{stroke:var(--bg);stroke-width:2}
.c-hit,.c-hitrow{fill:transparent}
.c-pt:hover .c-dot{r:7}
.c-row:hover .c-hitrow{fill:var(--surface)}
.c-mean{stroke:var(--ink);stroke-width:1.5;stroke-dasharray:4 3}
.s-teal{stroke:var(--teal);fill:var(--teal)}.c-line.s-teal{fill:none}
.s-navy{stroke:var(--navy);fill:var(--navy)}.c-line.s-navy{fill:none}
.s-gray{fill:#8D99AE;stroke:#8D99AE}
.s-coral{fill:var(--coral);stroke:var(--coral)}
.chartbox{background:var(--bg);border:1px solid var(--line);border-radius:12px;padding:14px 14px 8px;margin:16px 0}
.slides{display:grid;gap:18px}
.slide-card{display:grid;grid-template-columns:minmax(0,1.05fr) minmax(0,1fr);gap:20px;border:1px solid var(--line);border-radius:14px;padding:16px;box-shadow:var(--shadow)}
.slide-card figure{margin:0}
.slide-card h4{margin:0 0 6px;font-size:17px}
.badge-n{display:inline-flex;align-items:center;justify-content:center;min-width:26px;height:26px;padding:0 6px;border-radius:999px;background:var(--fill-navy);color:#fff;font-size:13px;font-weight:700;margin-right:8px}
.pill{font-size:12px;color:var(--muted);font-weight:400;margin-left:6px}
details{margin:8px 0}
details>summary{cursor:pointer;color:var(--teal-ink);font-weight:700;font-size:14.5px}
details p.en{font-size:14.5px;color:var(--ink);background:var(--surface);padding:10px 12px;border-radius:8px}
details p.ko{font-size:14.5px}
details.qa{border-bottom:1px solid var(--line);padding:8px 0;margin:0}
details.qa summary{color:var(--ink);font-weight:700}
details.qa summary .muted{font-weight:400;font-size:13.5px;display:block;margin-left:40px}
ol.steps,ul.list{padding-left:22px}
ol.steps li,ul.list li{margin:5px 0}
.formula{font:15px/1.6 "Cambria Math","STIX Two Math","Times New Roman",serif;background:var(--surface);border-radius:10px;padding:12px 16px;text-align:center;margin:12px 0;overflow-x:auto}
.toolbar{position:fixed;right:18px;bottom:18px;z-index:5;display:flex;gap:8px}
.toolbar button{border:1px solid var(--line);background:var(--bg);color:var(--ink);border-radius:999px;padding:8px 14px;font:inherit;font-size:13px;cursor:pointer;box-shadow:var(--shadow)}
#lb{position:fixed;inset:0;background:rgba(5,12,18,.88);display:none;align-items:center;justify-content:center;z-index:10;padding:16px;cursor:zoom-out}
#lb img{max-width:100%;max-height:100%;border-radius:8px;background:#fff}
#lb.on{display:flex}
@media (max-width:1000px){.wrap{display:block;padding:0 16px}.toc{position:static;max-height:none;padding:16px 0 0}
.grid2,.grid3,.slide-card{grid-template-columns:minmax(0,1fr)}.cond{grid-template-columns:minmax(0,1fr)}.cond .to{transform:rotate(90deg);justify-self:center}
h1{font-size:27px}h2{font-size:22px;margin-top:48px}.lead{font-size:16px}
.toolbar{position:static;justify-content:flex-end;padding:10px 16px 0}}
@media print{.toc,.toolbar{display:none}.wrap{display:block}details{display:block}details>*{display:block}.card,.slide-card{break-inside:avoid;box-shadow:none}}
"""

JS = r"""
(function(){
  var lb=document.getElementById('lb'),lbi=lb.querySelector('img');
  document.addEventListener('click',function(e){var t=e.target;
    if(t.matches&&t.matches('img[data-zoom]')){lbi.src=t.src;lbi.alt=t.alt;lb.classList.add('on');}
    else if(lb.classList.contains('on')){lb.classList.remove('on');}});
  document.addEventListener('keydown',function(e){if(e.key==='Escape')lb.classList.remove('on');});
  var toc=document.querySelector('details.toc');
  function fit(){ if(window.matchMedia('(min-width:1001px)').matches){toc.open=true;} }
  fit(); window.addEventListener('resize',fit);
  var root=document.documentElement,btn=document.getElementById('theme');
  function cur(){return root.getAttribute('data-theme')||(window.matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light');}
  function label(){btn.textContent=cur()==='dark'?'밝은 화면':'어두운 화면';}
  try{var s=localStorage.getItem('ns-theme'); if(s) root.setAttribute('data-theme',s);}catch(e){}
  label();
  btn.addEventListener('click',function(){var n=cur()==='dark'?'light':'dark';root.setAttribute('data-theme',n);
    try{localStorage.setItem('ns-theme',n);}catch(e){} label();});
  document.getElementById('expand').addEventListener('click',function(){
    var ds=document.querySelectorAll('main details'),any=false;ds.forEach(function(d){if(!d.open)any=true;});
    ds.forEach(function(d){d.open=any;}); this.textContent=any?'모두 접기':'모두 펼치기';});
})();
"""


def build():
    script, demo_lines, qa = parse_script()
    x2a = line_chart("장면 일치도 (CLIP, 높을수록 장면 문장과 맞음)", [1, 3, 5, 7.5, 12],
                     [21.48, 24.62, 25.72, 25.00, 25.64], [20.34, 22.93, 23.99, 22.98, 23.77], [22.70, 26.12, 27.55, 26.94, 27.50],
                     ymin=19, ymax=28, ytick=1, fmt="{:.1f}", series_cls="s-teal")
    x2b = line_chart("시드 간 다양성 (1 − 코사인, 높을수록 다양함)", [1, 3, 5, 7.5, 12],
                     [0.269, 0.209, 0.213, 0.182, 0.177], ymin=0.15, ymax=0.28, ytick=0.025, fmt="{:.3f}", series_cls="s-navy")
    x3 = hbar_chart("그림 1장 생성 시간 (중앙값, 낮을수록 좋음)", [
        ("SD-Turbo · 1스텝", 0.51, "s-teal"), ("SD-Turbo · 2스텝", 0.68, "s-teal"),
        ("SD-Turbo · 4스텝", 0.99, "s-teal"), ("SD 1.5 · DDIM 25스텝, CFG 7.5", 11.1, "s-gray")], vmax=12.5)

    body = f"""
<header class="hero">
  <div class="kicker">NextSlide · 생성형 AI 기말 프로젝트 해설서</div>
  <h1>말로 요청하면 다음 슬라이드가 만들어지는 강의 도구<br>무엇을 만들었고, 어떤 실험을 어떻게 했는가</h1>
  <p class="lead">강의 중 “다음 슬라이드에서는 …”이라고 말하면, 강사가 계속 말하는 동안 시스템이 다음 장을 만듭니다. 이 문서는 시스템의 구조, 수업 개념을 적용한 이미지 단계, 실험 하나하나의 질문·방법·결과·한계, 그리고 발표 PPT의 구성을 정리한 것입니다.</p>
  <p class="meta">작성 2026-11-24 · 저장소 <code>nunu0404/GenAI-proj-2026</code> · 발표 파일 <code>docs/presentation/NextSlide_final.pptx</code> · 이 파일은 <code>docs/presentation/build_guide.py</code>로 만듭니다.</p>
  <div class="note"><b>읽기 전에.</b> 이 문서의 수치는 모두 저장소에 기록된 실험 결과(<code>docs/diffusion-experiments.md</code>, <code>docs/results.md</code>, <code>eval/results/</code>)에서 옮겼습니다. 1회만 잰 값은 “n=1”로 표시했고, 측정하지 않은 것은 “미측정”으로 남겼습니다. 그림을 누르면 크게 볼 수 있습니다.</div>
</header>

<h2 id="summary">1. 한눈에 보기</h2>
<div class="stats">
  <div class="stat hl"><b>+2.10</b><span>강의 맥락을 조건에 넣었을 때 그림이 강사가 의도한 장면에 가까워진 정도 (CLIP 점수, 시나리오 42개, p=0.010)</span></div>
  <div class="stat"><b>7 → 0</b><span>맥락이 없을 때와 있을 때, 무엇을 그릴지 몰라 되물은 횟수 (42개 중)</span></div>
  <div class="stat"><b>0.68초</b><span>SD-Turbo 2스텝으로 그림 1장 생성 (SD 1.5 25스텝은 11.1초)</span></div>
  <div class="stat"><b>6.2초</b><span>요청 확정 → 그림까지 완성, 로컬 SD-Turbo 경로 (n=1). gpt-image-2 경로는 20.0초 (n=1)</span></div>
  <div class="stat"><b>56 / 60</b><span>규칙 기반 요청 감지 정답 (놓친 요청 0, 잘못 생성 1)</span></div>
</div>
<ul class="list">
  <li><b>만든 것</b>: 마이크 → 실시간 음성 인식 → 규칙 기반 요청 감지 → 맥락 고정 → 기획 LLM(엄격한 JSON) → 텍스트 먼저, 그림 다음 → 발표자가 확인하고 넘기면 청중 화면에 표시하는 웹 발표 시스템.</li>
  <li><b>새로운 점</b>: 사용자가 프롬프트를 쓰지 않습니다. <b>강의 자체(요청 + 직전 90초 발화 + 현재 장)</b>가 생성의 조건이 됩니다.</li>
  <li><b>수업 개념 적용</b>: 이미지 단계를 공개 확산 모델(SD 1.5, SD-Turbo)로 바꾸고, 샘플러·스텝·CFG·증류를 하나씩 바꿔 비교했습니다. 확산 중간의 x̂₀를 화면에 보여 주는 기능도 만들었습니다.</li>
  <li><b>확인한 것</b>: 맥락 조건은 효과가 있었고(p=0.010), 증류 모델은 실시간에 쓸 만큼 빨랐습니다. 반대로 맥락 효과가 글(+6.41)에서 그림(+2.10)으로 가며 줄어들어, <b>이미지 모델이 병목</b>이라는 점도 드러났습니다.</li>
  <li><b>남은 것</b>: 블라인드 사람 평가, 지연 반복 측정(n≥10), 그림 속 가짜 글자 문제.</li>
</ul>

<h2 id="project">2. 프로젝트 소개</h2>
<h3 id="problem">2-1. 문제와 목표</h3>
<p>좋은 강의는 즉흥적입니다. 강사는 “과적합은 시험 답을 외운 학생과 같다”처럼 그 자리에서 비유를 만들고, 학생은 슬라이드에 없던 질문을 합니다. 그런데 슬라이드는 미리 만들어 둔 것이라, 강의 중에 새 장이 필요하면 멈추고 편집기를 열어야 합니다. 그 순간 흐름이 끊깁니다.</p>
<p><b>목표</b>: 강사는 계속 말하고, 다음 장은 알아서 준비된다. 단, 잘못 만든 장이 청중에게 바로 보이면 안 되므로 <b>발표자가 먼저 확인</b>하고 넘깁니다.</p>

<h3 id="idea">2-2. 핵심 아이디어: 조건 설계</h3>
<p>생성형 모델은 조건(프롬프트)에 따라 결과가 달라집니다. 대부분의 도구는 사용자가 조건을 직접 씁니다. NextSlide는 <b>강의 음성에서 조건을 자동으로 만듭니다</b>. 그래서 “그 등산객 비유 그려 줘”처럼 앞 내용을 가리키는 요청도 처리할 수 있습니다.</p>
<div class="cond">
  <div class="chips">
    <div class="chip main"><b>요청</b> · 음성에서 감지한 “다음 슬라이드에서는 …”</div>
    <div class="chip"><b>최근 발화</b> · 요청 직전 90초(최대 1,500자), 요청 순간에 고정</div>
    <div class="chip"><b>현재 장</b> · 제목과 핵심 문장 + 최근에 만든 장 최대 3개</div>
    <div class="chip"><b>강의 정보</b> · 강의 제목, 청중</div>
  </div>
  <div class="to">→</div>
  <div class="plan"><b>슬라이드 계획</b> (기획 LLM, JSON)<br>형태 · 제목 · 핵심 문장 2~3개 · 그림 묘사(영어) · 필요하면 “되묻기”</div>
</div>
<p class="muted">이 조건 설계가 실제로 그림을 강사 의도에 가깝게 만드는지는 <a href="#x4">실험 X4</a>에서 검증했습니다.</p>

<h3 id="usage">2-3. 사용 흐름</h3>
<ol class="steps">
  <li>세션(강의 제목·청중)을 만들고 발표자 화면과 청중 화면(두 번째 창 또는 프로젝터)을 엽니다.</li>
  <li>마이크를 켜고 평소처럼 강의합니다. 일반 설명에는 아무것도 생기지 않습니다.</li>
  <li>“다음 슬라이드에서는 과적합을 시험 문제를 외운 학생에 비유해서 설명하겠습니다.”라고 말합니다.</li>
  <li>발표자 미리보기에 제목과 본문이 먼저 뜨고, 그림이 뒤따라옵니다. 로컬 확산 모델이면 그림이 흐릿한 상태에서 점점 선명해지는 과정이 보입니다.</li>
  <li>발표자가 내용을 확인하고 <kbd>→</kbd>로 넘기면 청중 화면에 나타납니다. 필요하면 제목·본문을 고치거나 그림만 다시 만들 수 있습니다.</li>
</ol>
{figure("docs/images/real_slide_v1_presenter_text_ready.png", "발표자 화면: 왼쪽 현재 장, 오른쪽 다음 장 미리보기와 자막, 생성 요청 카드", "발표자 화면(실제 API, 11-05). 오른쪽 위 ‘다음 장 미리보기’에 제목·본문이 먼저 떴고 그림은 생성 중입니다. 아래에 음성 자막과 생성 요청 카드가 보입니다.")}

<h3 id="pipeline">2-4. 시스템 구조</h3>
<div class="flow">
  <div class="box"><b>마이크</b>브라우저 AudioWorklet, 16kHz PCM</div><span class="arrow">→</span>
  <div class="box"><b>음성 인식</b>Gemini 실시간 전사(한국어)</div><span class="arrow">→</span>
  <div class="box"><b>요청 감지</b>규칙 기반, 부정·인용 제외</div><span class="arrow">→</span>
  <div class="box"><b>맥락 고정</b>요청 + 90초 + 현재 장</div><span class="arrow">→</span>
  <div class="box"><b>기획 LLM</b>엄격한 JSON, 형태 선택</div><span class="arrow">→</span>
  <div class="box dark"><b>텍스트 → 그림</b>발표자 확인 후 청중에게</div>
</div>
<div class="tbl"><table>
<thead><tr><th>단계</th><th>하는 일</th><th>왜 이렇게 했나</th></tr></thead><tbody>
<tr><td>오디오</td><td>브라우저가 장치 샘플레이트(보통 48kHz)를 저역통과 필터 후 16kHz PCM16 100ms 단위로 보냅니다.</td><td>STT가 요구하는 형식. 서버가 형식을 검증하고 다르면 거부합니다.</td></tr>
<tr><td>구간 나누기(VAD)</td><td>서버가 20ms마다 음량(RMS)을 보고, 250ms 이상 말소리가 이어지면 STT로 보내고, 700ms 침묵이면 구간을 닫습니다.</td><td>짧은 잡음은 보내지 않아 오인식과 비용을 줄입니다.</td></tr>
<tr><td>음성 인식</td><td>Gemini <code>gemini-3.5-transcribe-live</code>(무료 등급), ko-KR. 10분마다 쉬는 구간에서 세션을 바꿉니다.</td><td>실시간 한국어 전사. 무료 등급은 사용자의 선택.</td></tr>
<tr><td>요청 감지</td><td>“다음 슬라이드/장/페이지” 같은 트리거 + “설명하겠습니다” 같은 완료 표현(또는 2.5초 침묵)을 찾습니다. 부정(“만들지 마세요”)·인용(“…라고 말하면”)·장 넘김(“다음 장으로 넘어가”)은 제외합니다. 주제가 “그거”뿐이면 <b>입력 보완</b>으로 표시합니다.</td><td>발화마다 LLM을 부르면 느리고 비싸며, 잘못 생성되면 강의가 끊깁니다.</td></tr>
<tr><td>맥락 고정</td><td>요청 순간의 직전 90초 발화·현재 장·최근 장을 작업에 저장합니다. 이후 발화는 섞이지 않습니다.</td><td>생성 중에도 강의는 계속되므로, 조건이 바뀌지 않게 합니다.</td></tr>
<tr><td>대기열</td><td>세션마다 작업자 1개, 대기 최대 3개.</td><td>요청이 몰려도 순서대로 처리하고 넘치면 알립니다.</td></tr>
<tr><td>기획</td><td>OpenAI <code>gpt-6-luna</code>가 JSON 스키마에 맞춰 슬라이드 계획을 돌려주면 서버가 검증합니다(제목 40자, 핵심 문장 2~3개). 실패하면 오류 내용을 붙여 1회만 다시 요청합니다.</td><td>생성된 HTML을 실행하지 않고, 정해진 부품으로만 그려 안전하고 일관됩니다.</td></tr>
<tr><td>형태 선택</td><td>그림 · 수식(KaTeX) · 텍스트 · 좌우 비교 · 표 · 그래프. 그래프는 LLM이 함수와 범위만 정하고 좌표는 서버가 계산합니다.</td><td>이미지 모델은 글자·개수·관계를 자주 틀립니다(17강 31쪽). 숫자를 LLM이 지어내지 않게 합니다.</td></tr>
<tr><td>텍스트 먼저</td><td>기획이 끝나면 제목·본문을 발표자 미리보기에 먼저 보여 주고, 원하면 그림을 기다리지 않고 넘길 수 있습니다. 그림은 도착하면 서서히 나타납니다.</td><td>가장 느린 단계가 그림이라서.</td></tr>
<tr><td>그림</td><td>OpenAI <code>gpt-image-2</code>(1536×864, low) 또는 <b>로컬 확산 모델</b>(SD-Turbo 2스텝 기본 / SD 1.5). 프롬프트는 장면 묘사 + 짧은 화풍이고 77토큰에 맞춥니다. 받은 이미지는 형식·크기·비율을 검사합니다.</td><td>환경변수 하나(<code>IMAGE_PROVIDER</code>)로 바꿀 수 있습니다.</td></tr>
<tr><td>디노이징 미리보기</td><td>로컬 모델이 그림을 만드는 동안 매 스텝의 x̂₀ 미리보기를 <code>slide.preview</code> 이벤트로 보냅니다.</td><td>기다리는 시간을 ‘확산 과정 보여 주기’로 바꿉니다.</td></tr>
<tr><td>공개</td><td>준비 완료된 장만 넘길 수 있고 청중에게 전송됩니다. 취소되었거나 시도 번호가 다른 늦은 결과는 버립니다.</td><td>미완성·잘못된 장의 노출을 막습니다.</td></tr>
<tr><td>저장</td><td>SQLite(세션, 확정 발화, 슬라이드, 작업, 사용량·비용 기록). 새로고침해도 세션이 복원됩니다.</td><td>원시 음성은 저장하지 않습니다.</td></tr>
</tbody></table></div>

<h3 id="forms">2-5. 슬라이드 형태 (실제 API로 생성한 화면)</h3>
<div class="grid3">
{figure("docs/images/real_v2_illustration.png", "그림형 슬라이드", "그림형: 이미지 모델은 글자 없는 설명 그림만")}
{figure("docs/images/real_v2_equation_gd.png", "수식형 슬라이드", "수식형: KaTeX로 렌더링")}
{figure("docs/images/real_v4_comparison.png", "비교형 슬라이드", "비교형: 고정 2단 레이아웃")}
{figure("docs/images/real_v4_table.png", "표형 슬라이드", "표형: 강의에서 말한 항목만 사용")}
{figure("docs/images/real_v4_chart_function.png", "그래프형 슬라이드", "그래프형: 좌표는 서버가 계산")}
{figure("docs/images/real_v2_equation_mse.png", "형태 지정 없이 수식형이 선택된 슬라이드", "형태를 말하지 않아도 모델이 수식형을 고른 예")}
</div>

<h3 id="choices">2-6. 설계 선택과 근거</h3>
<div class="tbl"><table><thead><tr><th>선택</th><th>이유</th><th>뒷받침</th></tr></thead><tbody>
<tr><td>요청 감지는 규칙으로</td><td>비용·지연·오작동</td><td>감지 평가 56/60, 놓친 요청 0 (<a href="#detect">5-1</a>)</td></tr>
<tr><td>글자·수식·표·그래프는 이미지 모델에 맡기지 않음</td><td>17강 31쪽: 그럴듯한 그림도 글자·개수·관계를 놓침</td><td>X3·X5에서 SD-Turbo의 가짜 글자 확인 (<a href="#x5">5-7</a>)</td></tr>
<tr><td>그래프 좌표는 서버 계산</td><td>LLM이 숫자를 지어내지 않게</td><td>11-05 실제 API 점검 H③</td></tr>
<tr><td>발표자 확인 후 공개</td><td>틀린 장이 바로 청중에게 보이지 않게</td><td>ZeroPrep(즉시 표시)과의 차이</td></tr>
<tr><td>텍스트 먼저, 그림 다음</td><td>그림이 가장 느린 단계</td><td>gpt-image-2 경로에서 그림이 시간의 약 70~80% (<a href="#api">5-2</a>)</td></tr>
<tr><td>그림 기본값: 로컬 SD-Turbo 2스텝</td><td>속도와 비용</td><td>0.68초, 비용 0, CLIP도 SD 1.5보다 높음 (<a href="#x3">5-6</a>)</td></tr>
</tbody></table></div>

<h3 id="stack">2-7. 기술 구성</h3>
<div class="tbl"><table><tbody>
<tr><th>프런트엔드</th><td>React 18 + TypeScript + Vite, KaTeX. 발표자 화면, 청중 화면, 전체 화면 발표 모드(<kbd>M</kbd> 마이크, <kbd>→</kbd> 다음 장)</td></tr>
<tr><th>백엔드</th><td>FastAPI(단일 프로세스), WebSocket(역할별로 걸러서 전송), SQLite, Pydantic 검증</td></tr>
<tr><th>외부 모델</th><td>STT: Gemini <code>gemini-3.5-transcribe-live</code>(무료 등급) · 기획: OpenAI <code>gpt-6-luna</code> · 그림: OpenAI <code>gpt-image-2</code>(선택)</td></tr>
<tr><th>로컬 모델</th><td><code>stabilityai/sd-turbo</code>, <code>stable-diffusion-v1-5</code> · diffusers 0.43, PyTorch 2.15(MPS) · Apple M5, 메모리 16GB</td></tr>
<tr><th>테스트</th><td>pytest 112개(mock 제공자, 실제 API 호출 없음) · 프런트엔드 타입 검사·빌드 · 헤드리스 Chrome E2E</td></tr>
<tr><th>보안</th><td>API 키는 서버 환경변수에만 있고 브라우저로 보내지 않습니다(테스트로 확인). 서버는 127.0.0.1에만 엽니다.</td></tr>
</tbody></table></div>

<h3 id="prior">2-8. 기존 도구와의 차이</h3>
<div class="tbl"><table><thead><tr><th></th><th>ZeroPrep 같은 실시간 발표 도구</th><th>NextSlide</th></tr></thead><tbody>
<tr><td>생성 계기</td><td>실시간 모델이 모든 발화를 해석</td><td><b>명시적 요청만</b> (규칙 감지)</td></tr>
<tr><td>처음 보는 사람</td><td>청중, 즉시</td><td><b>발표자</b>, 확인 후 넘김</td></tr>
<tr><td>슬라이드 형태</td><td>카드, 지표, 다이어그램</td><td>그림, 수식, 비교, 표, 그래프</td></tr>
<tr><td>조건</td><td>실시간 대화</td><td>요청 + 직전 90초 + 현재 장 (고정)</td></tr>
</tbody></table></div>
<p class="meta">ZeroPrep: github.com/ramsrigouthamg/zeroprep, README와 app 코드를 2026-11-05에 확인. 서버 측 프롬프트는 확인하지 못했습니다.</p>

<h2 id="method">3. 실험 설계의 공통 원칙</h2>
<ol class="steps">
  <li><b>한 번에 하나만 바꾼다.</b> 17강 29쪽 “Change one setting at a time”. 모델, 해상도, 장면, 시드는 고정하고 비교할 설정 하나만 바꿉니다.</li>
  <li><b>초기 잡음을 고정한다.</b> 장면마다 시드 0과 1을 씁니다. 같은 시드는 같은 초기 잡음이므로 차이는 조건에서만 옵니다.</li>
  <li><b>결과를 보기 전에 기준을 고정한다.</b> X4의 시나리오와 정답 장면은 생성 전에 git에 커밋했습니다(<code>d1a4ce0</code>).</li>
  <li><b>실패도 기록한다.</b> 효과가 없던 대책, 검증에 실패한 지표도 결과로 남깁니다.</li>
</ol>
<h3 id="metrics">3-1. 지표</h3>
<dl class="kv" style="grid-template-columns:120px minmax(0,1fr)">
  <dt>CLIP 유사도</dt><dd>그림과 문장을 CLIP으로 같은 공간의 벡터로 바꾼 뒤 코사인 유사도 × 100. 높을수록 그림이 문장 내용과 맞습니다. 생성 모델이 쓰는 텍스트 인코더(SD 1.5: ViT-L/14, SD-Turbo: OpenCLIP ViT-H)와 <b>다른</b> <code>openai/clip-vit-base-patch32</code>로 채점해 ‘자기 채점’ 편향을 줄였습니다. 보통 20~35 사이 값이 나오며, 절대값보다 조건 간 차이를 봅니다.</dd>
  <dt>다양성</dt><dd>같은 장면·조건에서 시드 0과 1로 만든 두 그림의 이미지 임베딩 거리(1 − 코사인). 클수록 서로 다른 그림이 나옵니다.</dd>
  <dt>95% 신뢰구간</dt><dd>장면(또는 시나리오)을 복원 추출하는 부트스트랩 2,000회로 구합니다. 두 조건의 구간이 많이 겹치면 차이를 확신할 수 없습니다.</dd>
  <dt>순열 검정 p값</dt><dd>X4에서 사용. 시나리오별 차이(B−A)의 부호를 무작위로 뒤집는 것을 20,000회 반복해, “맥락이 아무 효과가 없다면 이만한 평균 차이가 우연히 나올 확률”을 계산합니다(양측). 0.05보다 작으면 우연으로 보기 어렵다고 판단합니다.</dd>
  <dt>시간</dt><dd>GPU 동기화 후 단조 시계로 잽니다. 첫 호출(워밍업)은 제외하고 중앙값을 씁니다.</dd>
</dl>
<h3 id="setup">3-2. 환경과 장면 세트</h3>
<p>Apple M5(메모리 16GB), MPS, PyTorch 2.15, diffusers 0.43. 해상도 768×432(16:9, 잠재 공간 96×54). 모든 확산 실험은 로컬에서 돌아 API 비용이 0입니다.</p>
<details><summary>X1~X3·X5에 쓴 장면 12개 보기</summary>{scenes_table()}
<p class="meta">출처: <code>eval/diffusion/prompts.json</code>. 개발자가 직접 썼고(기획 LLM 출력 아님), 글자 없이 그릴 수 있는 강의 비유 장면만 담았습니다. 프롬프트는 시스템과 같은 방식(장면 + 짧은 화풍, CFG&gt;1이면 “글자 금지” negative prompt)으로 만듭니다.</p></details>
<h3 id="glossary">3-3. 용어 풀이</h3>
<dl class="kv" style="grid-template-columns:150px minmax(0,1fr)">
  <dt>확산 모델</dt><dd>잡음에서 시작해 잡음을 조금씩 걷어 내며 그림을 만드는 모델. 걷어 내는 횟수가 <b>스텝</b>입니다.</dd>
  <dt>DDPM / DDIM</dt><dd>잡음을 걷어 내는 규칙(샘플러). DDPM은 매 스텝 무작위성을 더하고, DDIM은 결정적으로 건너뛰어 적은 스텝에서도 형태를 잘 유지합니다.</dd>
  <dt>CFG</dt><dd>Classifier-free guidance. 조건이 있는 예측과 없는 예측의 차이를 키워 프롬프트를 더 강하게 따르게 합니다. 스케일이 클수록 프롬프트를 잘 따르지만 다양성이 줄고, 지나치면 색이 과해집니다. 스텝마다 예측을 두 번 하므로 느려집니다.</dd>
  <dt>negative prompt</dt><dd>CFG의 ‘조건 없는’ 쪽을 “피하고 싶은 것”으로 바꾸는 방법. 그래서 CFG가 1보다 클 때만 효과가 있습니다.</dd>
  <dt>증류(SD-Turbo)</dt><dd>큰 모델의 여러 스텝 결과를 1~4스텝에 내도록 다시 학습시킨 모델. SD-Turbo는 적대적 확산 증류(ADD)를 썼고 CFG 없이 씁니다.</dd>
  <dt>잠재 공간 / VAE</dt><dd>Stable Diffusion은 그림을 VAE로 압축한 4채널 잠재(768×432 → 96×54)에서 확산하고, 마지막에 VAE 디코더로 그림을 복원합니다.</dd>
  <dt>x̂₀</dt><dd>스텝마다 모델이 “지금 잡음을 다 걷어 내면 이런 그림일 것”이라고 예측한 깨끗한 잠재. 디노이징 미리보기에 씁니다.</dd>
  <dt>77토큰</dt><dd>CLIP 텍스트 인코더가 한 번에 읽는 최대 길이. 넘으면 뒷부분이 잘립니다.</dd>
</dl>

<h2 id="overview">4. 실험 한눈에</h2>
<div class="tbl"><table><thead><tr><th>실험</th><th>질문</th><th>바꾼 것</th><th>표본</th><th>결론</th><th>비용</th></tr></thead><tbody>
<tr><td><a href="#detect">감지 평가</a></td><td>규칙 감지기가 요청만 골라내는가</td><td>—</td><td>발화 60개</td><td><span class="tag ok">성공</span>56/60, 놓친 요청 0, 잘못 생성 1</td><td>0</td></tr>
<tr><td><a href="#api">실제 API 점검</a></td><td>실제 서비스로 끝까지 도는가</td><td>—</td><td>단계별 1회</td><td><span class="tag ok">동작</span>그림이 지연의 대부분</td><td>약 2센트</td></tr>
<tr><td><a href="#speed">속도 기준선</a></td><td>로컬 모델은 얼마나 빠른가</td><td>모델, 스텝, slicing</td><td>설정별 2~3회</td><td>Turbo 0.5~1초, SD 1.5 5~26초</td><td>0</td></tr>
<tr><td><a href="#x1">X1</a></td><td>샘플러·스텝이 품질을 바꾸나</td><td>DDPM/DDIM × 50/25/10</td><td>12장면 × 2시드</td><td><span class="tag no">CLIP 차이 없음</span>눈으로는 DDPM 10스텝이 깨짐</td><td>0</td></tr>
<tr><td><a href="#x2">X2</a></td><td>CFG를 키우면?</td><td>CFG 1/3/5/7.5/12</td><td>12 × 2</td><td>일치도 오르다 5 근처에서 정체, 다양성 하락</td><td>0</td></tr>
<tr><td><a href="#x3">X3</a></td><td>증류 모델이 실시간에 맞나</td><td>SD-Turbo 1/2/4 대 SD 1.5</td><td>12 × 2</td><td><span class="tag ok">채택</span>약 16배 빠르고 CLIP도 높음</td><td>0</td></tr>
<tr><td><a href="#x5">X5</a></td><td>약한 CFG로 가짜 글자가 줄까</td><td>Turbo CFG 0/1.5/2/3</td><td>12 × 2</td><td><span class="tag no">효과 없음</span></td><td>0</td></tr>
<tr><td><a href="#x4">X4</a></td><td>강의 맥락이 그림을 의도에 가깝게 하나</td><td>요청만 대 요청 + 맥락</td><td>시나리오 42개(그림 짝 28)</td><td><span class="tag ok">효과 있음</span>+2.10, p=0.010</td><td>기획 LLM 약 4센트</td></tr>
<tr><td><a href="#glyph">글자 규칙</a></td><td>기획 프롬프트로 가짜 글자를 줄일까</td><td>규칙 전/후</td><td>34장씩</td><td><span class="tag no">효과 없음</span>77토큰 초과는 감소</td><td>X4에 포함</td></tr>
<tr><td><a href="#tok77">77토큰</a></td><td>(X4 중 발견한 버그)</td><td>—</td><td>18개 프롬프트</td><td><span class="tag ok">수정</span>토큰 단위 맞춤</td><td>0</td></tr>
<tr><td><a href="#e2e">실제 서버 E2E</a></td><td>로컬 경로가 실제로 빠른가</td><td>—</td><td>1회</td><td>요청 → 완성 6.2초</td><td>1센트 미만</td></tr>
<tr><td><a href="#preview">미리보기 확인</a></td><td>디노이징 과정이 화면에 잘 보이나</td><td>—</td><td>1회</td><td>미리보기 23장, 화면 오류 0</td><td>0</td></tr>
</tbody></table></div>

<h2 id="details">5. 실험별 상세</h2>

<section class="card" id="detect">
<h3>5-1. 요청 감지 정확도 <span class="tag">규칙 기반 · API 미사용</span></h3>
<dl class="kv"><dt>질문</dt><dd>일반 설명은 무시하고, 실제 요청만 골라내는가? 애매하면 되묻는가?</dd>
<dt>방법</dt><dd><code>eval/detection_cases.jsonl</code>의 발화 60개를 확정 음성 인식 구간처럼 0.8초 간격으로 넣고 2.6초 침묵시킵니다. 정답은 3분류: 생성(request 25) / 입력 보완(needs_input 8) / 무시(none 27). 결정적이라 몇 번 돌려도 결과가 같습니다(2026-11-24 재실행 결과도 동일).</dd></dl>
<div class="tbl"><table><thead><tr><th>범주</th><th>뜻</th><th class="num">정답</th></tr></thead><tbody>
<tr><td>clear</td><td>명확한 지시</td><td class="num">10/10</td></tr>
<tr><td>split</td><td>여러 음성 구간으로 나뉜 지시</td><td class="num">4/4</td></tr>
<tr><td>normal</td><td>일반 설명(생성하면 안 됨)</td><td class="num">6/8</td></tr>
<tr><td>negated</td><td>부정 지시(“만들지 마세요”)</td><td class="num">5/5</td></tr>
<tr><td>quoted</td><td>인용된 지시(“…라고 말하면”)</td><td class="num">3/4</td></tr>
<tr><td>ambiguous</td><td>모호한 지시(“그거 설명할게요”)</td><td class="num">4/5</td></tr>
<tr><td>truncated</td><td>중간에 끊긴 지시</td><td class="num">4/4</td></tr>
<tr><td>added / added_negative</td><td>나중에 추가한 구어 표현(생성 / 비생성)</td><td class="num">7/7 · 9/9</td></tr>
<tr><td>real_user</td><td>실제 사용 중 나온 전사</td><td class="num">4/4</td></tr>
</tbody></table></div>
<p><b>결과</b>: 56/60(93.3%). 요청을 놓친 경우 0건, 생성하면 안 되는데 생성한 경우 1건(“그거, 아까 그 예시 설명할게요.” → ‘예시’를 주제로 인정). 나머지 3건은 생성하지 않을 발화를 ‘입력 보완’으로 잘못 띄운 경우라 슬라이드는 생기지 않지만 불필요한 카드가 뜹니다.</p>
<p><b>한계</b>: 실제 전사 4건 외에는 규칙을 만든 개발자가 쓴 사례라 결과가 낙관적입니다. 오답에 맞춰 규칙을 다시 고치지는 않았습니다.</p>
</section>

<section class="card" id="api">
<h3>5-2. 실제 API 점검과 지연 <span class="tag">n=1</span></h3>
<dl class="kv"><dt>질문</dt><dd>실제 서비스(Gemini, OpenAI)로 끝까지 동작하는가? 어디서 시간이 걸리는가?</dd>
<dt>방법</dt><dd><code>eval/check_providers.py</code>로 단계별 1회 호출, 앱에서 텍스트 입력과 실제 마이크로 전체 흐름 1회씩(2026-11-05).</dd></dl>
<div class="tbl"><table><thead><tr><th>단계</th><th>결과 (각 1회)</th></tr></thead><tbody>
<tr><td>Gemini 연결</td><td>1차는 “선불 크레딧 소진” 오류. 결제가 연결되지 않은 프로젝트의 키로 바꿔 성공, 준비까지 812ms</td></tr>
<tr><td>한국어 전사 (TTS 음성 5.8초)</td><td>1글자 차이(“학생에” → “학생의”), 구간 종료 → 확정 409ms. 이 문장으로 감지기가 정상적으로 요청 판단</td></tr>
<tr><td>기획 <code>gpt-6-luna</code></td><td>6.96초, 토큰 765/291, 약 $0.00022</td></tr>
<tr><td>그림 <code>gpt-image-2</code> low 1536×864</td><td>13.9초, 약 $0.0043, 글자 없음(눈으로 확인)</td></tr>
<tr><td>전체 흐름 (텍스트 입력)</td><td>요청 확정 → 텍스트 5.7초 → 그림 14.3초 → <b>완성 20.0초</b></td></tr>
<tr><td>전체 흐름 (실제 마이크)</td><td>발화 종료(VAD 추정) → 확정 자막 0.42초, 기획 4.3초, 그림 18.6초, <b>완성 23.4초</b></td></tr>
<tr><td>형태 선택 (G·H)</td><td>“수식으로” → 수식형, 형태 지정 없음 → 모델이 수식형 선택, “비유해서” → 그림형, “비교해서” → 비교형, “표로” → 표, “그래프로” → 함수 그래프. 재요청 0회</td></tr>
</tbody></table></div>
<p><b>해석</b>: 그림이 전체 시간의 70~80%를 차지했습니다. 이 결과가 ① 텍스트를 먼저 보여 주는 구조와 ② 이미지 단계를 로컬 확산 모델로 바꾸는 실험(X1~X5)의 출발점입니다.</p>
<p><b>한계</b>: 모두 1회 측정이라 네트워크·서버 상태에 따른 변동을 모릅니다. 반복 측정 도구(<code>eval/latency_probe.py -n</code>)는 있지만 실행하지 않았습니다.</p>
</section>

<section class="card" id="speed">
<h3>5-3. 속도 기준선 <span class="tag">로컬</span></h3>
<dl class="kv"><dt>질문</dt><dd>이 노트북에서 로컬 모델은 그림 1장에 얼마나 걸리는가?</dd>
<dt>방법</dt><dd><code>eval/diffusion/bench_speed.py</code>, 768×432, 설정별 2~3회 반복(워밍업 제외) 중앙값.</dd></dl>
<div class="tbl"><table><thead><tr><th>모델</th><th>설정</th><th class="num">시간 중앙값</th></tr></thead><tbody>
<tr><td>SD-Turbo</td><td>1 / 2 / 4스텝, CFG 없음</td><td class="num">0.49 / 0.67 / 0.97초</td></tr>
<tr><td>SD 1.5</td><td>50 / 25 / 10스텝, CFG 7.5, attention slicing</td><td class="num">26.0 / 12.0 / 5.3초</td></tr>
<tr><td>SD 1.5</td><td>같은 설정, slicing 없음</td><td class="num">64.7 / 30.5 / 13.9초</td></tr>
<tr><td>(참고) gpt-image-2 API</td><td>low, 1536×864</td><td class="num">14~19초 (n=1)</td></tr>
</tbody></table></div>
<ul class="list"><li>SD 1.5는 메모리 압박(스왑 약 10GB) 때문에 느렸고, attention slicing을 켜면 2.5배 빨라졌습니다. SD-Turbo는 slicing을 켜면 오히려 느려져 끕니다.</li>
<li>CFG를 켜면 스텝마다 예측을 두 번 하므로 10스텝 기준 3.4초 → 5.4초(약 1.6배)였습니다.</li></ul>
</section>

<section class="card" id="x1">
<h3>5-4. X1 · 샘플러와 스텝 수 <span class="tag">SD 1.5, CFG 7.5</span></h3>
<dl class="kv"><dt>질문</dt><dd>DDPM과 DDIM, 스텝 50/25/10이 장면 일치도와 시간을 어떻게 바꾸는가?</dd>
<dt>방법</dt><dd>12장면 × 시드 2 × 6조건 = 144장. <code>run_sweep.py --name x1_sampler --model sd15 --schedulers ddpm ddim --steps 50 25 10 --cfg 7.5</code></dd></dl>
<div class="tbl"><table><thead><tr><th>샘플러</th><th class="num">스텝</th><th class="num">CLIP (95% CI)</th><th class="num">다양성</th><th class="num">시간</th></tr></thead><tbody>
<tr><td>DDPM</td><td class="num">50</td><td class="num">25.4 (22.9–27.7)</td><td class="num">0.148</td><td class="num">22.1초</td></tr>
<tr><td>DDPM</td><td class="num">25</td><td class="num">25.4 (23.0–27.7)</td><td class="num">0.168</td><td class="num">11.2초</td></tr>
<tr><td>DDPM</td><td class="num">10</td><td class="num">25.5 (23.4–27.4)</td><td class="num">0.168</td><td class="num">4.7초</td></tr>
<tr><td>DDIM</td><td class="num">50</td><td class="num">24.5 (22.5–26.2)</td><td class="num">0.158</td><td class="num">21.9초</td></tr>
<tr><td>DDIM</td><td class="num">25</td><td class="num">25.0 (23.0–26.9)</td><td class="num">0.182</td><td class="num">11.1초</td></tr>
<tr><td>DDIM</td><td class="num">10</td><td class="num">25.1 (23.7–26.7)</td><td class="num">0.159</td><td class="num">4.7초</td></tr>
</tbody></table></div>
{figure("docs/images/diffusion_x1_sampler.jpg", "X1 샘플러·스텝 비교 그림", "같은 장면·시드에서 샘플러와 스텝만 바꾼 결과")}
<ul class="list"><li><b>시간은 스텝 수에 거의 비례</b>합니다. 같은 U-Net을 덜 부를 뿐 모델이 작아지는 것은 아닙니다.</li>
<li><b>CLIP으로는 조건 간 차이가 없었습니다.</b> 신뢰구간이 모두 겹칩니다.</li>
<li><b>눈으로 보면 차이가 큽니다.</b> DDPM 10스텝은 형체가 뭉개졌고(P06 고양이가 거의 사라짐, P07 인물이 흐림), DDIM 10스텝은 형태를 유지했습니다. “DDIM은 적은 스텝에서도 쓸 만하다”는 강의 내용과 같습니다.</li></ul>
<div class="warn"><b>교훈</b>: CLIP 유사도는 그림이 문장과 맞는지만 보고, 그림이 깨졌는지는 잡지 못합니다. 그래서 이후 해석은 CLIP과 눈 확인을 함께 썼고, 사람 평가를 남은 일로 둡니다.</div>
</section>

<section class="card" id="x2">
<h3>5-5. X2 · CFG 스케일 <span class="tag">SD 1.5, DDIM 25스텝</span></h3>
<dl class="kv"><dt>질문</dt><dd>가이던스를 키우면 장면 일치도와 다양성이 어떻게 바뀌는가? (17강 7쪽: 조건은 잘 따르지만 다양성이 줄 수 있다)</dd>
<dt>방법</dt><dd>CFG 1 / 3 / 5 / 7.5 / 12, 12장면 × 시드 2. CFG&gt;1일 때 “글자 금지” negative prompt.</dd></dl>
<div class="grid2"><div class="chartbox">{x2a}</div><div class="chartbox">{x2b}</div></div>
<p class="meta">세로 막대는 95% 신뢰구간. 점에 마우스를 올리면 값이 보입니다. 시간: CFG 1은 6.5초, 3~12는 약 11.3초.</p>
{figure("docs/images/diffusion_x2_cfg.jpg", "X2 CFG 스케일 비교 그림", "P02·P09 장면, 시드 0·1에서 CFG만 바꾼 결과")}
<ul class="list"><li><b>CFG를 올리면 일치도가 21.5에서 25.7까지 오르다가 5 근처에서 멈춥니다.</b> 1과 5의 구간은 겹치지 않고, 5·7.5·12 사이는 구분되지 않습니다.</li>
<li><b>다양성은 계속 떨어집니다</b>(0.27 → 0.18). 강의에서 배운 트레이드오프와 같은 방향입니다.</li>
<li>눈으로 보면 CFG 1은 장면이 거의 형성되지 않고, 7.5~12에서 또렷해지며, 12에서는 색이 진해지고 단순해집니다.</li>
<li>CFG 1이 빠른 이유: diffusers는 1 이하에서 조건 없는 예측을 건너뜁니다.</li>
<li>negative prompt로도 글자가 완전히 막히지 않았습니다(P09 시드 0은 CFG 3~12 모두 왼쪽에 글줄 무늬).</li></ul>
</section>

<section class="card" id="x3">
<h3>5-6. X3 · 증류 모델 SD-Turbo 대 SD 1.5</h3>
<dl class="kv"><dt>질문</dt><dd>1~4스텝으로 증류된 모델이 실시간 강의에 맞는가? 품질 손해는 없는가?</dd>
<dt>방법</dt><dd>SD-Turbo 1/2/4스텝(CFG 0)과 X1의 SD 1.5 DDIM 25스텝(CFG 7.5)을 같은 장면·시드로 비교.</dd></dl>
<div class="chartbox">{x3}</div>
<div class="tbl"><table><thead><tr><th>모델·설정</th><th class="num">CLIP (95% CI)</th><th class="num">다양성</th><th class="num">시간</th></tr></thead><tbody>
<tr><td>SD-Turbo 1스텝</td><td class="num">29.2 (27.0–31.3)</td><td class="num">0.129</td><td class="num">0.51초</td></tr>
<tr><td>SD-Turbo 2스텝 (시스템 기본값)</td><td class="num">28.2 (26.3–29.9)</td><td class="num">0.136</td><td class="num">0.68초</td></tr>
<tr><td>SD-Turbo 4스텝</td><td class="num">28.2 (25.9–30.4)</td><td class="num">0.145</td><td class="num">0.99초</td></tr>
<tr><td>SD 1.5 DDIM 25스텝, CFG 7.5</td><td class="num">25.0 (23.0–26.9)</td><td class="num">0.182</td><td class="num">11.1초</td></tr>
</tbody></table></div>
{figure("docs/images/diffusion_x3_turbo.jpg", "X3 SD-Turbo와 SD 1.5 비교 그림", "P01·P06·P07: SD-Turbo 1스텝, 4스텝, SD 1.5 DDIM 25스텝")}
<ul class="list"><li><b>SD-Turbo는 약 16~20배 빠르면서 장면 일치도도 높았습니다.</b> SD-Turbo 1스텝과 SD 1.5의 구간은 거의 겹치지 않습니다. 눈으로 봐도 장면 요소를 더 많이 담습니다.</li>
<li><b>주의</b>: SD-Turbo는 SD 2.1 기반이고 텍스트 인코더도 더 큽니다(OpenCLIP ViT-H). 그래서 이 차이를 증류 효과만으로 볼 수는 없습니다.</li>
<li><b>약점</b>: 가짜 글자(P01 4스텝의 종이에 의미 없는 글자). CFG를 쓰지 않아 negative prompt가 들어갈 자리가 없습니다 → X5로 이어짐.</li>
<li>다양성은 SD-Turbo가 낮습니다. 시드가 2개뿐이라 경향으로만 봅니다.</li>
<li><b>결정</b>: 시스템 기본값을 SD-Turbo 2스텝, CFG 0으로 정했습니다.</li></ul>
</section>

<section class="card" id="x5">
<h3>5-7. X5 · SD-Turbo에 약한 CFG를 켜면 가짜 글자가 줄어드는가 <span class="tag no">효과 없음</span></h3>
<dl class="kv"><dt>질문</dt><dd>CFG를 조금 켜서 negative prompt(“글자 금지”)가 작동하게 하면 가짜 글자가 줄까?</dd>
<dt>방법</dt><dd>SD-Turbo 2·4스텝 × CFG 0 / 1.5 / 2 / 3, 12장면 × 시드 2. 시드 0의 12장면을 CFG 0 / 1.5 / 2로 나란히 놓고 눈으로 확인(블라인드 평가 아님).</dd></dl>
<div class="tbl"><table><thead><tr><th class="num">스텝</th><th class="num">CFG</th><th class="num">CLIP (95% CI)</th><th class="num">시간</th></tr></thead><tbody>
<tr><td class="num">2</td><td class="num">0</td><td class="num">28.2 (26.3–29.9)</td><td class="num">0.63초</td></tr>
<tr><td class="num">2</td><td class="num">1.5</td><td class="num">28.2 (26.0–30.3)</td><td class="num">0.83초</td></tr>
<tr><td class="num">2</td><td class="num">2</td><td class="num">28.3 (26.1–30.4)</td><td class="num">0.85초</td></tr>
<tr><td class="num">2</td><td class="num">3</td><td class="num">29.3 (27.0–31.5)</td><td class="num">0.87초</td></tr>
<tr><td class="num">4</td><td class="num">0</td><td class="num">28.2 (25.9–30.4)</td><td class="num">0.97초</td></tr>
<tr><td class="num">4</td><td class="num">1.5</td><td class="num">28.2 (25.4–30.8)</td><td class="num">1.39초</td></tr>
<tr><td class="num">4</td><td class="num">2</td><td class="num">27.9 (25.5–30.3)</td><td class="num">1.40초</td></tr>
<tr><td class="num">4</td><td class="num">3</td><td class="num">27.0 (24.7–29.1)</td><td class="num">1.39초</td></tr>
</tbody></table></div>
{figure("docs/images/diffusion_x5_turbo_cfg_a.jpg", "X5 SD-Turbo CFG 비교 그림", "시드 0, CFG 0 / 1.5 / 2 비교(일부 장면)")}
<ul class="list"><li>글줄 모양의 가짜 글자는 P01(시험지 더미)과 P08(답안지) 두 장면에서 <b>세 조건 모두</b> 똑같이 나타났습니다. 장면이 종이·문서를 요구하니 모델이 그 위에 글줄을 그립니다.</li>
<li>CFG를 켜면 시간이 1.3~1.4배 늘고, CFG 3에서는 색이 과하게 진해졌습니다(17강 30쪽 “가이던스가 지나치면 과포화”).</li></ul>
<h4>실패한 자동 지표: CLIP으로 “글자 섞임” 판정</h4>
<p>“글자가 쓰인 그림” 대 “글자 없는 그림”의 CLIP 확률로 가짜 글자를 자동 판정하려 했습니다. 확률 상위 6장을 직접 보니 실제 글자 모양은 1장(P01)뿐이었고, 진하고 장식적인 그림체에 반응하는 것으로 보였습니다. <b>이 지표는 쓰지 않기로 했습니다.</b> 글자 섞임은 사람이 판정해야 합니다.</p>
{figure("docs/images/diffusion_x5_textproxy_check.jpg", "CLIP 글자 판정 상위 6장 검증", "CLIP이 ‘글자 있음’ 확률을 높게 준 상위 6장. 실제 글자는 1장뿐")}
</section>

<section class="card" id="x4">
<h3>5-8. X4 · 강의 맥락 조건의 효과 <span class="tag ok">핵심 실험</span></h3>
<dl class="kv"><dt>질문</dt><dd>요청에 강의 맥락(최근 발화 + 현재 장)을 붙이면, 그림이 강사가 의도한 장면에 더 가까워지는가?</dd></dl>
<h4>설계</h4>
<div class="tbl"><table><thead><tr><th></th><th>A: 요청만</th><th>B: 요청 + 맥락</th></tr></thead><tbody>
<tr><td>기획 LLM 입력</td><td>요청 문장 + 강의 제목·청중</td><td>A + 최근 발화 3문장 + 현재 장(제목·핵심 문장)</td></tr>
<tr><td>고정한 것</td><td colspan="2">기획 LLM(<code>gpt-6-luna</code>, 같은 시스템 프롬프트), 이미지 모델(SD-Turbo 2스텝, CFG 0), 시드 0·1, 해상도</td></tr>
<tr><td>채점</td><td colspan="2">시나리오마다 미리 적어 둔 “강사가 의도한 그림” 영어 한 문장(정답 장면)과 그림의 CLIP 유사도(시드 2개 평균). 같은 방식으로 기획 LLM이 쓴 그림 묘사(글)와 정답 장면의 유사도도 계산</td></tr>
<tr><td>검정</td><td colspan="2">A·B 모두 그림이 나온 시나리오끼리 짝 비교, 순열 검정(20,000회)과 부트스트랩 95% CI</td></tr>
</tbody></table></div>
<div class="grid2">
<div class="scen"><b>S09</b> · 한국사 · 중학생<br>발화: “조선의 과거 시험은 관리를 뽑는 시험이었습니다. … 선비는 며칠을 걸어서 한양에 도착했습니다.”<br>현재 장: 과거 시험 보러 가는 길<br><span class="q">요청: “다음 슬라이드에서는 시험장 풍경을 보여주세요.”</span><br><span class="muted">정답 장면: a crowded Joseon dynasty civil service examination ground with scholars in traditional robes writing at mats</span></div>
<div class="scen"><b>L06</b> · 생성형 AI: 확산 모델 I · 대학 3학년<br>발화: “… 잉크 한 방울을 물에 떨어뜨리면 점점 퍼져서 결국 균일해지는 것과 같다고 했습니다.”<br>현재 장: 순방향: 잡음 더하기<br><span class="q">요청: “다음 슬라이드에서는 역방향 과정을 같은 비유로 보여주세요.”</span><br><span class="muted">정답 장면: a glass of water where spread-out ink gradually gathers back into a single drop, shown as a reversed sequence</span></div>
</div>
<p class="meta">요청만 보면 S09는 “어느 시대의 시험장”인지, L06은 “같은 비유”가 무엇인지 알 수 없습니다. 이런 지시어 요청에서 맥락이 필요합니다.</p>

<h4>1차 (시나리오 12개)</h4>
<p>일반 과목 시나리오 12개(<code>eval/context_scenarios.json</code>)로 먼저 돌렸습니다. 그림 B−A 평균 +1.07(95% CI −0.33~+2.78), B 우세 5/7. <b>방향은 맥락 쪽이었지만 짝이 7개뿐이라 확실하지 않았습니다.</b> 맥락이 없으면 2개 시나리오에서 되물었습니다. 그래서 표본을 늘렸습니다.</p>

<h4>확장 (시나리오 42개)</h4>
<ul class="list"><li>이 수업 강의자료(12강 VAE, 17강 DDIM·CFG·잠재 확산, 목차의 GAN·DiT·플로 매칭·ControlNet·LoRA·비디오·평가)로 시나리오 30개(L01~L30)를 추가했습니다(<code>eval/context_scenarios_lecture.json</code>).</li>
<li>시나리오와 정답 장면(<code>eval/diffusion/x4_gold.json</code>)은 개발 보조 AI(Claude)가 썼고, <b>생성 전에 커밋해 고정</b>했습니다(<code>d1a4ce0</code>).</li>
<li>42개 × A/B를 새로 기획했습니다(기획 LLM 비용 약 $0.03). 이때 기획 프롬프트에는 <a href="#glyph">빈 면·50단어 규칙</a>이 들어 있었고 A·B 모두 같습니다.</li></ul>
<div class="tbl"><table><thead><tr><th>조건</th><th class="num">그림</th><th class="num">비교표</th><th class="num">텍스트·수식</th><th class="num">되묻기</th></tr></thead><tbody>
<tr><td>A 요청만</td><td class="num">30</td><td class="num">5</td><td class="num">0</td><td class="num"><b>7</b></td></tr>
<tr><td>B 요청 + 맥락</td><td class="num">35</td><td class="num">5</td><td class="num">2</td><td class="num"><b>0</b></td></tr>
</tbody></table></div>
<div class="tbl"><table><thead><tr><th>지표 (그림이 있는 짝 28개)</th><th class="num">B−A</th><th class="num">95% CI</th><th class="num">B 우세</th><th class="num">p</th></tr></thead><tbody>
<tr><td><b>그림 ↔ 정답 장면</b></td><td class="num"><b>+2.10</b></td><td class="num">+0.65 ~ +3.61</td><td class="num">17/28</td><td class="num"><b>0.010</b></td></tr>
<tr><td>그림 묘사(글) ↔ 정답 장면</td><td class="num">+6.41</td><td class="num">+2.98 ~ +10.13</td><td class="num">20/28</td><td class="num">0.002</td></tr>
<tr><td>그림 · 요청에 지시어 있음(“그 비유”, “이걸”, “방금”)</td><td class="num">+1.81</td><td class="num">+0.22 ~ +3.48</td><td class="num">11/19</td><td class="num">0.048</td></tr>
<tr><td>그림 · 지시어 없음</td><td class="num">+2.72</td><td class="num">−0.12 ~ +5.72</td><td class="num">6/9</td><td class="num">0.142</td></tr>
</tbody></table></div>
<div class="chartbox">{x4_chart()}</div>
<p class="meta">막대에 마우스를 올리면 A·B 점수와 글 단계 차이가 보입니다. 초록은 맥락 쪽이 높은 시나리오, 주황은 낮은 시나리오.</p>
{figure("docs/images/diffusion_x4_n42_examples.jpg", "X4 맥락 없음과 있음 비교 그림", "왼쪽 A(요청만), 오른쪽 B(요청 + 맥락). S09 현대 교실 → 조선 시대 시험장, L06 설경 → 잉크 비유, L24 로봇 → 온도계 비유, L26 회로 → 고양이 사진 분포")}
<details><summary>시나리오별 원자료 표 보기</summary>{x4_table()}<p class="meta">출처: <code>eval/results/diffusion/x4_context_n42/summary.md</code></p></details>
<h4>해석</h4>
<ul class="list"><li><b>강의 맥락을 조건에 넣으면 그림이 강사가 의도한 장면에 더 가까워집니다(p=0.010).</b> 맥락이 없으면 42개 중 7개에서 가리키는 대상을 몰라 되물었습니다(엉뚱한 그림 대신 되물은 것이라 올바른 동작입니다).</li>
<li><b>효과가 글(+6.41)에서 그림(+2.10)으로 가며 약 1/3로 줄었습니다.</b> 기획 LLM은 맥락을 잘 반영했지만, SD-Turbo가 그것을 다 그리지 못했다는 뜻입니다. 이미지 모델이 병목입니다.</li>
<li>반대로 B가 낮은 경우도 있었습니다(L17 −5.0, L15 −4.0, L08 −3.0). 맥락의 비유를 넣으며 장면이 복잡해져 그림이 덜 맞은 것으로 보입니다.</li></ul>
<div class="warn"><b>한계</b>: 시나리오와 정답을 같은 쪽(개발 보조 AI)이 썼습니다. 지표가 CLIP 하나뿐입니다. 지시어 분류는 정규식입니다. 사람이 평가해도 같은 결론이 나오는지는 아직 확인하지 않았습니다.</div>
</section>

<section class="card" id="glyph">
<h3>5-9. 가짜 글자 대책: 기획 프롬프트 규칙 <span class="tag no">효과 없음</span></h3>
<dl class="kv"><dt>질문</dt><dd>기획 LLM에 “종이·화면·간판은 blank/empty/simple icons로 묘사하라, 그림 묘사는 영어 50단어 이내”라고 지시하면 가짜 글자가 줄까?</dd>
<dt>방법</dt><dd>X4의 S 시나리오 12개에서 규칙 전후의 그림 묘사와 그림(각 34장)을 비교. 가짜 글자는 직접 눈으로 셌습니다.</dd></dl>
<div class="tbl"><table><thead><tr><th></th><th class="num">규칙 전</th><th class="num">규칙 후</th></tr></thead><tbody>
<tr><td>그림 묘사에 blank·empty 언급</td><td class="num">2/18</td><td class="num">9/17</td></tr>
<tr><td>77토큰 초과</td><td class="num">18/18</td><td class="num"><b>7/17</b></td></tr>
<tr><td>토큰 수 중앙값</td><td class="num">95</td><td class="num"><b>73</b></td></tr>
<tr><td>가짜 글자가 보이는 그림</td><td class="num">약 9/34</td><td class="num">약 9/34</td></tr>
</tbody></table></div>
<p>LLM은 지시를 따랐지만, SD-Turbo는 영화관 간판(“MOVE NAKE”)이나 시험지 장면에서 계속 글자를 그렸습니다. <b>텍스트 모델은 지시를 따랐지만 이미지 모델은 따르지 못한 사례</b>입니다. 대신 50단어 규칙 덕분에 77토큰 잘림은 크게 줄었습니다. 가짜 글자는 알려진 한계로 두고, 품질이 중요하면 <code>gpt-image-2</code>로 바꿔 쓸 수 있습니다.</p>
</section>

<section class="card" id="tok77">
<h3>5-10. 실험 중 발견한 버그: 77토큰 잘림 <span class="tag ok">수정</span></h3>
<p>기획 LLM이 쓴 그림 묘사는 장면만으로도 <b>18개 모두 77토큰을 넘었습니다(78~110)</b>. 그래서 장면 뒷부분과 그 뒤에 붙인 화풍 문구가 잘리고 있었습니다. 개발자가 쓴 짧은 장면(X1~X3, 최대 57토큰)에서는 드러나지 않았던 문제입니다.</p>
<p><b>수정</b>: 모델의 토크나이저로 길이를 세서, 화풍 문구는 남기고 장면을 문장 단위로(필요하면 단어 단위로) 줄입니다(<code>compose_sd_prompt</code>). X4의 그림은 이 수정 뒤에 만들었습니다.</p>
</section>

<section class="card" id="e2e">
<h3>5-11. 실제 서버에서 로컬 경로 확인 <span class="tag">n=1</span></h3>
<p>실제 서버를 <code>IMAGE_PROVIDER=local</code>(SD-Turbo 2스텝)로 켜고 실제 기획 LLM으로 요청 1건을 처리했습니다(2026-11-17).</p>
<div class="chartbox">{stacked_latency()}</div>
<div class="tbl"><table><tbody>
<tr><td>서버 시작 시 모델 미리 로드</td><td class="num">4.5초 (서버 시작은 막지 않음)</td></tr>
<tr><td>요청 확정 → 텍스트 기획 완료</td><td class="num">5.0초</td></tr>
<tr><td>그림 생성</td><td class="num">1.2초</td></tr>
<tr><td><b>요청 확정 → 그림까지 완성</b></td><td class="num"><b>6.2초</b></td></tr>
</tbody></table></div>
{figure("docs/images/local_sdturbo_e2e.jpg", "실제 서버에서 SD-Turbo로 만든 그림", "요청한 장면(시험지 더미 속에서 고민하는 학생)은 맞았지만, 종이에 의미 없는 글자(“IMCABRGR”)가 보입니다.", "narrow")}
<p class="meta">두 경로 모두 1회 측정이고 측정 날짜가 다릅니다. 이제 남은 시간의 대부분은 기획 LLM(약 5초)입니다.</p>
</section>

<section class="card" id="preview">
<h3>5-12. 디노이징 과정 보여 주기 <span class="tag ok">구현</span></h3>
<p>확산 모델이 그림을 만드는 동안 매 스텝 스케줄러가 계산하는 <b>예측된 깨끗한 잠재 x̂₀</b>를 가로채 그림 자리에 보여 줍니다(17강 3쪽 “Estimate clean image”).</p>
<div class="formula">x̂₀ = ( x<sub>t</sub> − √(1 − ᾱ<sub>t</sub>) · ε̂ ) / √ᾱ<sub>t</sub></div>
<ol class="steps"><li>스케줄러의 <code>step</code>을 감싸 <code>pred_original_sample</code>(x̂₀)을 꺼냅니다.</li>
<li>4채널 잠재를 고정된 4×3 선형 행렬로 RGB에 근사합니다. 매 스텝 VAE 디코더를 돌리지 않아 거의 공짜입니다(색은 근사).</li>
<li>96×54를 4배 키운 작은 JPEG를 0.12초 간격 이내로 <code>slide.preview</code> 이벤트로 보냅니다. 청중에게는 그 장을 보여 줄 수 있을 때만 보냅니다.</li>
<li>완성 그림이 오면 미리보기 위로 서서히 덮습니다.</li></ol>
{figure("docs/presentation/assets/denoise_strip.jpg", "디노이징 미리보기 4단계", "SD 1.5 DDIM 25스텝: 4/25, 12/25, 22/25 스텝의 x̂₀ 미리보기와 완성 그림")}
<ul class="list"><li><b>확인</b>: SD 1.5 25스텝 + mock 기획, 헤드리스 Chrome. 발표자 화면에 미리보기 23장(2/25~24/25), 청중 화면에 미리보기와 완성 그림, 화면 오류 0건.</li>
<li><b>발견·수정</b>: SD 1.5 기본 스케줄러(PNDM)는 x̂₀를 주지 않아 잡음만 보였습니다 → SD 1.5 기본을 DDIM으로 바꿨습니다. 미리보기가 완성 그림 위에 그려지던 쌓임 순서 문제도 고쳤습니다.</li>
<li>SD-Turbo(2스텝, 0.6초)는 너무 빨라 미리보기가 거의 보이지 않습니다. 과정을 보여 주는 시연은 <code>LOCAL_IMAGE_MODEL=sd15</code>(약 12초)로 합니다.</li></ul>
</section>

<h2 id="deck">6. 발표 PPT 해설</h2>
<div class="stats">
  <div class="stat"><b>13장 + 부록 3장</b><span>영어 발표, 16:9 와이드</span></div>
  <div class="stat"><b>약 10분</b><span>대본 기준 10분, 시연 2분 포함</span></div>
  <div class="stat"><b>영·한 대본</b><span>슬라이드 노트와 <code>script.md</code>에 같은 내용</span></div>
</div>
<p><b>구성</b>: 청자가 따라오기 쉽게 짰습니다. 문제 상황(2장)과 해결 장면(3장)을 먼저 보여 주고, 실제 발표자 화면으로 동작을 설명한 뒤(4장), 핵심 아이디어를 실제 그림 한 쌍으로 보여 줍니다(5장). 실험은 “빠른가?”, “가이던스는 무엇을 바꾸나?”, “맥락이 정말 도움이 되나?” 세 질문으로 풀었습니다. 장마다 메시지는 하나이고, 방법·신뢰구간 같은 세부는 말로 하거나 부록(14~16장)에 두었습니다.</p>
<p><b>디자인</b>: 발표자의 IR 자료 스타일을 따랐습니다. 밝은 회색 바탕에 흰 카드를 깔고, 장마다 위쪽에 “왼쪽 라벨 블록 + 핵심 메시지 한두 줄” 띠를 둡니다. 소제목은 대괄호 막대로 표시합니다. 색은 파랑(#285592·#2D66AD), 강조 빨강(#DD5C47), 남색(#183257)이고, 글꼴은 나눔스퀘어 네오입니다. 결과를 보여 주는 실험 장은 라벨 블록을 빨강으로, 문제·한계 장은 짙은 회색으로 구분했습니다. PowerPoint에서 바로 고칠 수 있는 편집형 PPTX이고, 발표할 컴퓨터에는 나눔스퀘어 네오를 먼저 설치해야 그대로 보입니다(<code>docs/presentation/fonts/README.md</code>).</p>
<h3 id="deck-flow">6-1. 흐름과 평가 기준</h3>
<div class="flow">
  <div class="box"><b>문제·장면</b>1~3장</div><span class="arrow">→</span>
  <div class="box"><b>동작·아이디어</b>4~6장</div><span class="arrow">→</span>
  <div class="box dark"><b>시연</b>7장</div><span class="arrow">→</span>
  <div class="box"><b>수업 개념</b>8장</div><span class="arrow">→</span>
  <div class="box"><b>실험 3개</b>9~11장</div><span class="arrow">→</span>
  <div class="box"><b>한계·정리</b>12~13장</div>
</div>
<div class="tbl"><table><thead><tr><th>평가 항목 (17강 9~10쪽)</th><th class="num">배점</th><th>PPT에서 다루는 곳</th></tr></thead><tbody>
<tr><td>창의성·독창성</td><td class="num">30</td><td>5장 강의 맥락 아이디어 · 2~3장 유용성 · 11장 검증 · 부록 14장 ZeroPrep 비교</td></tr>
<tr><td>기술 이해</td><td class="num">15~20</td><td>6장 17강과 설계 연결 · 8장 확산·DDIM·x̂₀ · 9~10장 증류·CFG</td></tr>
<tr><td>구현</td><td class="num">15~20</td><td>3~4장 실제 결과와 발표자 화면 · 7장 실시간 시연 · 부록 15장 수치</td></tr>
<tr><td>실험·분석</td><td class="num">20~25</td><td>9~11장 실험 3개(X3·X2·X4) · 12장 한계 · 부록 16장 측정 방법</td></tr>
<tr><td>발표·질의응답</td><td class="num">10~15</td><td>대본, 예상 질문 8개(아래 6-4)</td></tr>
</tbody></table></div>
<p class="meta">같은 쪽 안에서 막대와 표의 배점이 달라 범위로 적었습니다(<code>docs/evaluation-criteria-analysis.md</code>).</p>

<h3 id="deck-slides">6-2. 슬라이드별 설명</h3>
<div class="slides">
{slides_html(script)}
</div>

<h3 id="deck-demo">6-3. 시연 계획</h3>
<div class="warn"><b>중요</b>: 시스템은 한국어 강의용입니다(음성 인식 ko-KR, 감지 규칙도 한국어). 발표는 영어로 하고, <b>시스템에 거는 강의 문장만 한국어로 말한 뒤</b> 바로 영어로 옮깁니다.</div>
<div class="note">{demo_html(demo_lines)}</div>
<h4>시연 준비 점검</h4>
<ul class="list">
<li>서버: <code>cd backend && HF_HUB_DISABLE_XET=1 IMAGE_PROVIDER=local LOCAL_IMAGE_MODEL=sd15 .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000</code></li>
<li>프런트엔드: <code>cd frontend && npm run dev</code> → http://localhost:5173 (또는 빌드 후 8000번에서 바로)</li>
<li>세션을 미리 만들고, 청중 화면을 두 번째 창이나 프로젝터에 띄웁니다. 화면이 하나면 전체 화면 발표 모드(<kbd>M</kbd> 마이크, <kbd>→</kbd> 다음 장)를 씁니다.</li>
<li>마이크 권한, 네트워크(기획 LLM과 STT는 인터넷 필요)를 확인합니다.</li>
<li>같은 흐름을 녹화한 <b>백업 영상</b>을 준비합니다. 마이크가 안 되면 텍스트 입력의 “발화로 입력”에 같은 문장을 넣어 계속합니다.</li>
<li>시연을 발표 끝에 하려면 PowerPoint에서 7번 장을 13번 장 앞으로 옮깁니다.</li>
</ul>

<h3 id="deck-qa">6-4. 예상 질문과 답변</h3>
{qa_html(qa)}

<h2 id="limits">7. 한계와 남은 일</h2>
<ul class="list">
<li><b>사람 평가가 없습니다.</b> 모든 품질 판단은 CLIP과 개발자의 눈 확인입니다. X1에서 CLIP이 깨진 그림을 놓쳤으므로 블라인드 사람 평가(장면 적합성, 깨짐, 가짜 글자)가 가장 중요한 남은 일입니다.</li>
<li><b>평가 자료를 같은 쪽이 썼습니다.</b> 감지 평가 사례, X4 시나리오와 정답 장면 모두 개발 쪽(개발자·개발 보조 AI)이 작성했습니다. X4는 생성 전에 커밋해 고정했지만 작성 편향은 남습니다.</li>
<li><b>지연은 n=1입니다.</b> 반복 측정(n≥10, 중앙값·p90)이 필요합니다.</li>
<li><b>가짜 글자</b>: SD-Turbo는 종이·간판 장면에서 의미 없는 글자를 그립니다. 프롬프트 대책은 효과가 없었습니다.</li>
<li><b>한국어 전용</b>: 영어 강의에는 STT 언어 변경과 영어 요청 표현 추가가 필요합니다.</li>
<li><b>감지기는 규칙 기반</b>이라 “다음 장” 같은 말이 들어간 일반 문장을 입력 보완으로 띄우는 경우가 있습니다.</li>
<li><b>시간 측정 환경</b>: 이 Mac 한 대, 메모리 압박(스왑)이 있는 상태입니다.</li>
</ul>

<h2 id="repro">8. 재현 방법</h2>
<p>모든 명령은 저장소 루트에서 실행합니다. 확산 실험은 로컬 모델만 쓰므로 비용이 없고, ‘실제 API’라고 적은 것만 비용이 듭니다.</p>
<pre><code># 준비 (백엔드 venv + 로컬 이미지 패키지)
cd backend && uv venv --python 3.11 .venv && uv pip install -r requirements.txt --python .venv/bin/python
uv pip install -r requirements-local-image.txt --python .venv/bin/python && cd ..
export HF_HUB_DISABLE_XET=1          # Hugging Face 다운로드가 멈출 때

# 테스트와 감지 평가 (API 불필요)
(cd backend && .venv/bin/python -m pytest -q)
backend/.venv/bin/python eval/run_detection_eval.py

# 속도 기준선
backend/.venv/bin/python eval/diffusion/bench_speed.py --model sd-turbo --steps 1 2 4
backend/.venv/bin/python eval/diffusion/bench_speed.py --model sd15 --steps 50 25 10

# X1 / X2 / X3 / X5 생성 → 채점
backend/.venv/bin/python eval/diffusion/run_sweep.py --name x1_sampler --model sd15 --schedulers ddpm ddim --steps 50 25 10 --cfg 7.5
backend/.venv/bin/python eval/diffusion/run_sweep.py --name x2_cfg --model sd15 --schedulers ddim --steps 25 --cfg 1 3 5 7.5 12
backend/.venv/bin/python eval/diffusion/run_sweep.py --name x3_turbo --model sd-turbo --steps 1 2 4 --cfg 0
backend/.venv/bin/python eval/diffusion/run_sweep.py --name x5_turbo_cfg --model sd-turbo --steps 2 4 --cfg 0 1.5 2 3
backend/.venv/bin/python eval/diffusion/score_clip.py eval/results/diffusion/x2_cfg

# X4 (plan 단계만 실제 API: 기획 LLM, 약 $0.03)
backend/.venv/bin/python eval/diffusion/run_x4_context.py plan   --out x4_context_n42
backend/.venv/bin/python eval/diffusion/run_x4_context.py render --out x4_context_n42
backend/.venv/bin/python eval/diffusion/run_x4_context.py score  --out x4_context_n42

# 실제 API 점검 (비용 발생)
backend/.venv/bin/python eval/check_providers.py --stt | --text | --image
backend/.venv/bin/python eval/latency_probe.py -n 10

# 발표 자료 다시 만들기
NODE_PATH=&lt;pptxgenjs·react-icons·sharp가 설치된 node_modules&gt; node docs/presentation/build_deck.js
python3 docs/presentation/build_guide.py</code></pre>

<h2 id="files">9. 파일 지도</h2>
<div class="tbl"><table><thead><tr><th>위치</th><th>내용</th></tr></thead><tbody>
<tr><td><code>docs/presentation/NextSlide_final.pptx</code></td><td>발표 PPT (영어 본문 13장 + 부록 3장, 노트에 영·한 대본)</td></tr>
<tr><td><code>docs/presentation/script.md</code></td><td>발표 대본, 시연 대본, 예상 질문</td></tr>
<tr><td><code>docs/presentation/build_deck.js</code> · <code>build_guide.py</code></td><td>PPT·대본 생성 스크립트, 이 해설서 생성 스크립트</td></tr>
<tr><td><code>docs/presentation/fonts/README.md</code></td><td>덱 글꼴(나눔스퀘어 네오) 설치 안내</td></tr>
<tr><td><code>docs/diffusion-experiments.md</code></td><td>확산 실험 X1~X5, X4 상세 기록</td></tr>
<tr><td><code>docs/results.md</code></td><td>테스트, 실제 API 점검, 감지 평가, 미검증 항목</td></tr>
<tr><td><code>docs/architecture.md</code></td><td>구조와 데이터 흐름</td></tr>
<tr><td><code>docs/evaluation-criteria-analysis.md</code></td><td>기말 평가 기준 분석</td></tr>
<tr><td><code>docs/DEVLOG.md</code></td><td>날짜별 개발 기록</td></tr>
<tr><td><code>backend/app/providers/local_image.py</code></td><td>로컬 확산 제공자(SD-Turbo/SD 1.5, 77토큰 맞춤, x̂₀ 미리보기)</td></tr>
<tr><td><code>eval/diffusion/</code></td><td>실험 스크립트, 장면 세트(<code>prompts.json</code>), X4 정답 장면(<code>x4_gold.json</code>)</td></tr>
<tr><td><code>eval/context_scenarios*.json</code></td><td>X4 시나리오(일반 12개, 강의자료 기반 30개)</td></tr>
<tr><td><code>eval/results/diffusion/</code></td><td>실험 원자료(<code>runs.jsonl</code>, <code>scores.jsonl</code>, <code>summary.md</code>). 개별 그림은 저장소에 없음</td></tr>
</tbody></table></div>
"""

    toc = """
<details class="toc"><summary>목차</summary><ol>
<li><a href="#summary">1. 한눈에 보기</a></li>
<li><a href="#project">2. 프로젝트 소개</a><ol>
<li><a href="#idea">조건 설계</a></li><li><a href="#pipeline">시스템 구조</a></li><li><a href="#forms">슬라이드 형태</a></li><li><a href="#choices">설계 근거</a></li><li><a href="#prior">기존 도구와 차이</a></li></ol></li>
<li><a href="#method">3. 실험 공통 원칙</a><ol><li><a href="#metrics">지표</a></li><li><a href="#glossary">용어 풀이</a></li></ol></li>
<li><a href="#overview">4. 실험 한눈에</a></li>
<li><a href="#details">5. 실험별 상세</a><ol>
<li><a href="#detect">감지 정확도</a></li><li><a href="#api">실제 API 점검</a></li><li><a href="#speed">속도 기준선</a></li><li><a href="#x1">X1 샘플러·스텝</a></li><li><a href="#x2">X2 CFG</a></li><li><a href="#x3">X3 증류 모델</a></li><li><a href="#x5">X5 가짜 글자</a></li><li><a href="#x4">X4 강의 맥락</a></li><li><a href="#glyph">글자 규칙</a></li><li><a href="#tok77">77토큰 버그</a></li><li><a href="#e2e">실제 서버 E2E</a></li><li><a href="#preview">디노이징 미리보기</a></li></ol></li>
<li><a href="#deck">6. 발표 PPT 해설</a><ol><li><a href="#deck-flow">흐름과 평가 기준</a></li><li><a href="#deck-slides">슬라이드별 설명</a></li><li><a href="#deck-demo">시연 계획</a></li><li><a href="#deck-qa">예상 질문</a></li></ol></li>
<li><a href="#limits">7. 한계와 남은 일</a></li>
<li><a href="#repro">8. 재현 방법</a></li>
<li><a href="#files">9. 파일 지도</a></li>
</ol></details>"""

    page = f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>NextSlide 해설서</title>
<meta name="description" content="NextSlide 프로젝트, 확산 모델 실험(X1~X5), 발표 PPT 구성을 정리한 해설서">
<style>{CSS}</style>
</head>
<body>
<div class="toolbar"><button id="expand" type="button">모두 펼치기</button><button id="theme" type="button">어두운 화면</button></div>
<div class="wrap">
<nav aria-label="목차">{toc}</nav>
<main>
{body}
<p class="meta" style="margin-top:48px">이 문서는 <code>docs/presentation/build_guide.py</code>가 저장소의 기록을 모아 만들었습니다. 그림은 파일 안에 들어 있어 이 HTML 하나만 있으면 오프라인에서도 열립니다.</p>
</main>
</div>
<div id="lb" role="dialog" aria-label="그림 크게 보기"><img alt=""></div>
<script>{JS}</script>
</body>
</html>"""
    OUT.write_text(page)
    print("wrote", OUT, f"{OUT.stat().st_size/1e6:.2f} MB")
    # GitHub serves raw .html as text/plain (the browser shows source instead of
    # saving it), so also ship a zip, which browsers always download.
    import zipfile
    zpath = OUT.with_suffix(".zip")
    info = zipfile.ZipInfo(OUT.name, date_time=(2026, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    with zipfile.ZipFile(zpath, "w") as z:
        z.writestr(info, OUT.read_bytes())
    print("wrote", zpath, f"{zpath.stat().st_size/1e6:.2f} MB")


if __name__ == "__main__":
    build()
