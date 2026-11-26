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
// 청자 기준 흐름: 문제 → 장면 → 동작 → 핵심 아이디어 → 시연 → 수업 개념 → 실험 질문 3개 → 한계 → 정리.
// backup: true 인 장은 질문이 나올 때만 쓰는 부록이라 발표 시간에 넣지 않는다.
const SCRIPT = [
  {
    t: "0:25", title: "Title",
    en: "Hi, I'm [name]. My project is NextSlide. The idea fits in one sentence: while I'm lecturing, I say what the next slide should show, and it gets made while I keep talking.",
    ko: "안녕하세요, [이름]입니다. 제 프로젝트는 NextSlide입니다. 아이디어는 한 문장입니다. 강의하면서 다음 장에 무엇을 보여 줄지 말하면, 제가 계속 말하는 동안 그 장이 만들어집니다.",
  },
  {
    t: "0:40", title: "The problem",
    en: "Anyone who has taught knows this moment. The slides were made before class. Then, halfway through, the students look lost, so you come up with an analogy on the spot. Say: overfitting is like a student who memorized the answers to old exams. It's a good explanation, but there's no slide for it. And making one right then means stopping the lecture.",
    ko: "가르쳐 본 사람이라면 아는 순간이 있습니다. 슬라이드는 수업 전에 만들어 둡니다. 그런데 중간에 학생들이 잘 못 따라오는 것 같으면 그 자리에서 비유를 하나 떠올립니다. 예를 들어 '과적합은 기출문제 답을 외운 학생과 같다' 같은 것이요. 좋은 설명인데 보여 줄 슬라이드가 없습니다. 그 자리에서 만들려면 강의를 멈춰야 합니다.",
  },
  {
    t: "0:40", title: "Just say it",
    en: "With NextSlide, I just say it. I gave the system this sentence in Korean: 'In the next slide, I'll explain overfitting by comparing it to a student who memorized the exam questions.' It recognized a request and made this slide: a title, three short points, and a picture.",
    ko: "NextSlide에서는 그냥 말하면 됩니다. 시스템에 '다음 슬라이드에서는 과적합을 시험 문제를 외운 학생에 비유해서 설명하겠습니다'라는 문장을 넣었더니, 요청으로 알아듣고 이 장을 만들었습니다. 제목, 짧은 설명 세 줄, 그림입니다.",
  },
  {
    t: "0:50", title: "How it works",
    en: "This is my presenter screen. It works in three steps. One, it listens: my speech is transcribed live by Gemini. Two, it decides: a rule-based detector reacts only to clear requests like 'in the next slide'. If I say 'don't make a slide', or I'm quoting someone, it does nothing. On a test set of 60 sentences it was right 56 times, and it never missed a request. Three, it makes the slide: a language model writes the title and points from my request and the last ninety seconds of the lecture, and then the picture is drawn. I see the new slide first; the audience sees it when I advance.",
    ko: "제 발표자 화면입니다. 세 단계로 동작합니다. 첫째, 듣습니다. 제 말을 Gemini가 실시간으로 받아 적습니다. 둘째, 판단합니다. 규칙 기반 감지기가 '다음 슬라이드에서는' 같은 분명한 요청에만 반응합니다. '만들지 마세요'라고 하거나 남의 말을 인용하면 아무것도 하지 않습니다. 60문장 평가 세트에서 56개를 맞혔고, 요청을 놓친 적은 없었습니다. 셋째, 만듭니다. 언어 모델이 제 요청과 직전 90초 동안 한 말을 보고 제목과 본문을 쓰고, 그다음 그림을 그립니다. 새 장은 제가 먼저 보고, 청중은 제가 넘길 때 봅니다.",
  },
  {
    t: "0:50", title: "Lecture context",
    en: "This is the core idea. Requests in a lecture are often vague. Here, a history teacher has been talking about the civil service exam in the Joseon dynasty, and then says: 'In the next slide, show the exam hall.' With only that sentence, the system draws a modern classroom. With what the teacher said just before, it draws the Joseon exam ground the teacher meant. No one wrote a prompt; the context came from the lecture. Whether this really helps is my main experiment, which I'll show later.",
    ko: "핵심 아이디어입니다. 강의 중의 요청은 모호한 경우가 많습니다. 역사 선생님이 조선의 과거 시험 이야기를 하다가 '다음 슬라이드에서는 시험장 풍경을 보여 주세요'라고 합니다. 이 문장만 주면 시스템은 현대식 교실을 그립니다. 직전에 한 말까지 주면 선생님이 뜻한 조선의 과거 시험장을 그립니다. 아무도 프롬프트를 쓰지 않았고, 맥락은 강의에서 왔습니다. 이게 정말 도움이 되는지는 뒤에서 핵심 실험으로 보여 드리겠습니다.",
  },
  {
    t: "0:35", title: "Right form",
    en: "One more design choice comes from Lecture 17. Image models make plausible pictures, but they still get text, counts and relations wrong. So the language model first decides what kind of slide this is. Only illustrations go to the image model. Equations are typeset with KaTeX, and comparisons use a fixed layout. All three of these were made by the system.",
    ko: "설계 선택 하나는 17강에서 왔습니다. 이미지 모델은 그럴듯한 그림은 그리지만 글자, 개수, 관계는 아직 자주 틀립니다. 그래서 언어 모델이 먼저 어떤 종류의 장인지 정합니다. 설명 그림만 이미지 모델에 보내고, 수식은 KaTeX로 조판하고, 비교는 정해진 레이아웃을 씁니다. 이 세 장은 모두 시스템이 만든 것입니다.",
  },
  {
    t: "2:00", title: "Live demo",
    en: "Now let me show it live. The system is built for Korean lectures, so I'll speak the lecture lines in Korean and translate as I go. Watch for the four things on the slide. (Run the demo. See the demo script below.)",
    ko: "이제 직접 보여 드리겠습니다. 한국어 강의용 시스템이라 강의 문장은 한국어로 말하고 바로 영어로 옮기겠습니다. 화면의 네 가지를 봐 주세요. (시연 진행. 아래 시연 대본 참고)",
  },
  {
    t: "0:40", title: "Watching diffusion",
    en: "Now the part that connects to this course. In the demo, the picture came from an open diffusion model running on my laptop. A diffusion model starts from noise and removes it step by step. At every step it also predicts what the finished image will look like; that's x-hat-zero from the lecture. I send that prediction to the screen, so you can watch the picture form. Here it is at steps 4, 12 and 22 of 25. It costs almost nothing, because I turn it into colors with a simple linear map instead of running the full decoder every step.",
    ko: "이제 수업과 연결되는 부분입니다. 시연의 그림은 제 노트북에서 도는 공개 확산 모델이 그렸습니다. 확산 모델은 잡음에서 시작해 한 단계씩 잡음을 걷어 냅니다. 매 단계 모델은 완성 그림이 어떨지도 예측하는데, 수업에서 배운 x̂₀입니다. 이 예측을 화면으로 보내서 그림이 만들어지는 과정을 보여 줍니다. 25단계 중 4, 12, 22단계 모습입니다. 매 단계 디코더 전체를 돌리지 않고 간단한 선형 변환으로 색을 만들기 때문에 비용은 거의 없습니다.",
  },
  {
    t: "0:40", title: "Experiment 1 · Speed",
    en: "I ran three experiments. First: is it fast enough for a live lecture? Stable Diffusion 1.5 with 25 steps takes 11 seconds per image. SD-Turbo is a distilled model that needs only a few steps; with two steps it takes 0.7 seconds, about sixteen times faster, and its pictures matched the prompts a little better. With SD-Turbo, one test run took about six seconds from my sentence to a finished slide. So that's the default.",
    ko: "실험은 세 가지입니다. 첫째, 실시간 강의에 쓸 만큼 빠른가? Stable Diffusion 1.5로 25단계를 돌리면 그림 한 장에 11초가 걸립니다. SD-Turbo는 몇 단계만 쓰도록 증류된 모델인데, 2단계로 0.7초, 약 16배 빠르고 프롬프트 일치도도 조금 더 높았습니다. SD-Turbo로 한 번 측정했을 때 제 문장부터 완성된 장까지 약 6초였습니다. 그래서 이것을 기본값으로 씁니다.",
  },
  {
    t: "0:35", title: "Experiment 2 · Guidance",
    en: "Second: what does classifier-free guidance change? Same prompt, same seed; only the guidance scale changes. At 1 the picture barely forms; by 7.5 it clearly follows the prompt. Averaged over 12 scenes, prompt match rises and levels off around 5, while the variety between seeds keeps falling. That's the trade-off from the lecture. One warning about the metric: CLIP measures prompt match, not quality. When DDPM at 10 steps gave broken images, the CLIP score barely moved.",
    ko: "둘째, classifier-free guidance는 무엇을 바꾸는가? 프롬프트와 시드는 같고 가이던스 세기만 바꿨습니다. 1에서는 그림이 거의 안 만들어지고, 7.5쯤 되면 프롬프트를 분명히 따릅니다. 장면 12개 평균으로 보면 프롬프트 일치도는 오르다가 5 근처에서 멈추고, 시드 간 다양성은 계속 줄어듭니다. 수업에서 배운 트레이드오프 그대로입니다. 지표에 대한 주의 하나: CLIP은 프롬프트 일치를 볼 뿐 품질은 보지 못합니다. DDPM 10단계로 그림이 깨졌을 때도 CLIP 점수는 거의 그대로였습니다.",
  },
  {
    t: "1:00", title: "Experiment 3 · Lecture context",
    en: "Third, the main question: does the lecture context actually help? I wrote 42 lecture scenarios, 30 of them based on this course's lecture slides. Each request runs twice. A gets only the request; B also gets the recent speech and the current slide. Everything else is the same. Before generating anything, I wrote down the scene the lecturer meant and committed it to git, so I couldn't change it later. Each bar is one scenario: how much closer B's picture is to that scene than A's. Most bars are above zero. On average B is 2.1 points closer, and a permutation test gives p = 0.010. Also, without context the system had to ask me what I meant 7 times out of 42; with context, never. One honest note: in the text prompt the gain was 6.4 points, but only 2.1 survives into the picture.",
    ko: "셋째, 핵심 질문입니다. 강의 맥락이 정말 도움이 될까요? 강의 시나리오 42개를 만들었고, 그중 30개는 이 수업 강의자료를 바탕으로 했습니다. 요청마다 두 번 돌립니다. A는 요청만, B는 최근 발화와 현재 장까지 받습니다. 나머지는 모두 같습니다. 생성하기 전에 강사가 뜻한 장면을 적어 git에 커밋해서 나중에 바꿀 수 없게 했습니다. 막대 하나가 시나리오 하나이고, B의 그림이 A보다 그 장면에 얼마나 더 가까운지를 나타냅니다. 대부분 0보다 위에 있습니다. 평균 2.1점 더 가까웠고, 순열 검정 p값은 0.010입니다. 그리고 맥락이 없으면 42개 중 7번은 시스템이 무슨 뜻인지 되물어야 했는데, 맥락이 있으면 한 번도 없었습니다. 솔직히 말씀드리면, 프롬프트 글에서는 6.4점이던 차이가 그림에서는 2.1점만 남았습니다.",
  },
  {
    t: "0:40", title: "What still goes wrong",
    en: "Some things still go wrong. The fast model writes fake text on paper and signs, in about 9 of 34 images, and telling the planner to describe blank surfaces didn't change that. My only automatic judge is CLIP, and we just saw it can miss broken images. And I wrote the scenarios and intended scenes myself, with help from an AI assistant. So the next step is a blind evaluation by people.",
    ko: "아직 안 되는 것도 있습니다. 빠른 모델은 종이나 간판에 가짜 글자를 그리고, 34장 중 약 9장이 그랬습니다. 기획 모델에 빈 면으로 묘사하라고 해도 줄지 않았습니다. 자동 평가는 CLIP 하나뿐인데, 방금 본 것처럼 깨진 그림을 놓칠 수 있습니다. 그리고 시나리오와 의도 장면을 제가 AI 보조 도구의 도움을 받아 직접 썼습니다. 그래서 다음 단계는 사람이 보는 블라인드 평가입니다.",
  },
  {
    t: "0:25", title: "To sum up",
    en: "To sum up. You say what the next slide should show, and it's ready in a few seconds. Using the lecture itself as context brings the picture closer to what you meant. The weak spot is still the image model. Thank you. I'm happy to take questions.",
    ko: "정리하겠습니다. 다음 장에 보여 줄 것을 말하면 몇 초 안에 준비됩니다. 강의 자체를 맥락으로 쓰면 그림이 뜻한 장면에 더 가까워집니다. 약한 부분은 아직 이미지 모델입니다. 감사합니다. 질문 받겠습니다.",
  },
  {
    t: "-", title: "Backup · Prior work", backup: true,
    en: "(Use if asked about prior work.) Live-staging tools such as ZeroPrep interpret every utterance and show the result to the audience right away. NextSlide reacts only to explicit requests, shows the presenter first, and picks the slide form instead of always making cards.",
    ko: "(이전 연구를 물으면 사용) ZeroPrep 같은 실시간 발표 도구는 모든 발화를 해석해 바로 청중에게 보여 줍니다. NextSlide는 명시적인 요청에만 반응하고, 발표자에게 먼저 보여 주며, 항상 카드를 만드는 대신 슬라이드 형태를 고릅니다.",
  },
  {
    t: "-", title: "Backup · System numbers", backup: true,
    en: "(Use if asked about the detector, tests or speed.) The detector got 56 of 60 test sentences right: no missed requests, one slide made when it shouldn't have been, and three unnecessary 'which topic?' questions. There are 112 automated backend tests with mock providers. End to end, one run took 6.2 seconds with local SD-Turbo and 20 seconds with the gpt-image-2 API.",
    ko: "(감지기·테스트·속도를 물으면 사용) 감지기는 평가 문장 60개 중 56개를 맞혔습니다. 놓친 요청 0건, 만들면 안 되는데 만든 경우 1건, 불필요하게 주제를 되물은 경우 3건입니다. 모의 제공자를 쓰는 자동 백엔드 테스트가 112개 있습니다. 전체 흐름은 로컬 SD-Turbo로 한 번 6.2초, gpt-image-2 API로 20초였습니다.",
  },
  {
    t: "-", title: "Backup · How it was measured", backup: true,
    en: "(Use if asked about the method.) Scores are cosine similarity from CLIP ViT-B/32, a different model from the generators' text encoders, times 100. X1 to X3 used 12 lecture scenes and 2 fixed seeds, changing one setting at a time, with bootstrap confidence intervals. X4 compared 28 paired scenarios with a permutation test. SD-Turbo is based on SD 2.1, so its gain is not distillation alone. The experiments also found a real bug: prompts longer than CLIP's 77 tokens lost their style words, now fixed.",
    ko: "(실험 방법을 물으면 사용) 점수는 생성 모델의 텍스트 인코더와 다른 CLIP ViT-B/32의 코사인 유사도에 100을 곱한 값입니다. X1~X3은 강의 장면 12개와 고정 시드 2개로 한 번에 설정 하나만 바꿨고, 부트스트랩 신뢰구간을 냈습니다. X4는 짝지은 시나리오 28개를 순열 검정으로 비교했습니다. SD-Turbo는 SD 2.1 기반이라 증류만의 효과는 아닙니다. 실험 중 실제 버그도 찾았습니다. CLIP의 77토큰을 넘는 프롬프트에서 화풍 문구가 잘리던 문제이고, 고쳤습니다.",
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
// X4 시나리오별 B−A (CLIP 점수 차). 출처: eval/results/diffusion/x4_context_n42/summary.md (그림이 A·B 모두 있는 28개)
const X4_DIFF = {
  L01: 1.43, L02: -0.01, L05: 3.24, L06: 10.78, L07: -0.16, L08: -3.03, L11: 1.51, L12: 1.75, L13: 4.89, L15: -3.98,
  L16: 3.98, L17: -5.0, L18: -0.21, L19: 2.84, L21: -0.65, L23: 2.16, L24: 6.21, L26: 9.62, L28: 6.72, L29: 4.96,
  L30: -1.53, S01: 0.27, S02: 1.57, S03: 1.97, S04: -0.2, S07: -0.26, S09: 10.82, S12: -0.9,
};

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
  const slideNum = () => ({ x: W - M - 1.0, y: 6.9, w: 1.0, h: 0.3, fontFace: MONO, fontSize: 10, color: C.text2, align: "right" });
  pres.defineSlideMaster({
    title: "TITLE",
    background: { path: BG_TITLE },
    objects: [
      { placeholder: { options: { name: "title", type: "title", x: M, y: 1.7, w: 6.4, h: 1.9, fontSize: 112, color: C.text1, valign: "bottom", align: "left", margin: 0 }, text: "" } },
      { placeholder: { options: { name: "body", type: "body", x: M, y: 3.8, w: 5.9, h: 1.4, fontSize: 24, color: C.text1, valign: "top", margin: 0 }, text: "" } },
    ],
  });
  pres.defineSlideMaster({
    title: "CONTENT",
    background: { path: BG_CONTENT },
    margin: [0.5, M, 0.6, M],
    objects: [
      { placeholder: { options: { name: "title", type: "title", x: M, y: 0.62, w: CW, h: 0.95, fontSize: 40, color: C.text1, valign: "middle", align: "left", margin: 0 }, text: "" } },
    ],
    slideNumber: slideNum(),
  });
  pres.defineSlideMaster({
    title: "SECTION",
    background: { path: BG_TITLE },
    objects: [
      { placeholder: { options: { name: "title", type: "title", x: M, y: 0.7, w: CW, h: 1.2, fontSize: 64, color: C.text1, valign: "middle", align: "left", margin: 0 }, text: "" } },
    ],
    slideNumber: slideNum(),
  });

  // 공통 요소
  const T = (s, t, o) => s.addText(t, { isTextBox: true, margin: 0, fontSize: 16, color: C.text1, valign: "top", ...o });
  const mono = (s, t, o) => T(s, t, { fontFace: MONO, fontSize: 10.5, charSpacing: 2, color: C.accent1, ...o });
  const kicker = (s, t) => mono(s, t.toUpperCase(), { x: M, y: 0.32, w: 9, h: 0.28, objectName: "Section label" });
  const dot = (s, x, y, d = 0.1) =>
    s.addShape(pres.shapes.OVAL, { x, y, w: d, h: d, fill: { color: C.accent1 }, line: { type: "none" }, objectName: "Live dot" });
  const box = (s, x, y, w, h, name, fill = C.background2) =>
    s.addShape(pres.shapes.RECTANGLE, { x, y, w, h, fill: { color: fill }, line: { type: "none" }, objectName: name });
  const frame = (s, x, y, w, h, name, color = C.accent3, width = 0.75) =>
    s.addShape(pres.shapes.RECTANGLE, { x, y, w, h, fill: { type: "none" }, line: { color, width }, objectName: name });
  const img = (s, file, x, y, w, h, alt, name) => {
    s.addImage({ path: A(file), x, y, w, h, altText: alt, objectName: name });
    frame(s, x, y, w, h, name + " frame");
  };
  const wave = (s, x, cy, h) => s.addImage({ data: WAVE.data, x, y: cy - h / 2, w: h * WAVE.ratio, h, altText: "Decorative speech waveform", objectName: "Waveform" });
  const badge = (s, n, x, y, d = 0.38) => {
    s.addShape(pres.shapes.OVAL, { x, y, w: d, h: d, fill: { color: C.accent1 }, line: { type: "none" }, objectName: "Step " + n + " badge" });
    T(s, String(n), { x, y, w: d, h: d, fontFace: MONO, fontSize: 13, bold: true, color: C.background1, align: "center", valign: "middle", objectName: "Step " + n + " number" });
  };
  const chartBase = () => ({
    showTitle: true, titleFontSize: 13, titleColor: H.dk1, titleFontFace: "+mn-lt",
    catAxisLabelColor: H.dk2, valAxisLabelColor: H.dk2, catAxisLabelFontSize: 12, valAxisLabelFontSize: 11,
    catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt",
    valGridLine: { color: H.accent3, size: 0.75 }, catGridLine: { style: "none" },
    showLegend: false, showValue: true, dataLabelColor: H.dk1, dataLabelFontSize: 11, dataLabelFontFace: "+mn-lt",
    catAxisLineShow: true, catAxisLineColor: H.accent4, valAxisLineShow: false,
    plotArea: { fill: { color: H.lt1, transparency: 100 } },
    chartArea: { fill: { color: H.lt1, transparency: 100 } },
  });
  const ko = (t, o = {}) => ({ text: t, options: { fontFace: KO, ...o } });
  const xhat = { text: "x̂₀", options: { fontFace: MONO } };

  let n = 0;
  const S = (layout, section) => {
    const s = pres.addSlide({ masterName: layout, sectionTitle: section });
    s.addNotes(notesFor(n));
    n += 1;
    return s;
  };
  // 제목: 짝수 번째 조각은 보통, 홀수 번째 조각은 이탤릭 호박색
  const title = (s, parts) => s.addText(parts.map((p, i) => (i % 2 ? { text: p, options: { italic: true, color: C.accent1 } } : { text: p })).filter((r) => r.text), { placeholder: "title" });

  // 1. 표지
  pres.addSection({ title: "Opening" });
  {
    const s = S("TITLE", "Opening");
    mono(s, "GENERATIVE AI  ·  FINAL PROJECT  ·  FALL 2026", { x: M, y: 1.25, w: 6.5, h: 0.3 });
    title(s, ["Next", "Slide"]);
    s.addText("Say what the next slide should show. It gets made while you keep talking.", { placeholder: "body" });
    const ix = 7.35, iw = W - M - ix, ih = iw * 9 / 16;
    img(s, "real_v2_illustration.jpg", ix, 2.0, iw, ih, "A slide made by NextSlide: a hiker overshooting the valley as an analogy for a learning rate that is too large", "Generated slide example");
    T(s, "A slide NextSlide made: a learning rate that is too large, shown as a hiker.", { x: ix, y: 2.0 + ih + 0.15, w: iw, h: 0.5, fontSize: 13, color: C.text2 });
  }

  // 2. 문제: 수업 전에 만든 장 사이에 즉석 비유가 끼어든다
  pres.addSection({ title: "Idea" });
  {
    const s = S("CONTENT", "Idea");
    title(s, ["Ideas that come up mid-lecture ", "have no slide"]);
    const ly = 4.3; // 시간 축
    s.addShape(pres.shapes.LINE, { x: M, y: ly, w: CW, h: 0, line: { color: C.accent4, width: 1 }, objectName: "Lecture timeline" });
    mono(s, "THE LECTURE  →", { x: M, y: ly - 0.32, w: 3, h: 0.26, color: C.text2 });
    const bw = 1.55, bh = 0.87, by = ly + 0.28;
    [[M, "SLIDE 1"], [2.55, "SLIDE 2"], [9.23, "SLIDE 3"], [W - M - bw, "SLIDE 4"]].forEach(([x, l]) => {
      box(s, x, by, bw, bh, l + " (prepared)");
      mono(s, l, { x, y: by, w: bw, h: bh, color: C.text2, align: "center", valign: "middle" });
    });
    const mx = 5.9; // 즉석 비유가 나온 순간
    s.addShape(pres.shapes.RECTANGLE, { x: mx - bw / 2, y: by, w: bw, h: bh, fill: { type: "none" }, line: { color: C.accent4, width: 1, dashType: "dash" }, objectName: "Missing slide" });
    mono(s, "NO SLIDE", { x: mx - bw / 2, y: by, w: bw, h: bh, color: C.text2, align: "center", valign: "middle" });
    s.addShape(pres.shapes.LINE, { x: mx, y: 3.38, w: 0, h: ly - 3.38, line: { color: C.accent1, width: 1 }, objectName: "Moment connector" });
    dot(s, mx - 0.09, ly - 0.09, 0.18);
    s.addShape(pres.shapes.RECTANGLE, { x: 3.4, y: 1.95, w: 5.0, h: 1.43, fill: { color: C.accent5 }, line: { color: C.accent1, width: 1 }, objectName: "Improvised analogy" });
    T(s, "“Overfitting is like a student who memorized the answers to old exams.”",
      { x: 3.62, y: 1.95, w: 4.6, h: 1.43, fontFace: SERIF, italic: true, fontSize: 24, valign: "middle" });
    T(s, "Making that slide right then means stopping the lecture.", { x: M, y: 6.0, w: CW, h: 0.6, fontFace: SERIF, fontSize: 28 });
  }

  // 3. 장면: 말하면 그 장이 생긴다
  {
    const s = S("CONTENT", "Idea");
    title(s, ["With NextSlide, ", "I just say it"]);
    dot(s, M, 2.06);
    mono(s, "WHAT I SAID", { x: M + 0.24, y: 1.97, w: 2, h: 0.28 });
    wave(s, M + 1.85, 2.11, 0.26);
    T(s, [ko("다음 슬라이드에서는", { breakLine: true }), ko("과적합을 시험 문제를 외운", { breakLine: true }), ko("학생에 비유해서 설명하겠습니다.")], { x: M, y: 2.45, w: 4.55, h: 1.45, fontSize: 20, lineSpacingMultiple: 1.1 });
    T(s, "“In the next slide, I'll explain overfitting by comparing it to a student who memorized the exam questions.”",
      { x: M, y: 3.95, w: 4.55, h: 1.0, fontSize: 15, italic: true, color: C.text2 });
    s.addShape(pres.shapes.RIGHT_ARROW, { x: 5.4, y: 3.62, w: 0.42, h: 0.38, fill: { color: C.accent1 }, line: { type: "none" }, objectName: "Arrow to result" });
    const ix = 6.0, iw = W - M - ix, ih = iw * 9 / 16;
    mono(s, "WHAT APPEARED IN MY PREVIEW", { x: ix, y: 1.97, w: iw, h: 0.28 });
    img(s, "scene_overfit.jpg", ix, 2.35, iw, ih, "The slide NextSlide made: overfitting explained as a student who memorized exam questions, with a title, three points and a picture", "Generated slide");
    T(s, "Real output from a test run with real APIs. Slide text is Korean.", { x: ix, y: 2.35 + ih + 0.14, w: iw, h: 0.35, fontSize: 13, color: C.text2 });
  }

  // 4. 동작: 실제 발표자 화면 위에 세 단계 표시
  pres.addSection({ title: "System" });
  {
    const s = S("CONTENT", "System");
    title(s, ["How it works"]);
    const steps = [
      ["Listen", [{ text: "My speech is transcribed live (Gemini)." }]],
      ["Decide", [{ text: "Only clear requests count, like “in the next slide…”. “Don't make…” and quotes are ignored." }]],
      ["Make", [{ text: "An LLM writes the slide from the request and the last 90 s of the lecture. Then the picture is drawn." }]],
    ];
    steps.forEach((st, i) => {
      const y = 1.95 + i * 1.35;
      badge(s, i + 1, M, y);
      T(s, st[0], { x: M + 0.55, y: y - 0.02, w: 3.6, h: 0.42, fontSize: 20, bold: true });
      T(s, st[1], { x: M + 0.55, y: y + 0.42, w: 3.75, h: 0.85, fontSize: 14.5, color: C.text2 });
    });
    const x0 = 5.2, w = 6.95, sc = w / 1440, h = 760 * sc, y0 = 1.95;
    img(s, "presenter_ui.jpg", x0, y0, w, h, "NextSlide presenter screen: current slide on the left; next-slide preview, live transcript and detected request on the right", "Presenter screen");
    // 패널 위치(원본 픽셀): 듣기=음성 인식, 판단=생성 요청, 만들기=다음 장 미리보기
    [[1, 364, 560], [2, 574, 750], [3, 14, 350]].forEach(([k, top, bot]) => {
      frame(s, x0 + 1025 * sc, y0 + top * sc, 398 * sc, (bot - top) * sc, "Step " + k + " area", C.accent1, 1.5);
      badge(s, k, x0 + w + 0.1, y0 + ((top + bot) / 2) * sc - 0.19);
    });
    T(s, "I see the new slide first. The audience sees it when I advance.", { x: M, y: 6.2, w: CW, h: 0.45, fontSize: 17 });
  }

  // 5. 핵심 아이디어: 직전에 한 말을 같이 쓴다
  {
    const s = S("CONTENT", "System");
    title(s, ["It also uses ", "what I said just before"]);
    mono(s, "A HISTORY LESSON, A MINUTE EARLIER  ·  TRANSLATED", { x: M, y: 1.85, w: 7.0, h: 0.26, color: C.text2 });
    T(s, "“Joseon's civil service exam chose government officials. … Today we follow a scholar walking to Hanyang to take it.”",
      { x: M, y: 2.15, w: 6.9, h: 0.95, fontFace: SERIF, italic: true, fontSize: 19 });
    mono(s, "THEN THE REQUEST", { x: 7.95, y: 1.85, w: 4.6, h: 0.26 });
    T(s, [{ text: "“In the next slide,", options: { breakLine: true } }, { text: "show the exam hall.”" }], { x: 7.95, y: 2.15, w: W - M - 7.95, h: 0.95, fontSize: 20 });
    const g = 0.4, iw = (CW - g) / 2, ih = iw * 9 / 16, iy = 3.55;
    T(s, [{ text: "Request only", options: { bold: true } }, { text: "  →  a modern classroom", options: { color: C.text2 } }], { x: M, y: iy - 0.36, w: iw, h: 0.3, fontSize: 15 });
    T(s, [{ text: "With the lecture before it", options: { bold: true, color: C.accent1 } }, { text: "  →  a Joseon exam ground", options: { color: C.text2 } }], { x: M + iw + g, y: iy - 0.36, w: iw, h: 0.3, fontSize: 15 });
    img(s, "s09_request_only.jpg", M, iy, iw, ih, "Image generated from the request only: a modern classroom", "Request only image");
    img(s, "s09_with_context.jpg", M + iw + g, iy, iw, ih, "Image generated with the lecture context: a Joseon-era civil service exam ground", "With context image");
  }

  // 6. 형태 고르기
  {
    const s = S("CONTENT", "System");
    title(s, ["Pictures only when a picture helps"]);
    T(s, "Image models still get text, counts and relations wrong (Lecture 17). So the LLM first picks the kind of slide, and only illustrations go to the image model.",
      { x: M, y: 1.85, w: CW, h: 0.7, fontSize: 17, color: C.text2 });
    const shots = [
      ["real_v2_illustration.jpg", "Illustration", "drawn by the image model"],
      ["real_v2_equation_gd.jpg", "Equation", "typeset with KaTeX"],
      ["real_v4_comparison.jpg", "Comparison", "fixed two-column layout"],
    ];
    const g = 0.35, iw = (CW - 2 * g) / 3, ih = iw * 9 / 16, iy = 2.9;
    shots.forEach((sh, i) => {
      const x = M + i * (iw + g);
      img(s, sh[0], x, iy, iw, ih, sh[1] + " slide made by NextSlide", sh[1] + " example");
      T(s, [{ text: sh[1], options: { bold: true, breakLine: true } }, { text: sh[2], options: { color: C.text2, fontSize: 14 } }],
        { x, y: iy + ih + 0.18, w: iw, h: 0.7, fontSize: 17 });
    });
  }

  // 7. 시연
  {
    const s = S("SECTION", "System");
    title(s, ["Live ", "demo"]);
    T(s, "I'll speak Korean to the system and translate as I go. Watch for four things:", { x: M, y: 2.05, w: CW, h: 0.45, fontSize: 18, color: C.text2 });
    const rows = [
      [{ text: "I explain something  →  " }, { text: "nothing is made", options: { color: C.text2 } }],
      [{ text: "I ask for a slide  →  " }, { text: "the text appears first", options: { color: C.text2 } }],
      [{ text: "The picture forms step by step" }],
      [{ text: "I say “don't make it”  →  " }, { text: "nothing is made", options: { color: C.text2 } }],
    ];
    rows.forEach((r, i) => {
      const y = 2.75 + i * 0.78;
      badge(s, i + 1, M, y + 0.08, 0.42);
      T(s, r, { x: M + 0.7, y, w: CW - 0.7, h: 0.58, fontSize: 25, valign: "middle" });
    });
    dot(s, M, 6.3, 0.12);
    mono(s, "LIVE", { x: M + 0.24, y: 6.21, w: 0.7, h: 0.3, fontSize: 11 });
    wave(s, M + 1.0, 6.36, 0.36);
    T(s, "Backup: a recorded video of the same steps", { x: 3.2, y: 6.18, w: 6, h: 0.36, fontSize: 14, color: C.text2, valign: "middle" });
  }

  // 8. 수업 개념: 확산 모델이 그리는 과정
  pres.addSection({ title: "Experiments" });
  {
    const s = S("CONTENT", "Experiments");
    title(s, ["You can watch the ", "diffusion model", " draw"]);
    T(s, [{ text: "At every step the model predicts the finished image (" }, xhat, { text: "). I send that guess to the screen, so the audience watches the picture form." }],
      { x: M, y: 1.85, w: CW, h: 0.7, fontSize: 17, color: C.text2 });
    const sw = CW, sh = sw * 360 / 2632, sy = 2.85;
    img(s, "denoise_strip.jpg", M, sy, sw, sh, "The model's guess of the finished image at steps 4, 12 and 22 of 25, and the final image", "Denoising strip");
    const pw = sw * 664 / 2632;
    ["STEP 4 OF 25", "STEP 12", "STEP 22", "FINAL IMAGE"].forEach((l, i) =>
      mono(s, l, { x: M + i * pw, y: sy + sh + 0.15, w: pw - 0.2, h: 0.28, color: i === 3 ? C.accent1 : C.text2 }));
    T(s, "Stable Diffusion 1.5 with the DDIM sampler, 25 steps, about 12 s on my laptop. The guess is turned into colors with a fixed linear map instead of the full decoder, so showing it costs almost nothing.",
      { x: M, y: 5.25, w: CW, h: 0.8, fontSize: 15, color: C.text2 });
  }

  // 9. 실험 1: 속도
  {
    const s = S("CONTENT", "Experiments");
    kicker(s, "Experiment 1 of 3");
    title(s, ["Is it fast enough for a ", "live lecture", "?"]);
    s.addChart(pres.charts.BAR, [{ name: "Seconds per image", labels: ["Stable Diffusion 1.5 · 25 steps", "SD-Turbo · 2 steps"], values: [11.1, 0.68] }], {
      x: M, y: 1.95, w: 7.0, h: 2.9, ...chartBase(), barDir: "bar", title: "Seconds per image on my laptop (lower is better)",
      chartColors: [H.accent4, H.accent1], dataLabelPosition: "outEnd", dataLabelFormatCode: "0.0#\" s\"", dataLabelFontSize: 13,
      valAxisHidden: true, valGridLine: { style: "none" }, barGapWidthPct: 50, catAxisOrientation: "maxMin", catAxisLabelFontSize: 13,
      objectName: "Speed chart",
    });
    T(s, "SD-Turbo is a distilled version of Stable Diffusion that needs only 1–4 steps. It also matched the prompts slightly better (CLIP 28.2 vs 25.0).",
      { x: M, y: 5.15, w: 7.0, h: 0.8, fontSize: 15, color: C.text2 });
    const rx = 8.4, rw = W - M - rx;
    T(s, "0.7 s", { x: rx, y: 1.95, w: rw, h: 0.95, fontFace: SERIF, fontSize: 64, color: C.accent1, valign: "bottom" });
    T(s, "per image with SD-Turbo", { x: rx, y: 2.95, w: rw, h: 0.4, fontSize: 16 });
    T(s, "about 6 s", { x: rx, y: 3.75, w: rw, h: 0.85, fontFace: SERIF, fontSize: 48, valign: "bottom" });
    T(s, [{ text: "from my sentence to a finished slide", options: { breakLine: true } }, { text: "one test run", options: { fontSize: 13, color: C.text2 } }], { x: rx, y: 4.65, w: rw, h: 0.7, fontSize: 16 });
  }

  // 10. 실험 2: 가이던스
  {
    const s = S("CONTENT", "Experiments");
    kicker(s, "Experiment 2 of 3");
    title(s, ["What does the ", "guidance scale", " change?"]);
    const g = 0.2, iw = (CW - 3 * g) / 4, ih = iw * 9 / 16, iy = 1.95;
    [["cfg_1.jpg", "1"], ["cfg_3.jpg", "3"], ["cfg_7_5.jpg", "7.5"], ["cfg_12.jpg", "12"]].forEach(([f, l], i) => {
      const x = M + i * (iw + g);
      img(s, f, x, iy, iw, ih, "Stable Diffusion 1.5 image at guidance scale " + l, "Guidance " + l + " image");
      mono(s, "GUIDANCE " + l, { x, y: iy + ih + 0.1, w: iw, h: 0.26, color: C.text2 });
    });
    T(s, "Same prompt (a hiker walking down a foggy valley) and same seed. Only the guidance scale changes.",
      { x: M, y: iy + ih + 0.45, w: CW, h: 0.35, fontSize: 14, color: C.text2 });
    const labels = ["1", "3", "5", "7.5", "12"];
    const mini = (ttl, min, max, fmt, color) => ({
      ...chartBase(), title: ttl, chartColors: [color], lineSize: 2, lineDataSymbol: "circle", lineDataSymbolSize: 7,
      dataLabelPosition: "t", dataLabelFontSize: 10, valAxisMinVal: min, valAxisMaxVal: max, dataLabelFormatCode: fmt, valAxisLabelFormatCode: fmt,
      valAxisLabelFontSize: 10, catAxisLabelFontSize: 11,
    });
    const cw = (CW - 0.4) / 2, cy = 4.3, ch = 2.45;
    s.addChart(pres.charts.LINE, [{ name: "Prompt match", labels, values: [21.5, 24.6, 25.7, 25.0, 25.6] }],
      { x: M, y: cy, w: cw, h: ch, ...mini("Match with the prompt (CLIP): rises, then levels off", 20, 27, "0.0", H.accent1), objectName: "Guidance vs prompt match" });
    s.addChart(pres.charts.LINE, [{ name: "Variety", labels, values: [0.269, 0.209, 0.213, 0.182, 0.177] }],
      { x: M + cw + 0.4, y: cy, w: cw, h: ch, ...mini("Variety between seeds: keeps falling", 0.15, 0.28, "0.00", H.accent2), objectName: "Guidance vs variety" });
  }

  // 11. 실험 3: 강의 맥락 (핵심)
  {
    const s = S("CONTENT", "Experiments");
    kicker(s, "Experiment 3 of 3");
    title(s, ["Does the lecture context ", "actually help", "?"]);
    T(s, [
      { text: "42 scenarios, 30 based on this course's lectures", options: { bullet: true, breakLine: true } },
      { text: "A: request only.  B: request + recent speech + current slide", options: { bullet: true, breakLine: true } },
      { text: "The intended scene was committed to git before any image was made", options: { bullet: true } },
    ], { x: M, y: 1.9, w: 5.1, h: 1.5, fontSize: 15, color: C.text2, paraSpaceAfter: 6 });
    T(s, "+2.1", { x: M, y: 3.5, w: 2.1, h: 1.05, fontFace: SERIF, fontSize: 66, color: C.accent1, valign: "middle" });
    T(s, "points closer to the intended scene on average (CLIP, p\u00A0=\u00A00.010)", { x: M + 2.2, y: 3.5, w: 2.9, h: 1.05, fontSize: 15, valign: "middle" });
    T(s, [{ text: "7 " }, { text: "→", options: { fontFace: "+mn-lt" } }, { text: " 0" }], { x: M, y: 4.85, w: 2.1, h: 1.0, fontFace: SERIF, fontSize: 48, valign: "middle" });
    T(s, "times the system had to ask what I meant (out of 42)", { x: M + 2.2, y: 4.85, w: 2.9, h: 1.0, fontSize: 15, valign: "middle" });
    const ids = Object.keys(X4_DIFF).sort((a, b) => X4_DIFF[b] - X4_DIFF[a]);
    const cx = 6.25, cwid = W - M - cx;
    s.addChart(pres.charts.BAR, [{ name: "B minus A", labels: ids, values: ids.map((k) => X4_DIFF[k]) }], {
      x: cx, y: 1.85, w: cwid, h: 4.4, ...chartBase(), barDir: "col", title: "Each bar is one scenario: how much closer B is than A",
      chartColors: [H.accent1], invertedColors: [H.accent4], showValue: false, catAxisHidden: true,
      valAxisMinVal: -6, valAxisMaxVal: 12, valAxisMajorUnit: 3, valAxisLabelFormatCode: "+0;-0;0", barGapWidthPct: 40,
      objectName: "X4 per-scenario difference",
    });
    T(s, "17 of the 28 scenarios where both versions drew a picture moved closer.", { x: cx, y: 6.3, w: cwid, h: 0.4, fontSize: 13, color: C.text2 });
  }

  // 12. 한계
  pres.addSection({ title: "Closing" });
  {
    const s = S("CONTENT", "Closing");
    title(s, ["What still goes wrong"]);
    const iw = 5.3, ih = iw * 9 / 16;
    img(s, "fake_text.jpg", M, 1.95, iw, ih, "SD-Turbo image with fake text: lines on the papers look like writing but are meaningless", "Fake text example");
    T(s, "SD-Turbo, scene “a student peeking at the answer key”: the lines on the papers are fake text.", { x: M, y: 1.95 + ih + 0.14, w: iw, h: 0.6, fontSize: 13, color: C.text2 });
    const rx = 6.55, rw = W - M - rx;
    const items = [
      ["Fake text in pictures", "About 9 of 34 images. Telling the planner to describe blank surfaces didn't reduce it."],
      ["Only one automatic judge", "CLIP scores prompt match. It barely reacted to broken DDPM images."],
      ["My own test set", "I wrote the scenarios and intended scenes myself, with an AI assistant."],
    ];
    items.forEach((it, i) => {
      const y = 1.95 + i * 1.3;
      T(s, it[0], { x: rx, y, w: rw, h: 0.42, fontSize: 19, bold: true });
      T(s, it[1], { x: rx, y: y + 0.44, w: rw, h: 0.75, fontSize: 15, color: C.text2 });
    });
    T(s, "Next: a blind evaluation by people", { x: rx, y: 5.95, w: rw, h: 0.45, fontSize: 18, bold: true, color: C.accent1 });
  }

  // 13. 정리
  {
    const s = S("SECTION", "Closing");
    title(s, ["To sum up"]);
    const lines = [
      ["Say what the next slide should show, and it is ready in a few seconds.", C.text1],
      ["Using the lecture as context brings the picture closer to what you meant.", C.text1],
      ["The weak spot is still the image model.", C.text2],
    ];
    lines.forEach((l, i) => T(s, l[0], { x: M, y: 2.25 + i * 0.95, w: CW, h: 0.8, fontFace: SERIF, fontSize: 28, color: l[1] }));
    T(s, [{ text: "Thank you  ·  " }, { text: "Questions?", options: { italic: true, color: C.accent1 } }],
      { x: M, y: 5.6, w: 8, h: 0.8, fontFace: SERIF, fontSize: 38 });
  }

  // 부록 1: 기존 도구 비교
  pres.addSection({ title: "Backup" });
  {
    const s = S("CONTENT", "Backup");
    kicker(s, "Backup");
    title(s, ["Compared with live-staging tools"]);
    const hdr = (t, hi) => ({ text: t, options: { fontFace: MONO, fontSize: 11, charSpacing: 1, color: hi ? C.accent1 : C.text2, fill: { color: C.background2 } } });
    const hi = (t) => ({ text: t, options: { bold: true, color: C.accent1 } });
    const lab = (t) => ({ text: t, options: { bold: true } });
    s.addTable([
      [hdr(""), hdr("LIVE-STAGING TOOLS (E.G. ZEROPREP)"), hdr("NEXTSLIDE", true)],
      [lab("What triggers a slide"), "A realtime model interprets every utterance", hi("Only explicit requests (rule-based detector)")],
      [lab("Who sees it first"), "The audience, immediately", hi("The presenter; the audience sees it when I advance")],
      [lab("Slide forms"), "Cards, metrics, diagrams", hi("Illustration, equation, comparison, table, chart")],
      [lab("Context used"), "The current utterance", hi("Request + last 90 s of speech + current slide")],
    ], {
      x: M, y: 1.95, w: CW, colW: [2.6, 4.4, CW - 7.0], fontSize: 15, color: C.text1,
      border: { type: "solid", pt: 0.75, color: H.accent3 }, valign: "middle", rowH: [0.55, 0.8, 0.8, 0.8, 0.8], margin: 0.12,
      objectName: "Prior work comparison",
    });
    T(s, "ZeroPrep: github.com/ramsrigouthamg/zeroprep (README and app code read on 2026-11-05)", { x: M, y: 6.25, w: CW, h: 0.35, fontSize: 12, color: C.text2 });
  }

  // 부록 2: 시스템 수치
  {
    const s = S("CONTENT", "Backup");
    kicker(s, "Backup");
    title(s, ["System numbers"]);
    const cw = (CW - 0.5) / 2;
    T(s, "56 / 60", { x: M, y: 1.85, w: cw, h: 0.95, fontFace: SERIF, fontSize: 54, valign: "bottom" });
    T(s, "correct on the request-detector test set", { x: M, y: 2.85, w: cw, h: 0.4, fontSize: 16, bold: true });
    T(s, "0 missed requests · 1 slide made when it shouldn't have been · 3 needless “which topic?” questions. I wrote the test set myself.",
      { x: M, y: 3.25, w: cw, h: 0.8, fontSize: 14, color: C.text2 });
    T(s, "112", { x: M + cw + 0.5, y: 1.85, w: cw, h: 0.95, fontFace: SERIF, fontSize: 54, valign: "bottom" });
    T(s, "automated backend tests", { x: M + cw + 0.5, y: 2.85, w: cw, h: 0.4, fontSize: 16, bold: true });
    T(s, "Run with mock providers, so they make no API calls.", { x: M + cw + 0.5, y: 3.25, w: cw, h: 0.8, fontSize: 14, color: C.text2 });
    const hdr = (t) => ({ text: t, options: { fontFace: MONO, fontSize: 11, charSpacing: 1, color: C.text2, fill: { color: C.background2 } } });
    s.addTable([
      [hdr("END TO END (ONE RUN EACH)"), hdr("TEXT READY"), hdr("IMAGE"), hdr("SLIDE READY")],
      [{ text: "Local SD-Turbo", options: { bold: true } }, "5.0 s", "1.2 s", { text: "6.2 s", options: { bold: true, color: C.accent1 } }],
      [{ text: "gpt-image-2 API", options: { bold: true } }, "5.7 s", "14.3 s", { text: "20.0 s", options: { bold: true } }],
    ], {
      x: M, y: 4.35, w: CW, colW: [4.4, 2.45, 2.45, CW - 9.3], fontSize: 15, color: C.text1,
      border: { type: "solid", pt: 0.75, color: H.accent3 }, valign: "middle", rowH: [0.5, 0.55, 0.55], margin: 0.12,
      objectName: "Latency table",
    });
    T(s, "Cost: the planner LLM is about $0.0002–0.0004 per slide; an API image is about $0.0045; local images are free.", { x: M, y: 6.15, w: CW, h: 0.4, fontSize: 13, color: C.text2 });
  }

  // 부록 3: 측정 방법
  {
    const s = S("CONTENT", "Backup");
    kicker(s, "Backup");
    title(s, ["How the experiments were measured"]);
    const b = (t, last) => ({ text: t, options: { bullet: true, breakLine: !last } });
    T(s, [
      b("Score: cosine similarity from CLIP ViT-B/32 × 100, a different model from the generators' text encoders"),
      b("X1–X3: 12 lecture scenes × 2 fixed seeds, one setting changed at a time, 95% bootstrap confidence intervals"),
      b("X4: 28 paired scenarios, paired permutation test; intended scenes committed before any image was made"),
      b("X1: DDPM at 10 steps broke shapes and DDIM didn't, yet CLIP gave 25.5 vs 25.1"),
      b("X3 caveat: SD-Turbo is based on SD 2.1 with a larger text encoder, so the gain is not distillation alone"),
      b("Bug found by the experiments: prompts over CLIP's 77-token limit lost their style words (18 of 18); fixed with token-aware trimming"),
      b("Tried and dropped: CLIP as a fake-text detector (only 1 of its top 6 picks had text)", true),
    ], { x: M, y: 1.9, w: CW, h: 4.7, fontSize: 16, paraSpaceAfter: 9 });
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
  const main = SCRIPT.filter((s) => !s.backup);
  const total = main.reduce((a, s) => { const [m, sec] = s.t.split(":").map(Number); return a + m * 60 + sec; }, 0);
  const demoNo = SCRIPT.findIndex((s) => s.title === "Live demo") + 1;
  const L = [];
  L.push("# NextSlide 발표 대본 (영어 / 한국어)", "");
  L.push(`발표 파일: [NextSlide_final.pptx](NextSlide_final.pptx). 슬라이드 노트에도 같은 대본이 들어 있습니다. 이 파일과 노트는 \`build_deck.js\`가 함께 만듭니다.`, "");
  L.push(`- 예상 시간: 약 ${Math.floor(total / 60)}분 ${total % 60}초(본문 ${main.length}장, 시연 2분 포함). 부록 ${SCRIPT.length - main.length}장은 질문이 나올 때만 씁니다.`);
  L.push(`- 시연을 발표 끝에 하려면 PowerPoint에서 ${demoNo}번 슬라이드(Live demo)를 ${main.length}번(To sum up) 앞으로 옮기면 됩니다. 대본 순서도 같이 옮깁니다.`);
  L.push("- [name] 자리에 이름을 넣어 말하세요. 표지에는 이름이 없으니 필요하면 직접 추가하세요.");
  L.push("- 글꼴: 덱은 Instrument Serif·Instrument Sans·IBM Plex Mono를 씁니다(OFL). 발표할 컴퓨터에 `fonts/` 폴더의 글꼴을 먼저 설치하세요. 없으면 PowerPoint가 다른 글꼴로 바꿔 보여 줍니다.", "");
  SCRIPT.forEach((s, i) => {
    if (s.backup && !SCRIPT[i - 1].backup) L.push("## 부록 (질문 대비)", "");
    L.push(`${s.backup ? "###" : "##"} ${i + 1}. ${s.title}${s.backup ? "" : ` (${s.t})`}`, "", `**EN** ${s.en}`, "", `**KO** ${s.ko}`, "");
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
