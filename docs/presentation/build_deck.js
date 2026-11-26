// NextSlide 기말 발표 PPT 생성 스크립트 (pptxgenjs).
// 실행: NODE_PATH=<pptxgenjs·react-icons·sharp 가 설치된 node_modules> node docs/presentation/build_deck.js
// 결과: docs/presentation/NextSlide_final.pptx, docs/presentation/script.md (한·영 대본)
// 대본은 아래 SCRIPT 한 곳에서 관리하고, 슬라이드 노트와 script.md 를 함께 만든다.

const path = require("path");
const fs = require("fs");
const pptxgen = require("pptxgenjs");
const React = require("react");
const ReactDOMServer = require("react-dom/server");
const sharp = require("sharp");
const fa = require("react-icons/fa6");

const HERE = __dirname;
const A = (f) => path.join(HERE, "assets", f);
const OUT = path.join(HERE, "NextSlide_final.pptx");
const APPLY_THEME = process.env.APPLY_THEME_JS; // pptx 스킬의 scripts/apply_theme.js 경로 (선택)

// 디자인: frontend-slides 스타일 탐색에서 고른 "실시간 자막" 시안(어두운 바탕, 세리프 제목, 호박색 포인트).
// 글꼴(OFL): Instrument Serif(제목), Instrument Sans(본문), IBM Plex Mono(라벨). docs/presentation/fonts/ 에 있음.
// 어두운 덱이라 dk1 을 밝은 글자색, lt1 을 바탕색으로 둔다(기본 clrMap: tx1=dk1, bg1=lt1).
const THEME = {
  name: "NextSlide Live Caption",
  headFontFace: "Instrument Serif",
  bodyFontFace: "Instrument Sans",
  colors: {
    dk1: "F1EDE4", // 글자(따뜻한 흰색)
    lt1: "0E1013", // 바탕
    dk2: "8E8A80", // 보조 글자
    lt2: "17191D", // 카드 면
    accent1: "FFB547", // 호박색 신호
    accent2: "8FA6C1", // 두 번째 데이터 계열(차가운 회청색)
    accent3: "2C2F34", // 가는 선
    accent4: "5E5B55", // 흐린 요소
    accent5: "1E2126", // 한 단계 밝은 면
    accent6: "C9C3B6",
    hlink: "FFB547", folHlink: "8FA6C1",
  },
};
const H = THEME.colors; // hex-only 옵션(차트 격자선, 그림자)용
const MONO = "IBM Plex Mono";
const SERIF = "+mj-lt"; // 테마 제목 글꼴
const KO = "Apple SD Gothic Neo"; // 한국어 라벨(Instrument 글꼴에는 한글이 없음)

// ───────────────────────── 대본 (영어 / 한국어) ─────────────────────────
const SCRIPT = [
  {
    t: "0:30", title: "Title",
    en: "Hi, I'm [name]. My project is NextSlide. The idea is simple: while I'm lecturing, I say what the next slide should show, and the system builds it while I keep talking. Today I'll explain how it works, run a short live demo, and then show experiments on the image stage using the diffusion concepts from this course.",
    ko: "안녕하세요, [이름]입니다. 제 프로젝트는 NextSlide입니다. 아이디어는 간단합니다. 강의하면서 다음 장에 무엇을 보여 줄지 말하면, 제가 계속 말하는 동안 시스템이 그 장을 만듭니다. 오늘은 동작 방식을 설명하고, 짧게 시연한 뒤, 이 수업에서 배운 확산 모델 개념으로 이미지 단계를 실험한 결과를 보여 드리겠습니다.",
  },
  {
    t: "0:45", title: "The problem",
    en: "Real lectures are not fixed. A good lecturer invents an analogy on the spot, like: overfitting is a student who memorized the exam answers. Students ask questions the deck never planned for. But slides are prepared in advance. If I want a new slide in the middle of a lecture, I have to stop, open an editor, and lose the flow. So my goal is: the lecturer keeps talking, and the next slide gets ready.",
    ko: "실제 강의는 정해진 대로 흘러가지 않습니다. 좋은 강사는 '과적합은 시험 답을 외운 학생과 같다'처럼 즉석에서 비유를 만들고, 학생들은 슬라이드에 없던 질문을 합니다. 하지만 슬라이드는 미리 만들어 둔 것입니다. 강의 도중 새 장이 필요하면 멈추고 편집기를 열어야 해서 흐름이 끊깁니다. 그래서 목표는 '강사는 계속 말하고, 다음 장은 알아서 준비된다'입니다.",
  },
  {
    t: "0:50", title: "What's new",
    en: "The key idea is what we condition on. In most tools, the user writes a prompt. In NextSlide, the condition is built automatically from the lecture: the request detected from speech, the last ninety seconds of what I said, and the current slide. That's why a vague request like 'draw that hiker analogy' still works. Compared with live-staging tools such as ZeroPrep, there are three differences. Only explicit requests trigger a slide. The new slide goes to the presenter first, so I can check it before the audience sees it. And the system picks the right form, such as an equation, a table, or a chart, instead of always making a picture.",
    ko: "핵심은 '무엇을 조건으로 주느냐'입니다. 대부분의 도구에서는 사용자가 프롬프트를 씁니다. NextSlide에서는 강의에서 조건을 자동으로 만듭니다. 음성에서 감지한 요청, 직전 90초 동안 한 말, 그리고 현재 장입니다. 그래서 '그 등산객 비유 그려 줘'처럼 모호한 요청도 처리됩니다. ZeroPrep 같은 실시간 발표 도구와 비교하면 차이는 세 가지입니다. 명시적인 요청에만 새 장을 만듭니다. 새 장은 발표자에게 먼저 보이므로, 청중이 보기 전에 확인할 수 있습니다. 그리고 항상 그림을 만들지 않고 수식·표·그래프처럼 맞는 형태를 고릅니다.",
  },
  {
    t: "0:50", title: "Pipeline",
    en: "Here is one request end to end. The browser streams microphone audio, and Gemini transcribes it live. A rule-based detector looks for phrases like 'in the next slide' and ignores negations and quotes. On my 60-example test set it got 56 right. When a request is confirmed, the context is frozen, so later speech doesn't leak in. The planner LLM returns a strict JSON slide spec and chooses the form. The title and bullets appear first in the presenter preview, and the image follows. With the local SD-Turbo model, one request took about six seconds from request to finished slide.",
    ko: "요청 한 건의 흐름입니다. 브라우저가 마이크 음성을 보내고, Gemini가 실시간으로 받아 적습니다. 규칙 기반 감지기가 '다음 슬라이드에서는' 같은 표현을 찾고, 부정이나 인용은 무시합니다. 직접 만든 60개 평가 세트에서 56개를 맞혔습니다. 요청이 확정되면 맥락을 고정해서 이후 발화가 섞이지 않게 합니다. 기획 LLM은 엄격한 JSON 형식으로 슬라이드 내용을 돌려주고 형태를 고릅니다. 제목과 본문이 먼저 발표자 미리보기에 뜨고, 그림이 뒤따라옵니다. 로컬 SD-Turbo로는 요청부터 완성까지 약 6초가 걸렸습니다(1회 측정).",
  },
  {
    t: "0:40", title: "Right form for each content",
    en: "One design choice comes straight from Lecture 17: image models make plausible pictures, but they still get text, counts, and relations wrong. So the image model only draws text-free illustrations. Equations are rendered with KaTeX, comparisons and tables use fixed layouts, and chart values are computed by the server, not invented by the LLM. These three slides were generated by the system with real APIs.",
    ko: "설계 선택 하나는 17강에서 바로 나왔습니다. 이미지 모델은 그럴듯한 그림을 그리지만 글자, 개수, 관계는 자주 틀립니다. 그래서 이미지 모델에는 글자 없는 설명 그림만 맡깁니다. 수식은 KaTeX로, 비교와 표는 고정 레이아웃으로 그리고, 그래프 값은 LLM이 지어내지 않고 서버가 계산합니다. 이 세 장은 모두 실제 API로 시스템이 만든 결과입니다.",
  },
  {
    t: "2:00", title: "Live demo",
    en: "Let me show it live. NextSlide is built for Korean lectures, so I will speak the lecture lines to it in Korean and translate as I go. Please watch four things: normal speech creates nothing, a request shows text first, the image appears through the denoising steps, and a negation is ignored. (Run the demo. See the demo script below.)",
    ko: "직접 보여 드리겠습니다. NextSlide는 한국어 강의용이라 강의 문장은 한국어로 말하고, 바로 영어로 옮겨 드리겠습니다. 네 가지를 봐 주세요. 일반 설명에는 아무것도 생기지 않고, 요청하면 글이 먼저 뜨고, 그림은 디노이징 단계를 거쳐 나타나며, 부정 지시는 무시됩니다. (시연 진행. 아래 시연 대본 참고)",
  },
  {
    t: "0:45", title: "Diffusion inside the loop",
    en: "Now the course part. I replaced the image API with open diffusion models running locally on my laptop: Stable Diffusion 1.5 with DDIM and classifier-free guidance, and SD-Turbo, which is distilled to run in one to four steps. While the model denoises, I take the predicted clean latent, x-hat-zero, from each scheduler step, map its four channels to RGB with a linear approximation, and stream it to the slide. So the audience literally sees the reverse diffusion process, and it costs almost nothing, because there is no VAE decoding per step.",
    ko: "이제 수업 내용과 연결되는 부분입니다. 이미지 API 대신 제 노트북에서 돌아가는 공개 확산 모델을 붙였습니다. DDIM과 classifier-free guidance를 쓰는 Stable Diffusion 1.5, 그리고 1~4스텝으로 돌도록 증류된 SD-Turbo입니다. 모델이 잡음을 제거하는 동안 매 스텝 스케줄러가 계산한 '예측된 깨끗한 잠재' x̂₀를 가져와, 4채널을 선형 근사로 RGB로 바꿔 슬라이드에 보냅니다. 그래서 청중은 역확산 과정을 그대로 보게 되고, 스텝마다 VAE 디코딩을 하지 않으므로 비용은 거의 없습니다.",
  },
  {
    t: "0:50", title: "X2 · Guidance scale",
    en: "In every experiment I changed one setting at a time: 12 lecture scenes, two fixed seeds, and CLIP similarity measured with a different CLIP model from the generators. Raising the guidance scale increases alignment from 21.5 to about 25.7, and then it plateaus around 5. Diversity between seeds keeps falling. This is exactly the trade-off from the lecture. One warning: when I compared samplers, DDPM at 10 steps visibly broke the shapes while DDIM kept them, but the CLIP scores did not change. CLIP measures prompt match, not image quality.",
    ko: "모든 실험에서 한 번에 설정 하나만 바꿨습니다. 강의 장면 12개, 고정 시드 2개를 쓰고, 생성 모델과 다른 CLIP 모델로 유사도를 쟀습니다. 가이던스 스케일을 올리면 장면 일치도가 21.5에서 25.7 정도까지 오르다가 5 근처에서 멈춥니다. 반면 시드 간 다양성은 계속 떨어집니다. 강의에서 배운 트레이드오프 그대로입니다. 주의할 점이 하나 있습니다. 샘플러를 비교했을 때 DDPM 10스텝은 눈에 띄게 형체가 깨졌고 DDIM은 유지됐는데, CLIP 점수는 차이가 없었습니다. CLIP은 프롬프트 일치를 볼 뿐 그림 품질은 보지 못합니다.",
  },
  {
    t: "0:40", title: "X3 · Distilled model",
    en: "For a live lecture, speed matters most. SD-Turbo with two steps takes 0.68 seconds. SD 1.5 with 25 steps and guidance takes 11 seconds, about sixteen times slower. SD-Turbo also scored higher on CLIP, 28.2 versus 25.0. One caveat: SD-Turbo is based on SD 2.1 with a larger text encoder, so this is not the effect of distillation alone. The system default is SD-Turbo with two steps.",
    ko: "실시간 강의에서는 속도가 가장 중요합니다. SD-Turbo 2스텝은 0.68초, 가이던스를 쓰는 SD 1.5 25스텝은 11초로 약 16배 느립니다. CLIP 점수도 SD-Turbo가 28.2 대 25.0으로 높았습니다. 단, SD-Turbo는 SD 2.1 기반이고 텍스트 인코더도 더 커서 증류만의 효과라고 볼 수는 없습니다. 시스템 기본값은 SD-Turbo 2스텝입니다.",
  },
  {
    t: "1:00", title: "X4 · Lecture context",
    en: "This is the main experiment: does the lecture context actually help? I built 42 scenarios, 12 general ones and 30 based on this course's lectures. Condition A gets only the request. Condition B also gets the recent speech and the current slide. Everything else is fixed. Before generating anything, I wrote down the intended scene for each scenario and committed it to git. With context, the images were closer to the intended scene by 2.1 CLIP points. The 95 percent interval is 0.65 to 3.6, and the permutation test gives p equals 0.010. Without context, the planner had to ask for clarification 7 times out of 42. With context, zero times. Look at S09: without context we get a modern classroom; with context, a Joseon-era exam hall, which is what the lecturer meant. Also notice that the gain is 6.4 in the prompt text but only 2.1 in the image. The image model is the bottleneck.",
    ko: "핵심 실험입니다. 강의 맥락이 정말 도움이 될까요? 시나리오 42개를 만들었습니다. 일반 시나리오 12개와 이 수업 강의자료를 바탕으로 한 30개입니다. A 조건은 요청만, B 조건은 최근 발화와 현재 장까지 받습니다. 나머지는 모두 같습니다. 생성하기 전에 시나리오마다 의도한 장면을 적어 git에 커밋해 고정했습니다. 맥락이 있으면 그림이 의도한 장면에 CLIP 점수로 2.1점 더 가까웠습니다. 95% 구간은 0.65~3.6, 순열 검정 p값은 0.010입니다. 맥락이 없으면 42개 중 7개에서 보완 질문을 해야 했고, 맥락이 있으면 0개였습니다. S09를 보면 맥락 없이는 현대식 교실이, 맥락이 있으면 강사가 말한 조선 시대 과거 시험장이 나옵니다. 그리고 프롬프트 글에서 6.4점이던 차이가 그림에서는 2.1점으로 줄어듭니다. 이미지 모델이 병목입니다.",
  },
  {
    t: "0:45", title: "What didn't work",
    en: "Some things did not work, and I want to be clear about them. First, SD-Turbo draws fake text on paper and signs. Weak guidance with a negative prompt didn't fix it, and neither did telling the planner to describe blank surfaces: about 9 of 34 images had fake text, before and after. Second, I tried CLIP as an automatic text detector. When I checked its top six images, only one really had text, so I dropped it. Third, the experiment found a real bug: planner prompts were longer than CLIP's 77-token limit, so the style words were cut off. I fixed it with token-aware trimming. Finally, the evaluation uses CLIP only, and the scenarios and intended scenes were written by the same side, with help from an AI assistant. A blind human evaluation is the next step.",
    ko: "잘 안 된 것도 분명히 말씀드리겠습니다. 첫째, SD-Turbo는 종이나 간판에 가짜 글자를 그립니다. 약한 가이던스와 negative prompt로도, 기획 LLM에 '빈 면으로 묘사하라'고 지시해도 고쳐지지 않았습니다. 전후 모두 34장 중 약 9장에 가짜 글자가 있었습니다. 둘째, CLIP으로 글자를 자동 판정하려 했지만, 상위 6장 중 실제 글자는 1장뿐이라 버렸습니다. 셋째, 실험 중에 실제 버그를 찾았습니다. 기획 LLM의 그림 묘사가 CLIP의 77토큰 한도를 넘어 화풍 문구가 잘리고 있었습니다. 토큰 수를 세서 줄이는 방식으로 고쳤습니다. 마지막으로, 평가 지표는 CLIP 하나뿐이고, 시나리오와 의도 장면은 같은 쪽에서 AI 보조 도구의 도움을 받아 썼습니다. 다음 단계는 블라인드 사람 평가입니다.",
  },
  {
    t: "0:30", title: "Takeaways",
    en: "To sum up. Conditioning on the lecture itself makes the images match what the lecturer meant, with no extra questions. Distilled diffusion makes the image stage fast enough for a live lecture. And the remaining bottleneck is the image model, not the language model. Thank you. I'm happy to take questions.",
    ko: "정리하겠습니다. 강의 자체를 조건으로 쓰면 추가 질문 없이도 그림이 강사가 의도한 장면에 가까워집니다. 증류된 확산 모델 덕분에 이미지 단계가 실시간 강의에 쓸 만큼 빨라졌습니다. 그리고 남은 병목은 언어 모델이 아니라 이미지 모델입니다. 감사합니다. 질문 받겠습니다.",
  },
];

const DEMO = [
  {
    step: "1. Normal speech → nothing happens", time: "0:20",
    speak: "과적합은 모델이 학습 데이터에 지나치게 맞춰져서 새로운 데이터에는 잘 대응하지 못하는 현상입니다.",
    meaning: "Overfitting is when a model fits the training data too closely and fails on new data.",
    point_en: "Point at the live caption. \"I just explained overfitting in Korean. It's an explanation, not a request, so nothing is generated.\"",
    point_ko: "자막을 가리키며: \"방금 한국어로 과적합을 설명했습니다. 요청이 아니라 설명이라서 아무것도 생성되지 않습니다.\"",
  },
  {
    step: "2. Request → text first", time: "0:40",
    speak: "다음 슬라이드에서는 과적합을 시험 문제를 외운 학생에 비유해서 설명하겠습니다.",
    meaning: "In the next slide, I'll explain overfitting with a student who memorized the exam answers.",
    point_en: "\"I said: in the next slide, I'll explain overfitting with a student who memorized the exam answers. The detector confirmed the request. The title and bullets appear first in my preview. The audience screen hasn't changed yet.\"",
    point_ko: "\"방금 '다음 슬라이드에서는 과적합을 시험 문제를 외운 학생에 비유해서 설명하겠습니다'라고 했습니다. 감지기가 요청을 확정했고, 제목과 본문이 먼저 제 미리보기에 뜹니다. 청중 화면은 아직 그대로입니다.\"",
  },
  {
    step: "3. Denoising preview → advance", time: "0:30",
    speak: "(없음. 그림이 만들어지는 동안 영어로 계속 설명합니다.)",
    meaning: "",
    point_en: "\"This blurry picture is the model's current guess of the clean image, x-hat-zero, at each step. ... Now it's ready, so I advance, and the audience sees it.\" Press →.",
    point_ko: "\"이 흐린 그림이 매 스텝 모델이 예측한 깨끗한 그림 x̂₀입니다. … 준비됐으니 넘기면 청중 화면에도 나타납니다.\" → 키.",
  },
  {
    step: "4. Negation → ignored", time: "0:20",
    speak: "다음 슬라이드는 만들지 마세요.",
    meaning: "Don't make a next slide.",
    point_en: "\"I said: don't make a next slide. It is detected as a negation, so nothing is generated.\"",
    point_ko: "\"'다음 슬라이드는 만들지 마세요'라고 했습니다. 부정 지시로 판단해 생성하지 않습니다.\"",
  },
];

const QA = [
  {
    q_en: "Isn't this just chaining APIs?", q_ko: "API를 이어 붙인 것 아닌가요?",
    a_en: "Two parts are my own work. First, the condition design: the condition is built automatically from the lecture, and I measured its effect (X4, p = 0.010). Second, the image stage now runs on local diffusion models that I benchmarked one setting at a time (X1 to X3), plus the x-hat-zero denoising preview.",
    a_ko: "제 작업은 두 가지입니다. 첫째, 강의에서 조건을 자동으로 만드는 조건 설계이고, 그 효과를 측정했습니다(X4, p=0.010). 둘째, 이미지 단계를 로컬 확산 모델로 바꾸고 설정을 하나씩 바꿔 비교했으며(X1~X3), x̂₀ 디노이징 미리보기를 구현했습니다.",
  },
  {
    q_en: "Why rules instead of an LLM for detecting requests?", q_ko: "요청 감지를 왜 LLM이 아니라 규칙으로 하나요?",
    a_en: "Cost, latency, and false triggers. An LLM call for every utterance is slow and expensive, and a false trigger interrupts the lecture. The rules got 56 of 60 right on my test set, with no missed requests and one false generation. The set was written by me, so it is optimistic.",
    a_ko: "비용, 지연, 오작동 때문입니다. 발화마다 LLM을 부르면 느리고 비싸며, 잘못 생성되면 강의가 끊깁니다. 규칙은 평가 세트 60개 중 56개를 맞혔고, 놓친 요청 0건, 잘못 생성 1건이었습니다. 제가 쓴 평가 세트라 결과가 낙관적일 수 있습니다.",
  },
  {
    q_en: "What if the generated content is wrong?", q_ko: "생성된 내용이 틀리면 어떻게 하나요?",
    a_en: "The audience never sees a slide until I advance to it. In the presenter preview I can edit the title and bullets, retry the image, or cancel the job.",
    a_ko: "제가 넘기기 전에는 청중이 새 장을 보지 못합니다. 발표자 미리보기에서 제목·본문을 고치거나, 그림을 다시 만들거나, 작업을 취소할 수 있습니다.",
  },
  {
    q_en: "How fast and how expensive is it?", q_ko: "속도와 비용은 어느 정도인가요?",
    a_en: "With local SD-Turbo: about 6 seconds from request to finished slide, and the image itself took 1.2 seconds (single measurement). The planner LLM costs about 0.02 to 0.04 cents per slide, and local images are free. With the gpt-image-2 API it was about 20 seconds and about 0.45 cents per image.",
    a_ko: "로컬 SD-Turbo 기준으로 요청부터 완성까지 약 6초, 그림만 1.2초였습니다(1회 측정). 기획 LLM 비용은 장당 약 $0.0002~0.0004이고 로컬 그림은 무료입니다. gpt-image-2 API로는 약 20초, 그림당 약 $0.0045였습니다.",
  },
  {
    q_en: "How does the denoising preview work?", q_ko: "디노이징 미리보기는 어떻게 동작하나요?",
    a_en: "At each step the scheduler already computes the predicted clean sample, x-hat-zero equals x_t minus the square root of one minus alpha-bar times the predicted noise, divided by the square root of alpha-bar. I capture it, project the 4 latent channels to RGB with a fixed linear matrix, and send a small JPEG over WebSocket. No VAE decoding is needed.",
    a_ko: "스케줄러가 매 스텝 이미 계산하는 x̂₀ = (x_t − √(1−ᾱ_t)·ε̂) / √ᾱ_t 를 가로챕니다. 잠재 4채널을 고정 선형 행렬로 RGB에 투영하고, 작은 JPEG로 WebSocket을 통해 보냅니다. VAE 디코딩이 필요 없습니다.",
  },
  {
    q_en: "Can you trust the CLIP score?", q_ko: "CLIP 점수를 믿을 수 있나요?",
    a_en: "Not on its own. X1 showed that CLIP misses broken images, and my CLIP-based text detector failed validation. I used a different CLIP model from the generators to reduce bias, and a blind human evaluation is the next step.",
    a_ko: "단독으로는 아닙니다. X1에서 CLIP이 깨진 그림을 잡지 못했고, CLIP으로 글자를 판정하는 방법도 검증에서 실패했습니다. 편향을 줄이려고 생성 모델과 다른 CLIP을 썼고, 다음 단계는 블라인드 사람 평가입니다.",
  },
  {
    q_en: "Why SD-Turbo instead of gpt-image-2?", q_ko: "왜 gpt-image-2 대신 SD-Turbo인가요?",
    a_en: "It is about sixteen to twenty times faster, it runs locally for free, and I can open up the sampling process. The trade-off is fake text in some images. Switching back is a single environment variable.",
    a_ko: "약 16~20배 빠르고, 로컬에서 무료로 돌며, 샘플링 과정을 직접 다룰 수 있습니다. 대신 일부 그림에 가짜 글자가 생깁니다. 환경변수 하나로 다시 바꿀 수 있습니다.",
  },
  {
    q_en: "Does it work for English lectures?", q_ko: "영어 강의에서도 되나요?",
    a_en: "Not yet. Speech recognition is set to Korean and the detector rules are Korean phrases. The planner LLM itself can write English slides, so adding English trigger phrases and switching the STT language is the main work.",
    a_ko: "아직은 아닙니다. 음성 인식 언어가 한국어이고 감지 규칙도 한국어 표현입니다. 기획 LLM은 영어 슬라이드도 쓸 수 있으므로, 영어 요청 표현을 추가하고 STT 언어를 바꾸는 것이 주된 작업입니다.",
  },
];

// ───────────────────────── 아이콘·배경·파형 그림 ─────────────────────────
async function icon(name, color, size = 256) {
  const Comp = fa[name];
  if (!Comp) throw new Error(`unknown icon ${name}`);
  const svg = ReactDOMServer.renderToStaticMarkup(React.createElement(Comp, { color: "#" + color, size: String(size) }));
  const buf = await sharp(Buffer.from(svg)).resize(size, size).png().toBuffer();
  return "image/png;base64," + buf.toString("base64");
}

// 어두운 바탕 + 은은한 빛 번짐 + 고운 입자. 결정적 난수라 다시 만들어도 같은 그림이 나온다.
async function makeBackground(file, glows) {
  if (fs.existsSync(file)) return;
  const w = 1920, h = 1080, buf = Buffer.alloc(w * h * 3);
  let seed = 20261126;
  const rnd = () => ((seed = (seed * 1664525 + 1013904223) >>> 0) / 4294967296);
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      let c = [14, 16, 19];
      for (const g of glows) {
        const dx = (x - g.x * w) / (g.rx * w), dy = (y - g.y * h) / (g.ry * h);
        let t = Math.max(0, 1 - Math.sqrt(dx * dx + dy * dy));
        t = t * t * g.a;
        c = c.map((v, k) => v + (g.col[k] - v) * t);
      }
      const n = (rnd() - 0.5) * 6;
      const i = (y * w + x) * 3;
      for (let k = 0; k < 3; k++) buf[i + k] = Math.max(0, Math.min(255, Math.round(c[k] + n)));
    }
  }
  await sharp(buf, { raw: { width: w, height: h, channels: 3 } }).jpeg({ quality: 88 }).toFile(file);
}

// 음성 파형(장식). 막대 18개짜리 그림 한 장.
const WAVE_H = [0.3, 0.62, 0.44, 0.95, 0.5, 0.8, 0.24, 0.9, 0.4, 0.74, 0.32, 0.56, 0.92, 0.26, 0.78, 0.46, 0.68, 0.34];
async function waveform(color) {
  const bw = 10, gap = 10, H0 = 100, W0 = WAVE_H.length * (bw + gap) - gap;
  const bars = WAVE_H.map((v, i) => {
    const bh = Math.round(v * H0);
    return `<rect x="${i * (bw + gap)}" y="${(H0 - bh) / 2}" width="${bw}" height="${bh}" rx="${bw / 2}" fill="#${color}" fill-opacity="0.8"/>`;
  }).join("");
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${W0}" height="${H0}" viewBox="0 0 ${W0} ${H0}">${bars}</svg>`;
  const buf = await sharp(Buffer.from(svg), { density: 288 }).png().toBuffer();
  return { data: "image/png;base64," + buf.toString("base64"), ratio: W0 / H0 };
}

function notesFor(i) {
  const s = SCRIPT[i];
  let n = `[${s.t}] ${s.en}\n\n[KO] ${s.ko}`;
  if (s.title === "Live demo") {
    n += "\n\n" + DEMO.map((d) => `${d.step} (${d.time})\nSPEAK (KO): ${d.speak}${d.meaning ? `\n(= ${d.meaning})` : ""}\nEN: ${d.point_en}\n[KO] ${d.point_ko}`).join("\n\n");
  }
  return n;
}

// ───────────────────────── 덱 ─────────────────────────
async function build() {
  const BG_CONTENT = A("bg_content.jpg"), BG_TITLE = A("bg_title.jpg");
  await makeBackground(BG_CONTENT, [
    { x: 0.86, y: 0.02, rx: 0.55, ry: 0.75, a: 0.10, col: [255, 181, 71] },
    { x: 0.04, y: 1.0, rx: 0.5, ry: 0.6, a: 0.10, col: [120, 140, 170] },
  ]);
  await makeBackground(BG_TITLE, [
    { x: 0.76, y: 0.28, rx: 0.62, ry: 0.85, a: 0.15, col: [255, 181, 71] },
    { x: 0.06, y: 1.0, rx: 0.55, ry: 0.65, a: 0.13, col: [120, 140, 170] },
  ]);
  const WAVE = await waveform(H.dk1);

  const pres = new pptxgen();
  pres.layout = "LAYOUT_WIDE"; // 13.333 x 7.5
  pres.title = "NextSlide: Speak the Next Slide";
  pres.subject = "Generative AI final project";
  pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
  const C = pres.SchemeColor;
  const W = 13.333, M = 0.75, CW = W - 2 * M;

  // 레이아웃: 표지 / 본문 / 구간(시연·정리)
  const slideNum = () => ({ x: W - M - 1.0, y: 6.84, w: 1.0, h: 0.3, fontFace: MONO, fontSize: 10, color: C.text2, align: "right" });
  pres.defineSlideMaster({
    title: "TITLE",
    background: { path: BG_TITLE },
    objects: [
      { placeholder: { options: { name: "title", type: "title", x: M, y: 1.15, w: 6.6, h: 1.95, fontSize: 112, color: C.text1, valign: "bottom", align: "left", margin: 0 }, text: "" } },
      { placeholder: { options: { name: "body", type: "body", x: M, y: 3.4, w: 5.9, h: 1.5, fontSize: 30, color: C.text1, valign: "top", margin: 0 }, text: "" } },
    ],
  });
  pres.defineSlideMaster({
    title: "CONTENT",
    background: { path: BG_CONTENT },
    margin: [0.5, M, 0.6, M],
    objects: [
      { placeholder: { options: { name: "title", type: "title", x: M, y: 0.78, w: CW, h: 0.95, fontSize: 40, color: C.text1, valign: "middle", align: "left", margin: 0 }, text: "" } },
    ],
    slideNumber: slideNum(),
  });
  pres.defineSlideMaster({
    title: "SECTION",
    background: { path: BG_TITLE },
    objects: [
      { placeholder: { options: { name: "title", type: "title", x: M, y: 0.8, w: CW, h: 1.2, fontSize: 64, color: C.text1, valign: "middle", align: "left", margin: 0 }, text: "" } },
    ],
    slideNumber: slideNum(),
  });

  // 공통 요소
  const T = (s, t, o) => s.addText(t, { isTextBox: true, margin: 0, fontSize: 15, color: C.text1, valign: "top", ...o });
  const mono = (s, t, o) => T(s, t, { fontFace: MONO, fontSize: 10.5, charSpacing: 2, color: C.accent1, ...o });
  const kicker = (s, t) => mono(s, t.toUpperCase(), { x: M, y: 0.46, w: 9, h: 0.3, objectName: "Section label" });
  const dot = (s, x, y, d = 0.1) =>
    s.addShape(pres.shapes.OVAL, { x, y, w: d, h: d, fill: { color: C.accent1 }, line: { type: "none" }, objectName: "Live dot" });
  const box = (s, x, y, w, h, name, fill = C.background2) =>
    s.addShape(pres.shapes.RECTANGLE, { x, y, w, h, fill: { color: fill }, line: { type: "none" }, objectName: name });
  const frame = (s, x, y, w, h, name) =>
    s.addShape(pres.shapes.RECTANGLE, { x, y, w, h, fill: { type: "none" }, line: { color: C.accent3, width: 0.75 }, objectName: name });
  const img = (s, file, x, y, w, h, alt, name) => {
    s.addImage({ path: A(file), x, y, w, h, altText: alt, objectName: name });
    frame(s, x, y, w, h, name + " frame");
  };
  const wave = (s, x, cy, h) => s.addImage({ data: WAVE.data, x, y: cy - h / 2, w: h * WAVE.ratio, h, altText: "Decorative speech waveform", objectName: "Waveform" });
  // 하단 자막 줄: 측정 방법·출처·주의를 실시간 자막처럼 한 줄로 둔다.
  const capline = (s, label, text, fs = 12) => {
    dot(s, M, 6.95);
    mono(s, label.toUpperCase(), { x: M + 0.24, y: 6.86, w: 1.0, h: 0.28, fontSize: 9.5, valign: "middle", objectName: "Caption label" });
    T(s, text, { x: M + 1.3, y: 6.68, w: CW - 1.3 - 1.1, h: 0.64, fontSize: fs, color: C.text2, valign: "middle", objectName: "Caption line" });
  };
  const chartBase = () => ({
    showTitle: true, titleFontSize: 14, titleColor: H.dk1, titleFontFace: "+mn-lt",
    catAxisLabelColor: H.dk2, valAxisLabelColor: H.dk2, catAxisLabelFontSize: 12, valAxisLabelFontSize: 11,
    catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt",
    valGridLine: { color: H.accent3, size: 0.75 }, catGridLine: { style: "none" },
    showLegend: false, showValue: true, dataLabelColor: H.dk1, dataLabelFontSize: 11, dataLabelFontFace: "+mn-lt",
    catAxisLineShow: true, catAxisLineColor: H.accent4, valAxisLineShow: false,
    plotArea: { fill: { color: H.lt1, transparency: 100 } },
    chartArea: { fill: { color: H.lt1, transparency: 100 } },
  });

  let n = 0;
  const S = (layout, section) => {
    const s = pres.addSlide({ masterName: layout, sectionTitle: section });
    s.addNotes(notesFor(n));
    n += 1;
    return s;
  };
  const title = (s, parts) => s.addText(parts.map((p, i) => (i % 2 ? { text: p, options: { italic: true, color: C.accent1 } } : { text: p })).filter((r) => r.text), { placeholder: "title" });

  // 1. 표지
  pres.addSection({ title: "Opening" });
  {
    const s = S("TITLE", "Opening");
    mono(s, "GENERATIVE AI  ·  FINAL PROJECT  ·  FALL 2026", { x: M, y: 0.82, w: 6.5, h: 0.3 });
    title(s, ["Next", "Slide"]);
    s.addText([
      { text: "Speak the next slide.", options: { breakLine: true } },
      { text: "The lecture itself becomes the condition for generation.", options: { fontSize: 20, color: C.text2, paraSpaceBefore: 10 } },
    ], { placeholder: "body" });
    const ix = 7.25, iw = W - M - ix, ih = iw * 9 / 16;
    mono(s, "PRESENTER PREVIEW", { x: ix, y: 0.98, w: 3, h: 0.28, color: C.text2 });
    mono(s, "FINAL IMAGE", { x: ix + iw - 2.5, y: 0.98, w: 2.5, h: 0.28, align: "right" });
    img(s, "real_v2_illustration.jpg", ix, 1.32, iw, ih, "A slide generated by NextSlide: a hiker overshooting the valley as an analogy for a too-large learning rate", "Generated slide example");
    T(s, "Made by NextSlide with real APIs.", { x: ix, y: 1.32 + ih + 0.14, w: iw, h: 0.3, fontSize: 12, color: C.text2 });
    // 실시간 자막 줄
    dot(s, M, 5.96, 0.12);
    mono(s, "LIVE", { x: M + 0.24, y: 5.87, w: 0.7, h: 0.3, fontSize: 11 });
    wave(s, M + 1.0, 6.02, 0.36);
    T(s, "“Explain a too-large learning rate with a hiker coming down a mountain.”", { x: 3.2, y: 5.72, w: W - M - 3.2, h: 0.45, fontSize: 19 });
    mono(s, "REQUEST  ·  TRANSLATED FROM KOREAN", { x: 3.2, y: 6.22, w: 6, h: 0.28, fontSize: 9.5, color: C.text2 });
  }

  // 2. 문제
  pres.addSection({ title: "Idea" });
  {
    const s = S("CONTENT", "Idea");
    kicker(s, "The problem");
    title(s, ["Lectures improvise, ", "slides don't"]);
    dot(s, M, 2.06);
    mono(s, "LIVE  ·  MID-LECTURE", { x: M + 0.24, y: 1.97, w: 2.6, h: 0.28 });
    wave(s, M + 2.75, 2.11, 0.26);
    T(s, "“In the next slide, I'll explain overfitting with a student who memorized the exam answers.”",
      { x: M, y: 2.45, w: 5.7, h: 1.9, fontFace: SERIF, italic: true, fontSize: 32 });
    T(s, "An analogy invented mid-lecture: no slide exists for it.", { x: M, y: 4.4, w: 5.7, h: 0.35, fontSize: 15, color: C.text2 });
    const rows = [
      ["Analogies appear on the spot", "The best explanations are often improvised."],
      ["Students ask unplanned questions", "The deck was fixed before class."],
      ["Making a slide breaks the flow", "Stop, open an editor, lose the audience."],
    ];
    rows.forEach((r, i) => {
      const y = 2.0 + i * 1.05;
      mono(s, "0" + (i + 1), { x: 7.15, y: y + 0.05, w: 0.6, h: 0.3, fontSize: 12 });
      T(s, r[0], { x: 7.8, y, w: 4.8, h: 0.4, fontSize: 19, bold: true });
      T(s, r[1], { x: 7.8, y: y + 0.42, w: 4.8, h: 0.35, fontSize: 15, color: C.text2 });
    });
    mono(s, "GOAL", { x: M, y: 5.3, w: 2, h: 0.28 });
    T(s, [{ text: "The lecturer keeps talking. The next slide gets " }, { text: "ready.", options: { italic: true, color: C.accent1 } }],
      { x: M, y: 5.62, w: CW, h: 0.75, fontFace: SERIF, fontSize: 34 });
  }

  // 3. 새로운 점
  {
    const s = S("CONTENT", "Idea");
    kicker(s, "What's new");
    title(s, ["The condition is ", "the lecture itself"]);
    const chips = [
      ["Request", "detected from speech"],
      ["Recent speech", "last 90 s, frozen at request"],
      ["Current slide", "title + key points"],
    ];
    chips.forEach((c, i) => {
      const y = 2.0 + i * 1.0, first = i === 0;
      box(s, M, y, 3.35, 0.82, c[0] + " chip", first ? C.accent1 : C.background2);
      T(s, [{ text: c[0], options: { bold: true, breakLine: true } }, { text: c[1], options: { fontSize: 13, color: first ? C.background1 : C.text2 } }],
        { x: M + 0.22, y, w: 3.0, h: 0.82, fontSize: 17, valign: "middle", color: first ? C.background1 : C.text1 });
    });
    s.addShape(pres.shapes.RIGHT_ARROW, { x: 4.3, y: 3.21, w: 0.42, h: 0.4, fill: { color: C.accent4 }, line: { type: "none" }, objectName: "Arrow to planner" });
    s.addShape(pres.shapes.RECTANGLE, { x: 4.9, y: 2.66, w: 1.85, h: 1.5, fill: { color: C.accent5 }, line: { color: C.accent1, width: 1 }, objectName: "Planner box" });
    T(s, [{ text: "Slide plan", options: { bold: true, breakLine: true } }, { text: "form + text + image prompt", options: { fontSize: 13, color: C.text2 } }],
      { x: 5.0, y: 2.66, w: 1.65, h: 1.5, fontSize: 17, valign: "middle", align: "center" });
    T(s, "No one types a prompt. “Draw that hiker analogy” works because the condition carries the lecture.",
      { x: M, y: 5.2, w: 6.0, h: 0.8, fontSize: 16, italic: true, color: C.text2 });

    const hdr = (t, hi) => ({ text: t, options: { fontFace: MONO, fontSize: 10.5, charSpacing: 1, color: hi ? C.accent1 : C.text2, fill: { color: C.background2 } } });
    const hi = (t) => ({ text: t, options: { bold: true, color: C.accent1 } });
    const lab = (t) => ({ text: t, options: { bold: true } });
    s.addTable([
      [hdr(""), hdr("LIVE-STAGING TOOLS (ZEROPREP)"), hdr("NEXTSLIDE", true)],
      [lab("Trigger"), "A realtime model interprets every utterance", hi("Only explicit requests (rule detector)")],
      [lab("Who sees it first"), "The audience, immediately", hi("The presenter; I advance when ready")],
      [lab("Slide forms"), "Cards, metrics, diagrams", hi("Illustration, equation, comparison, table, chart")],
    ], {
      x: 6.95, y: 2.0, w: W - M - 6.95, colW: [1.25, 2.0, W - M - 6.95 - 3.25], fontSize: 14, color: C.text1,
      border: { type: "solid", pt: 0.75, color: H.accent3 }, valign: "middle", rowH: [0.55, 1.05, 1.05, 1.05], margin: 0.1,
      objectName: "Prior work comparison",
    });
    capline(s, "Source", "ZeroPrep: github.com/ramsrigouthamg/zeroprep (README and app code read 2026-11-05)");
  }

  // 4. 파이프라인
  pres.addSection({ title: "System" });
  {
    const s = S("CONTENT", "System");
    kicker(s, "System");
    title(s, ["One request, ", "end to end"]);
    const steps = [
      ["FaMicrophone", "Mic", "Browser streams 16 kHz audio"],
      ["FaWaveSquare", "Live STT", "Gemini live transcription"],
      ["FaFilter", "Detector", "Rules: request vs. negation, quote"],
      ["FaLock", "Freeze context", "Request + 90 s + current slide"],
      ["FaBrain", "Planner LLM", "Strict JSON, picks the form"],
      ["FaDisplay", "Text → image", "Presenter preview first, then audience"],
    ];
    const gap = 0.26, bw = (CW - 5 * gap) / 6, y = 1.98, bh = 2.55;
    for (let i = 0; i < steps.length; i++) {
      const x = M + i * (bw + gap), last = i === steps.length - 1;
      const ink = last ? C.background1 : C.text1, sub = last ? C.background1 : C.text2;
      box(s, x, y, bw, bh, steps[i][1] + " box", last ? C.accent1 : C.background2);
      mono(s, "0" + (i + 1), { x: x + 0.2, y: y + 0.2, w: 0.6, h: 0.28, color: last ? C.background1 : C.accent1 });
      s.addImage({ data: await icon(steps[i][0], last ? H.lt1 : H.accent1), x: x + 0.2, y: y + 0.62, w: 0.42, h: 0.42, altText: steps[i][1] + " icon", objectName: steps[i][1] + " icon" });
      T(s, steps[i][1], { x: x + 0.18, y: y + 1.1, w: bw - 0.28, h: 0.62, fontSize: 16, bold: true, color: ink, valign: "bottom" });
      T(s, steps[i][2], { x: x + 0.18, y: y + 1.8, w: bw - 0.28, h: 0.68, fontSize: 12.5, color: sub });
      if (!last)
        s.addShape(pres.shapes.LINE, { x: x + bw + 0.04, y: y + bh / 2, w: gap - 0.08, h: 0, line: { color: C.accent4, width: 1.25, endArrowType: "triangle" }, objectName: "Flow arrow " + (i + 1) });
    }
    const stats = [
      ["56 / 60", "utterances classified correctly", "test set written by the developer"],
      ["112", "automated backend tests", "mock providers, no API calls"],
      ["6.2 s", "request → finished slide", "local SD-Turbo, single run (n = 1)"],
    ];
    const sw = (CW - 2 * 0.4) / 3;
    stats.forEach((st, i) => {
      const x = M + i * (sw + 0.4);
      T(s, st[0], { x, y: 4.82, w: sw, h: 0.9, fontFace: SERIF, fontSize: 58, color: i === 2 ? C.accent1 : C.text1, valign: "bottom" });
      T(s, st[1], { x, y: 5.8, w: sw, h: 0.35, fontSize: 16, bold: true });
      T(s, st[2], { x, y: 6.17, w: sw, h: 0.3, fontSize: 12.5, color: C.text2 });
    });
  }

  // 5. 형태 고르기
  {
    const s = S("CONTENT", "System");
    kicker(s, "System  ·  output forms");
    title(s, ["Image models draw ", "pictures", ", not text"]);
    T(s, [
      { text: "Lecture 17: a plausible image can still miss the prompt (counts, relations, text). ", options: { color: C.text2 } },
      { text: "So the planner picks a form, and only illustrations go to the image model.", options: { bold: true } },
    ], { x: M, y: 1.85, w: CW, h: 0.65, fontSize: 16 });
    const shots = [
      ["real_v2_illustration.jpg", "Illustration", "image model, no text inside"],
      ["real_v2_equation_gd.jpg", "Equation", "rendered with KaTeX"],
      ["real_v4_comparison.jpg", "Comparison", "fixed two-column layout"],
    ];
    const g = 0.35, iw = (CW - 2 * g) / 3, ih = iw * 9 / 16;
    shots.forEach((sh, i) => {
      const x = M + i * (iw + g);
      mono(s, sh[1].toUpperCase(), { x, y: 2.75, w: iw, h: 0.28 });
      img(s, sh[0], x, 3.08, iw, ih, sh[1] + " slide generated by NextSlide", sh[1] + " screenshot");
      T(s, sh[2], { x, y: 3.08 + ih + 0.16, w: iw, h: 0.35, fontSize: 15, color: C.text2 });
    });
    capline(s, "Also", "Tables, and charts whose values the server computes (the LLM gives only the function and range). All three made with real APIs; slide text is Korean.");
  }

  // 6. 시연
  {
    const s = S("SECTION", "System");
    mono(s, "WATCH FOR FOUR THINGS", { x: M, y: 0.46, w: 6, h: 0.3 });
    title(s, ["Live ", "demo"]);
    const ko = (t) => ({ text: t, options: { fontFace: KO } });
    const rows = [
      [[{ text: "Normal speech" }], [{ text: "An explanation creates nothing" }]],
      [[ko("“다음 슬라이드…”")], [{ text: "A request (“In the next slide…”): title and bullets appear first" }]],
      [[{ text: "Denoising preview" }], [{ text: "x̂₀", options: { fontFace: MONO } }, { text: " at each step, then the image" }]],
      [[ko("“만들지 마세요”")], [{ text: "A negation (“Don't make it”) is ignored" }]],
    ];
    const y0 = 2.35, rh = 0.84;
    rows.forEach((r, i) => {
      const y = y0 + i * rh;
      s.addShape(pres.shapes.LINE, { x: M, y, w: CW, h: 0, line: { color: C.accent3, width: 0.75 }, objectName: "Row rule " + (i + 1) });
      mono(s, "0" + (i + 1), { x: M, y: y + 0.27, w: 0.6, h: 0.3, fontSize: 12 });
      T(s, r[0], { x: 1.6, y, w: 3.7, h: rh, fontSize: 22, valign: "middle" });
      T(s, r[1], { x: 5.45, y, w: W - M - 5.45, h: rh, fontSize: 17, color: C.text2, valign: "middle" });
    });
    s.addShape(pres.shapes.LINE, { x: M, y: y0 + 4 * rh, w: CW, h: 0, line: { color: C.accent3, width: 0.75 }, objectName: "Row rule 5" });
    dot(s, M, 6.27, 0.12);
    mono(s, "LIVE", { x: M + 0.24, y: 6.18, w: 0.7, h: 0.3, fontSize: 11 });
    wave(s, M + 1.0, 6.33, 0.38);
    T(s, "Spoken to the system in Korean (built for Korean lectures)  ·  Backup: recorded video",
      { x: 3.35, y: 6.15, w: W - M - 3.35 - 1.1, h: 0.36, fontSize: 14, color: C.text2, valign: "middle" });
  }

  // 7. 확산 모델을 고리 안에
  pres.addSection({ title: "Experiments" });
  {
    const s = S("CONTENT", "Experiments");
    kicker(s, "Experiments  ·  setup");
    title(s, ["Course concepts ", "inside", " the image stage"]);
    const xh = (pre, post) => [{ text: pre, options: { bullet: true } }, { text: "x̂₀", options: { fontFace: MONO } }, { text: post, options: { breakLine: true } }];
    const cols = [
      ["Local diffusion, no API", [
        [{ text: "SD 1.5: DDIM sampler + classifier-free guidance", options: { bullet: true, breakLine: true } }],
        [{ text: "SD-Turbo: adversarially distilled, 1–4 steps, no CFG", options: { bullet: true, breakLine: true } }],
        [{ text: "Apple M5 laptop (MPS), image cost $0", options: { bullet: true } }],
      ]],
      ["Show the reverse process", [
        xh("Capture predicted clean latent ", " at every scheduler step"),
        [{ text: "Linear 4-channel latent → RGB (no VAE decode)", options: { bullet: true, breakLine: true } }],
        [{ text: "Stream a small JPEG to the slide over WebSocket", options: { bullet: true } }],
      ]],
    ];
    cols.forEach((c, i) => {
      const x = M + i * 6.1;
      mono(s, c[0].toUpperCase(), { x, y: 1.95, w: 5.6, h: 0.3 });
      T(s, c[1].flat(), { x, y: 2.32, w: 5.6, h: 1.4, fontSize: 15, paraSpaceAfter: 6 });
    });
    const sw = CW, sh = sw * 360 / 2632, sy = 3.95;
    img(s, "denoise_strip.jpg", M, sy, sw, sh, "Denoising preview at steps 4, 12, 22 of 25 and the final image", "Denoising strip");
    const pw = sw * 664 / 2632;
    [["x̂₀  ·  STEP 4 / 25", false], ["STEP 12 / 25", false], ["STEP 22 / 25", false], ["FINAL IMAGE", true]].forEach((l, i) =>
      mono(s, l[0], { x: M + i * pw, y: sy + sh + 0.14, w: pw - 0.2, h: 0.28, color: l[1] ? C.accent1 : C.text2 }));
    capline(s, "Note", "SD 1.5, DDIM 25 steps (about 12 s): presenter and audience screens show 23 intermediate previews. With SD-Turbo (2 steps, 0.6 s) the preview is barely visible.");
  }

  // 8. X2 가이던스
  {
    const s = S("CONTENT", "Experiments");
    kicker(s, "Experiments  ·  X2 guidance scale");
    title(s, ["Guidance buys alignment, ", "costs diversity"]);
    const labels = ["1", "3", "5", "7.5", "12"];
    const line = (ttl, min, max, fmt, color) => ({
      ...chartBase(), title: ttl, chartColors: [color], lineSize: 2, lineDataSymbol: "circle", lineDataSymbolSize: 8,
      dataLabelPosition: "t", valAxisMinVal: min, valAxisMaxVal: max, dataLabelFormatCode: fmt, valAxisLabelFormatCode: fmt,
      showCatAxisTitle: true, catAxisTitle: "CFG scale", catAxisTitleColor: H.dk2, catAxisTitleFontSize: 12, catAxisTitleFontFace: "+mn-lt",
    });
    const cw = (CW - 0.35) / 2;
    s.addChart(pres.charts.LINE, [{ name: "CLIP alignment", labels, values: [21.5, 24.6, 25.7, 25.0, 25.6] }],
      { x: M, y: 1.9, w: cw, h: 3.5, ...line("Scene alignment (CLIP, higher is closer)", 20, 27, "0.0", H.accent1), objectName: "CFG vs CLIP chart" });
    s.addChart(pres.charts.LINE, [{ name: "Diversity", labels, values: [0.269, 0.209, 0.213, 0.182, 0.177] }],
      { x: M + cw + 0.35, y: 1.9, w: cw, h: 3.5, ...line("Diversity between seeds (1 − cosine)", 0.15, 0.28, "0.00", H.accent2), objectName: "CFG vs diversity chart" });
    box(s, M, 5.55, CW, 1.0, "Sampler warning");
    mono(s, "X1  ·  SAMPLER CHECK", { x: M + 0.3, y: 5.68, w: 4, h: 0.28 });
    T(s, "DDPM at 10 steps visibly broke shapes while DDIM kept them, yet CLIP scores were the same (25.5 vs 25.1). CLIP measures prompt match, not quality.",
      { x: M + 0.3, y: 5.98, w: CW - 0.6, h: 0.5, fontSize: 14.5 });
    capline(s, "Method", "X2 · SD 1.5, DDIM 25 steps · 12 lecture scenes × 2 fixed seeds · CLIP ViT-B/32 (not the generators' text encoder), cosine × 100");
  }

  // 9. X3 증류 모델
  {
    const s = S("CONTENT", "Experiments");
    kicker(s, "Experiments  ·  X3 distilled model");
    title(s, ["A ", "distilled", " model fits a live lecture"]);
    s.addChart(pres.charts.BAR, [{ name: "Seconds per image", labels: ["SD-Turbo · 1 step", "SD-Turbo · 2 steps", "SD-Turbo · 4 steps", "SD 1.5 · 25 steps, CFG 7.5"], values: [0.51, 0.68, 0.99, 11.1] }], {
      x: M, y: 1.9, w: 7.1, h: 3.55, ...chartBase(), barDir: "bar", title: "Seconds per image (lower is better)",
      chartColors: [H.accent1, H.accent1, H.accent1, H.accent4], dataLabelPosition: "outEnd", dataLabelFormatCode: "0.0#\" s\"",
      valAxisHidden: true, valGridLine: { style: "none" }, barGapWidthPct: 60, catAxisOrientation: "maxMin", catAxisLabelFontSize: 13,
      objectName: "Speed chart",
    });
    const stats = [
      ["~16×", "faster than SD 1.5", "0.68 s vs 11.1 s (2 steps vs 25 steps)", C.accent1],
      ["28.2 vs 25.0", "CLIP alignment", "SD-Turbo 2 steps vs SD 1.5; CIs barely overlap", C.text1],
    ];
    stats.forEach((st, i) => {
      const y = 1.95 + i * 1.75;
      T(s, st[0], { x: 8.35, y, w: W - M - 8.35, h: 0.85, fontFace: SERIF, fontSize: i ? 46 : 60, color: st[3], valign: "bottom" });
      T(s, st[1], { x: 8.35, y: y + 0.92, w: W - M - 8.35, h: 0.35, fontSize: 16, bold: true });
      T(s, st[2], { x: 8.35, y: y + 1.27, w: W - M - 8.35, h: 0.35, fontSize: 12.5, color: C.text2 });
    });
    box(s, M, 5.55, CW, 1.05, "Caveat");
    T(s, [
      { text: "CAVEAT", options: { fontFace: MONO, fontSize: 10.5, charSpacing: 2, color: C.accent1, breakLine: true } },
      { text: "SD-Turbo is built on SD 2.1 with a larger text encoder, so this is not distillation alone.", options: { breakLine: true } },
      { text: "System default: SD-Turbo, 2 steps. For reference, the gpt-image-2 API took 14–19 s (n = 1)." },
    ], { x: M + 0.3, y: 5.55, w: CW - 0.6, h: 1.05, fontSize: 14, valign: "middle" });
    capline(s, "Method", "X3 · same 12 scenes × 2 seeds, 768 × 432 · time = median per image on the laptop after warm-up");
  }

  // 10. X4 강의 맥락
  {
    const s = S("CONTENT", "Experiments");
    kicker(s, "Experiments  ·  X4 lecture context");
    title(s, ["Lecture context moves images ", "toward the intent"]);
    T(s, "+2.10", { x: M, y: 1.85, w: 3.3, h: 1.3, fontFace: SERIF, fontSize: 88, color: C.accent1, valign: "middle" });
    T(s, [{ text: "CLIP points between the image and the intended scene", options: { bold: true, breakLine: true } },
      { text: "95% CI +0.65 to +3.61 · permutation p = 0.010 · B better in 17 of 28 pairs", options: { fontSize: 12.5, color: C.text2, paraSpaceBefore: 4 } }],
      { x: M + 3.35, y: 1.95, w: 3.2, h: 1.1, fontSize: 15, valign: "middle" });
    const mini = [
      [[{ text: "7 " }, { text: "→", options: { fontFace: "+mn-lt" } }, { text: " 0" }], "clarification questions out of 42", "Without context the planner couldn't tell what “that analogy” meant"],
      [[{ text: "+6.41 " }, { text: "→", options: { fontFace: "+mn-lt" } }, { text: " +2.10" }], "text gain → image gain", "Text p = 0.002; the image model loses two-thirds of it"],
    ];
    mini.forEach((m, i) => {
      const y = 3.4 + i * 1.3;
      box(s, M, y, 6.55, 1.1, "Stat card " + (i + 1));
      T(s, m[0], { x: M + 0.25, y, w: 2.6, h: 1.1, fontFace: SERIF, fontSize: 27, valign: "middle" });
      T(s, [{ text: m[1], options: { bold: true, breakLine: true } }, { text: m[2], options: { fontSize: 12.5, color: C.text2 } }],
        { x: M + 2.95, y, w: 3.45, h: 1.1, fontSize: 15, valign: "middle" });
    });
    T(s, "Top row, S09: a modern classroom (A) becomes the Joseon-era exam hall the lecturer meant (B).", { x: M, y: 6.02, w: 6.55, h: 0.45, fontSize: 12.5, italic: true, color: C.text2 });
    const ih = 4.55, iw = ih * 720 / 680;
    img(s, "x4_examples.jpg", W - M - iw, 1.9, iw, ih, "Pairs of images without and with lecture context for scenarios S09, L24 and L26", "X4 examples");
    capline(s, "Method", "X4 · 42 scenarios (12 general + 30 from this course) · A: request only, B: + recent speech + current slide · same planner, model, seeds · intended scenes committed to git before generation", 11);
  }

  // 11. 실패와 한계
  pres.addSection({ title: "Closing" });
  {
    const s = S("CONTENT", "Closing");
    kicker(s, "Limits");
    title(s, ["What ", "didn't", " work, and what it taught me"]);
    const items = [
      ["Fake text in images", "SD-Turbo writes pseudo-text on paper and signs. Weak CFG + negative prompt (X5) and a “blank surfaces” planner rule: about 9 / 34 images before and after.", "Known limitation; gpt-image-2 when quality matters", false],
      ["CLIP as a text detector", "Zero-shot “image with text” probability. Of the top 6 flagged images, only 1 really had text.", "Dropped; text needs human judgment", false],
      ["77-token truncation (bug found)", "Planner image prompts exceeded CLIP's 77-token limit in 18 / 18 cases, so style words were cut.", "Fixed: token-aware trimming → 7 / 17", true],
      ["Evaluation limits", "CLIP is the only metric. Scenarios and intended scenes were written by the same side (with an AI assistant). Latency is n = 1.", "Next: blind human evaluation", false],
    ];
    const g = 0.3, cw = (CW - g) / 2, ch = 2.2;
    items.forEach((it, i) => {
      const x = M + (i % 2) * (cw + g), y = 1.95 + Math.floor(i / 2) * (ch + 0.25);
      box(s, x, y, cw, ch, it[0] + " card");
      mono(s, "0" + (i + 1), { x: x + 0.3, y: y + 0.3, w: 0.5, h: 0.28, fontSize: 12 });
      T(s, it[0], { x: x + 0.85, y: y + 0.22, w: cw - 1.15, h: 0.45, fontSize: 19, bold: true });
      T(s, it[1], { x: x + 0.3, y: y + 0.78, w: cw - 0.6, h: 0.9, fontSize: 14, color: C.text2 });
      T(s, "→ " + it[2], { x: x + 0.3, y: y + 1.72, w: cw - 0.6, h: 0.32, fontSize: 14, bold: true, color: it[3] ? C.accent1 : C.text1 });
    });
  }

  // 12. 정리
  {
    const s = S("SECTION", "Closing");
    mono(s, "CLOSING", { x: M, y: 0.46, w: 6, h: 0.3 });
    title(s, ["Takeaways"]);
    const items = [
      ["The lecture is a good condition", "+2.1 CLIP toward the intended scene (p = 0.010); 0 clarifying questions, not 7"],
      ["Distillation makes diffusion live", "0.7 s per image; about 6 s from spoken request to finished slide"],
      ["The bottleneck is the image model", "Context gains shrink by two-thirds from text to image; fake text remains"],
    ];
    items.forEach((it, i) => {
      const y = 2.15 + i * 1.25;
      T(s, String(i + 1), { x: M, y: y - 0.12, w: 0.6, h: 0.8, fontFace: SERIF, fontSize: 46, color: C.accent1 });
      T(s, [{ text: it[0], options: { fontSize: 23, breakLine: true } }, { text: it[1], options: { fontSize: 15, color: C.text2, paraSpaceBefore: 3 } }],
        { x: M + 0.8, y, w: 7.7, h: 1.05 });
    });
    const nx = 9.3, nw = W - M - nx;
    box(s, nx, 2.2, nw, 2.55, "Next steps card");
    mono(s, "NEXT", { x: nx + 0.3, y: 2.45, w: 2, h: 0.28 });
    T(s, [
      { text: "Blind human rating of fit, breakage and fake text", options: { bullet: true, breakLine: true } },
      { text: "Real STT transcripts in the detector test set", options: { bullet: true, breakLine: true } },
      { text: "Latency over 10+ runs", options: { bullet: true } },
    ], { x: nx + 0.3, y: 2.85, w: nw - 0.55, h: 1.75, fontSize: 15, paraSpaceAfter: 8 });
    T(s, [{ text: "Thank you  ·  " }, { text: "Questions?", options: { italic: true, color: C.accent1 } }],
      { x: M, y: 5.95, w: 8, h: 0.75, fontFace: SERIF, fontSize: 36 });
  }

  await pres.writeFile({ fileName: OUT });
  if (APPLY_THEME) {
    const { applyTheme } = require(APPLY_THEME);
    await applyTheme(OUT, THEME);
  }
  console.log("wrote", OUT, "slides:", n);
}

// ───────────────────────── script.md ─────────────────────────
function writeScript() {
  const total = SCRIPT.reduce((a, s) => { const [m, sec] = s.t.split(":").map(Number); return a + m * 60 + sec; }, 0);
  const L = [];
  L.push("# NextSlide 발표 대본 (영어 / 한국어)", "");
  L.push(`발표 파일: [NextSlide_final.pptx](NextSlide_final.pptx). 슬라이드 노트에도 같은 대본이 들어 있습니다. 이 파일과 노트는 \`build_deck.js\`가 함께 만듭니다.`, "");
  L.push(`- 예상 시간: 약 ${Math.floor(total / 60)}분 ${total % 60}초(시연 2분 포함).`);
  L.push("- 시연을 발표 끝에 하려면 PowerPoint에서 6번 슬라이드(Live demo)를 12번(Takeaways) 앞으로 옮기면 됩니다. 대본 순서도 같이 옮깁니다.");
  L.push("- [name] 자리에 이름을 넣어 말하세요. 표지에는 이름이 없으니 필요하면 직접 추가하세요.");
  L.push("- 글꼴: 덱은 Instrument Serif·Instrument Sans·IBM Plex Mono를 씁니다(OFL). 발표할 컴퓨터에 `fonts/` 폴더의 글꼴을 먼저 설치하세요. 없으면 PowerPoint가 다른 글꼴로 바꿔 보여 줍니다.", "");
  SCRIPT.forEach((s, i) => {
    L.push(`## ${i + 1}. ${s.title} (${s.t})`, "", `**EN** ${s.en}`, "", `**KO** ${s.ko}`, "");
    if (s.title === "Live demo") {
      L.push("### 시연 대본 (Demo script)", "");
      L.push("준비: 백엔드를 `IMAGE_PROVIDER=local LOCAL_IMAGE_MODEL=sd15`로 켜면 디노이징 미리보기가 약 12초 동안 보입니다(SD-Turbo는 0.6초라 거의 안 보임). 청중 화면을 두 번째 창이나 프로젝터에 띄우고, 같은 흐름을 녹화한 백업 영상을 준비합니다.", "");
      DEMO.forEach((d) => {
        L.push(`**${d.step}** (${d.time})`, "", `- 시스템에 말할 문장(한국어): ${d.speak}`);
        if (d.meaning) L.push(`  - 뜻: ${d.meaning}`);
        L.push(`- 설명 EN: ${d.point_en}`, `- 설명 KO: ${d.point_ko}`, "");
      });
      L.push("문제가 생기면: \"Let me switch to the recorded video.\" (녹화 영상으로 넘어가겠습니다.) 마이크가 안 되면 텍스트 입력의 \"발화로 입력\"에 같은 문장을 넣습니다.", "");
    }
  });
  L.push("## 예상 질문과 답변 (Q&A)", "");
  QA.forEach((q, i) => {
    L.push(`**Q${i + 1}. ${q.q_en}** (${q.q_ko})`, "", `- EN: ${q.a_en}`, `- KO: ${q.a_ko}`, "");
  });
  fs.writeFileSync(path.join(HERE, "script.md"), L.join("\n"));
  console.log("wrote script.md, total", total, "s");
}

build().then(writeScript).catch((e) => { console.error(e); process.exit(1); });
