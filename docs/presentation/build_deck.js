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
const lu = require("react-icons/lu");

const HERE = __dirname;
const A = (f) => path.join(HERE, "assets", f);
const OUT = path.join(HERE, "NextSlide_final.pptx");
const APPLY_THEME = process.env.APPLY_THEME_JS; // pptx 스킬의 scripts/apply_theme.js 경로 (선택)

// 디자인: 사용자의 IR 자료 스타일(밝은 회색 바탕 + 흰 카드, 왼쪽 라벨 블록이 있는 핵심 메시지 띠,
// 대괄호 소제목, 파랑 #285592 · 빨강 #DD5C47 · 남색 #183257, 나눔스퀘어 계열 글꼴)을 따른다.
// 글꼴: 나눔스퀘어 네오(NAVER). Light는 TTF, Bold/ExtraBold/Heavy는 OTF 패밀리 이름으로 지정한다.
const F = {
  L: "NanumSquare Neo Light",
  B: "NanumSquare Neo OTF Bold",
  EB: "NanumSquare Neo OTF ExtraBold",
  H: "NanumSquare Neo OTF Heavy",
  MATH: "Cambria Math", // x̂₀ (나눔스퀘어 네오에는 결합 기호 ̂ 이 없음)
};
const THEME = {
  name: "NextSlide IR",
  headFontFace: F.EB,
  bodyFontFace: F.B,
  colors: {
    dk1: "404040", // 본문 글자
    lt1: "FFFFFF",
    dk2: "285592", // 파랑 글자(소제목)
    lt2: "F5F5F5", // 바탕 회색
    accent1: "2D66AD", // 파랑 블록
    accent2: "DD5C47", // 강조 빨강
    accent3: "183257", // 남색
    accent4: "6494CB", // 연한 파랑
    accent5: "A7A7A7", // 회색
    accent6: "C8DBF9", // 아주 연한 파랑
    hlink: "285592", folHlink: "183257",
  },
};
const H = THEME.colors; // hex-only 옵션(차트, 그림자)용
const TINT = { blue: "EEF3FA", red: "FDECEA", bar: "F2F2F2", line: "DDDDDD", sub: "535353", dark: "4A4A4A" };

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

// ───────────────────────── 아이콘 ─────────────────────────
async function icon(name, color, size = 256) {
  const Comp = lu[name];
  if (!Comp) throw new Error(`unknown icon ${name}`);
  const svg = ReactDOMServer.renderToStaticMarkup(React.createElement(Comp, { color: "#" + color, size: String(size), strokeWidth: 2 }));
  const buf = await sharp(Buffer.from(svg)).resize(size, size).png().toBuffer();
  return "image/png;base64," + buf.toString("base64");
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
  const pres = new pptxgen();
  pres.layout = "LAYOUT_WIDE"; // 13.333 x 7.5 (IR 자료와 같은 크기)
  pres.title = "NextSlide: Speak the Next Slide";
  pres.subject = "Generative AI final project";
  pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
  const C = pres.SchemeColor;
  const W = 13.333, HGT = 7.5;
  const X0 = 0.87; // 왼쪽 기준선(IR: 머리말·라벨 블록·카드가 모두 이 선에서 시작)

  // ── 레이아웃 ──
  // 로고: 겹친 두 장(뒤 연한 파랑, 앞 파랑) + NEXT/SLIDE 두 줄
  const logoObjs = (x, y, s, white) => [
    { rect: { x, y: y + 0.04 * s, w: 0.36 * s, h: 0.27 * s, fill: { color: white ? "FFFFFF" : H.accent4, transparency: white ? 45 : 0 } } },
    { rect: { x: x + 0.09 * s, y: y + 0.13 * s, w: 0.36 * s, h: 0.27 * s, fill: { color: white ? "FFFFFF" : H.dk2 } } },
    { text: { text: "NEXT\nSLIDE", options: { x: x + 0.53 * s, y: y - 0.02 * s, w: 1.4 * s, h: 0.5 * s, fontFace: F.H, fontSize: 11 * s, color: white ? "FFFFFF" : H.accent3, lineSpacingMultiple: 0.85, margin: 0, valign: "middle" } } },
  ];
  pres.defineSlideMaster({
    title: "COVER",
    background: { color: H.lt2 },
    objects: [{ rect: { x: 0, y: 0, w: W, h: 6.05, fill: { color: H.accent1 } } }],
  });
  pres.defineSlideMaster({
    title: "CONTENT",
    background: { color: H.lt2 },
    objects: [
      { rect: { x: X0, y: 0.68, w: 0.36, h: 0.035, fill: { color: H.dk2 } } }, // 머리말 아래 짧은 파랑 막대
      ...logoObjs(11.62, 0.42, 1, false),
      { text: { text: "NextSlide · Speak the next slide", options: { x: 0.2, y: 3.2, w: 2.6, h: 0.22, rotate: 270, fontFace: F.L, fontSize: 8, color: H.accent5, margin: 0 } } },
      { rect: { x: 0.495, y: 5.15, w: 0.01, h: 2.4, fill: { color: TINT.line } } },
      { text: { text: "Speak the next slide · NEXTSLIDE  |", options: { x: W - 4.6, y: 7.16, w: 3.82, h: 0.22, fontFace: F.L, fontSize: 8, color: H.accent5, align: "right", margin: 0 } } },
      { placeholder: { options: { name: "title", type: "title", x: X0, y: 0.82, w: 10.4, h: 0.45, fontFace: F.EB, fontSize: 20, color: C.text1, valign: "middle", align: "left", margin: 0 }, text: "" } },
    ],
    slideNumber: { x: W - 0.76, y: 7.16, w: 0.5, h: 0.22, fontFace: F.EB, fontSize: 8, color: C.text1, align: "left", margin: 0 },
  });
  pres.defineSlideMaster({
    title: "ENDING",
    background: { color: H.lt2 },
    objects: [
      { rect: { x: 0, y: 0, w: W, h: 4.3, fill: { color: TINT.dark } } },
      { rect: { x: 0, y: 4.3, w: W, h: 1.5, fill: { color: H.accent1 } } },
    ],
  });

  // ── 공통 요소 ──
  const T = (s, t, o) => s.addText(t, { isTextBox: true, margin: 0, fontFace: F.B, fontSize: 14, color: C.text1, valign: "top", ...o });
  const shadow = () => ({ type: "outer", color: "000000", blur: 9, offset: 2, angle: 90, opacity: 0.12 });
  const rect = (s, x, y, w, h, fill, name, o = {}) => s.addShape(pres.shapes.RECTANGLE, { x, y, w, h, fill: { color: fill }, line: { type: "none" }, objectName: name, ...o });
  const dotted = (s, x, y, w, name = "Dotted rule") => s.addShape(pres.shapes.LINE, { x, y, w, h: 0, line: { color: H.accent5, width: 0.75, dashType: "sysDot" }, objectName: name });
  const frame = (s, x, y, w, h, name, color = TINT.line, width = 0.75) =>
    s.addShape(pres.shapes.RECTANGLE, { x, y, w, h, fill: { type: "none" }, line: { color, width }, objectName: name });
  const img = (s, file, x, y, w, h, alt, name) => {
    s.addImage({ path: A(file), x, y, w, h, altText: alt, objectName: name });
    frame(s, x, y, w, h, name + " frame");
  };
  const xhat = (o = {}) => ({ text: "x̂₀", options: { fontFace: F.MATH, ...o } });

  // 머리말: "01 | Problem" + 슬라이드 제목(플레이스홀더)
  const head = (s, crumb, title) => {
    T(s, crumb, { x: X0, y: 0.36, w: 6, h: 0.28, fontFace: F.L, fontSize: 12, color: TINT.sub, objectName: "Section breadcrumb" });
    s.addText(title, { placeholder: "title" });
  };
  // 핵심 메시지 띠: 왼쪽 라벨 블록(꺾쇠) + 오른쪽 흰 띠에 한두 줄
  const banner = (s, label, rows, fill = H.accent1) => {
    rect(s, 2.36, 1.3, W - 2.36 + 0.05, 0.98, "FFFFFF", "Key message bar", { shadow: shadow() });
    rect(s, X0, 1.3, 1.49, 0.98, fill, "Key message label");
    s.addShape(pres.shapes.ISOSCELES_TRIANGLE, { x: 2.3, y: 1.72, w: 0.26, h: 0.14, rotate: 90, fill: { color: fill }, line: { type: "none" }, objectName: "Label notch" });
    T(s, label, { x: X0, y: 1.3, w: 1.49, h: 0.98, fontFace: F.EB, fontSize: 17, color: "FFFFFF", align: "center", valign: "middle" });
    // 띠 오른쪽의 흐린 로고(IR 자료의 워터마크 자리)
    rect(s, 12.15, 1.53, 0.42, 0.31, H.accent6, "Banner mark back", { fill: { color: H.accent6, transparency: 35 } });
    rect(s, 12.26, 1.64, 0.42, 0.31, H.accent6, "Banner mark front", { fill: { color: H.accent4, transparency: 55 } });
    const run = (r) => [
      ...(Array.isArray(r[0]) ? r[0] : [{ text: r[0] }]).map((x) => ({ text: x.text, options: { fontFace: F.EB, color: C.text1, ...(x.options || {}) } })),
      { text: "  |  ", options: { fontFace: F.EB, color: C.text1 } },
      { text: r[1], options: { fontFace: F.L, color: TINT.sub } },
    ];
    if (rows.length === 1) {
      T(s, run(rows[0]), { x: 2.75, y: 1.3, w: 9.25, h: 0.98, fontSize: 14, valign: "middle" });
    } else {
      T(s, run(rows[0]), { x: 2.75, y: 1.32, w: 9.25, h: 0.46, fontSize: 14, valign: "middle" });
      dotted(s, 2.75, 1.79, 9.1);
      T(s, run(rows[1]), { x: 2.75, y: 1.8, w: 9.25, h: 0.46, fontSize: 14, valign: "middle" });
    }
  };
  // 흰 카드(왼쪽 위만 둥글게 보이도록 오른쪽·아래로 넘긴다)
  const card = (s) => s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: X0, y: 2.45, w: W - X0 + 0.4, h: 5.5, rectRadius: 0.22, fill: { color: "FFFFFF" }, line: { type: "none" }, shadow: shadow(), objectName: "Content card" });
  // 대괄호 소제목: [ 텍스트 ]
  const bracket = (s, x, y, w, text, color = C.text2) => {
    const bw = 0.045, arm = 0.13, bh = 0.44;
    rect(s, x, y, bw, bh, H.accent1, "Bracket");
    rect(s, x, y, arm, bw, H.accent1, "Bracket");
    rect(s, x, y + bh - bw, arm, bw, H.accent1, "Bracket");
    rect(s, x + w - bw, y, bw, bh, H.accent3, "Bracket");
    rect(s, x + w - arm, y, arm, bw, H.accent3, "Bracket");
    rect(s, x + w - arm, y + bh - bw, arm, bw, H.accent3, "Bracket");
    rect(s, x + 0.17, y + 0.04, w - 0.34, bh - 0.08, TINT.bar, "Subheading bar");
    T(s, text, { x: x + 0.17, y: y + 0.04, w: w - 0.34, h: bh - 0.08, fontFace: F.EB, fontSize: 14.5, color, align: "center", valign: "middle", objectName: "Subheading" });
  };
  const iconCircle = async (s, name, x, y, d, red = false) => {
    s.addShape(pres.shapes.OVAL, { x, y, w: d, h: d, fill: { color: red ? TINT.red : TINT.blue }, line: { color: red ? H.accent2 : H.accent4, width: 1 }, objectName: name + " circle" });
    const p = d * 0.27;
    s.addImage({ data: await icon(name, red ? H.accent2 : H.dk2), x: x + p, y: y + p, w: d - 2 * p, h: d - 2 * p, altText: name.replace(/^Lu/, "") + " icon", objectName: name + " icon" });
  };
  const chev = (s, x, y, w = 0.3, h = 0.75) =>
    s.addShape(pres.shapes.CHEVRON, { x, y, w, h, fill: { color: "E4E4E4" }, line: { type: "none" }, shadow: shadow(), objectName: "Flow chevron" });
  const badge = (s, n, x, y, d = 0.34, fill = H.accent1) => {
    s.addShape(pres.shapes.OVAL, { x, y, w: d, h: d, fill: { color: fill }, line: { type: "none" }, objectName: "Badge " + n });
    T(s, String(n), { x, y, w: d, h: d, fontFace: F.EB, fontSize: 12, color: "FFFFFF", align: "center", valign: "middle", objectName: "Badge " + n + " number" });
  };
  const chartBase = () => ({
    showTitle: false, catAxisLabelColor: TINT.sub, valAxisLabelColor: H.accent5, catAxisLabelFontSize: 12, valAxisLabelFontSize: 10,
    catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt",
    valGridLine: { color: "E6E6E6", size: 0.75 }, catGridLine: { style: "none" },
    showLegend: false, showValue: true, dataLabelColor: H.dk1, dataLabelFontSize: 12, dataLabelFontFace: "+mj-lt",
    catAxisLineShow: true, catAxisLineColor: "BFBFBF", valAxisLineShow: false,
  });

  let n = 0;
  const S = (layout, section) => {
    const s = pres.addSlide({ masterName: layout, sectionTitle: section });
    s.addNotes(notesFor(n));
    n += 1;
    return s;
  };
  // 세 칸(대괄호) 배치용 좌표
  const COL3 = [1.32, 5.37, 9.42], CW3 = 3.45;
  const COL2 = [1.32, 7.21], CW2 = 5.62;

  // 1. 표지
  pres.addSection({ title: "Opening" });
  {
    const s = S("COVER", "Opening");
    s.addShape(pres.shapes.OVAL, { x: 8.0, y: 0.35, w: 5.0, h: 5.0, fill: { color: "FFFFFF", transparency: 90 }, line: { type: "none" }, objectName: "Decor blob" });
    s.addShape(pres.shapes.OVAL, { x: 11.0, y: 3.4, w: 2.3, h: 2.3, fill: { color: "FFFFFF", transparency: 85 }, line: { type: "none" }, objectName: "Decor blob" });
    rect(s, 0.45, 4.3, 1.75, 1.3, "FFFFFF", "Decor mark", { fill: { color: "FFFFFF", transparency: 92 } });
    rect(s, 0.9, 4.75, 1.75, 1.3, "FFFFFF", "Decor mark", { fill: { color: "FFFFFF", transparency: 90 } });
    T(s, "Generative AI  ·  Final project", { x: 0.72, y: 0.95, w: 6.5, h: 0.4, fontFace: F.L, fontSize: 15, color: "DCE6F4" });
    T(s, "The lecturer keeps talking,", { x: 0.72, y: 1.55, w: 6.6, h: 0.7, fontFace: F.L, fontSize: 34, color: "FFFFFF" });
    T(s, [{ text: "the next slide", options: { fontFace: F.H } }, { text: " gets made", options: { fontFace: F.L } }], { x: 0.72, y: 2.25, w: 6.6, h: 0.75, fontSize: 36, color: "FFFFFF" });
    // 로고(크게, 흰색)
    rect(s, 0.75, 3.42, 0.62, 0.46, "FFFFFF", "Logo back", { fill: { color: "FFFFFF", transparency: 45 } });
    rect(s, 0.9, 3.57, 0.62, 0.46, "FFFFFF", "Logo front");
    T(s, "NEXT\nSLIDE", { x: 1.7, y: 3.3, w: 3, h: 0.85, fontFace: F.H, fontSize: 24, color: "FFFFFF", lineSpacingMultiple: 0.85, valign: "middle" });
    // 실제로 만든 장을 기기 화면처럼
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 7.45, y: 1.2, w: 5.25, h: 3.15, rectRadius: 0.16, fill: { color: H.accent3 }, line: { type: "none" }, shadow: { type: "outer", color: "000000", blur: 14, offset: 4, angle: 90, opacity: 0.25 }, objectName: "Device" });
    s.addImage({ path: A("real_v2_illustration.jpg"), x: 7.6, y: 1.35, w: 4.95, h: 2.785, altText: "A slide made by NextSlide: a learning rate that is too large, shown as a hiker overshooting the valley", objectName: "Generated slide example" });
    T(s, "A slide NextSlide made: a learning rate that is too large, shown as a hiker.", { x: 7.45, y: 4.5, w: 5.25, h: 0.5, fontFace: F.L, fontSize: 12, color: "DCE6F4" });
    T(s, [{ text: "Generative AI", options: { fontFace: F.EB } }, { text: "  |  Final project", options: { fontFace: F.L } }], { x: 0.72, y: 6.55, w: 6, h: 0.4, fontSize: 15, valign: "middle" });
    T(s, "Fall 2026", { x: W - 3.6, y: 6.55, w: 2.9, h: 0.4, fontFace: F.L, fontSize: 13, color: TINT.sub, align: "right", valign: "middle" });
  }

  // 2. 문제
  pres.addSection({ title: "Idea" });
  {
    const s = S("CONTENT", "Idea");
    head(s, "01  |  Problem", "1. Ideas that come up mid-lecture have no slide");
    banner(s, "Problem", [
      ["Improvised explanations", "the best analogy often comes up in the middle of a lecture"],
      ["Broken flow", "making a slide right then means stopping the lecture"],
    ], TINT.dark);
    card(s);
    bracket(s, COL2[0], 2.7, CW2, "A lecture, over time");
    bracket(s, COL2[1], 2.7, CW2, "What happens in class");
    const ly = 4.55;
    T(s, "Prepared before class", { x: 1.5, y: 3.55, w: 3, h: 0.3, fontFace: F.L, fontSize: 12, color: TINT.sub });
    s.addShape(pres.shapes.LINE, { x: 1.5, y: ly, w: 5.3, h: 0, line: { color: H.accent5, width: 1.25, endArrowType: "triangle" }, objectName: "Lecture timeline" });
    const bx = [1.5, 2.85, 4.2, 5.55], bw = 1.15, by = ly + 0.3, bh = 0.72;
    ["Slide 1", "Slide 2", "", "Slide 3"].forEach((l, i) => {
      if (!l) return;
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: bx[i], y: by, w: bw, h: bh, rectRadius: 0.06, fill: { color: TINT.blue }, line: { color: H.accent6, width: 0.75 }, objectName: l });
      T(s, l, { x: bx[i], y: by, w: bw, h: bh, fontFace: F.EB, fontSize: 13, color: C.text2, align: "center", valign: "middle" });
    });
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: bx[2], y: by, w: bw, h: bh, rectRadius: 0.06, fill: { color: "FFFFFF" }, line: { color: H.accent2, width: 1.25, dashType: "dash" }, objectName: "Missing slide" });
    T(s, "No slide", { x: bx[2], y: by, w: bw, h: bh, fontFace: F.EB, fontSize: 13, color: C.accent2, align: "center", valign: "middle" });
    const mx = bx[2] + bw / 2;
    s.addShape(pres.shapes.OVAL, { x: mx - 0.09, y: ly - 0.09, w: 0.18, h: 0.18, fill: { color: H.accent2 }, line: { type: "none" }, objectName: "Moment dot" });
    T(s, "An analogy comes up", { x: mx - 1.1, y: ly - 0.5, w: 2.2, h: 0.3, fontFace: F.EB, fontSize: 12.5, color: C.accent2, align: "center" });
    // 말풍선
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 7.55, y: 3.4, w: 4.95, h: 1.45, rectRadius: 0.22, fill: { color: "FFFFFF" }, line: { color: H.accent3, width: 1.75 }, objectName: "Speech bubble" });
    s.addShape(pres.shapes.ISOSCELES_TRIANGLE, { x: 8.35, y: 4.83, w: 0.3, h: 0.24, flipV: true, fill: { color: H.accent3 }, line: { type: "none" }, objectName: "Bubble tail" });
    T(s, [
      { text: "“Overfitting is like a student who", options: { breakLine: true } },
      { text: "memorized the answers", options: { color: "FFFFFF", highlight: H.accent3 } },
      { text: " to old exams.”" },
    ], { x: 7.75, y: 3.4, w: 4.55, h: 1.45, fontSize: 16, align: "center", valign: "middle", lineSpacingMultiple: 1.15 });
    await iconCircle(s, "LuUser", 8.05, 5.3, 0.8);
    T(s, "The lecturer, mid-lecture", { x: 9.05, y: 5.36, w: 3.6, h: 0.35, fontFace: F.EB, fontSize: 14 });
    T(s, "…and the deck has no slide for it.", { x: 9.05, y: 5.72, w: 3.6, h: 0.35, fontFace: F.L, fontSize: 13, color: TINT.sub });
  }

  // 3. 해결 장면
  {
    const s = S("CONTENT", "Idea");
    head(s, "01  |  Problem", "2. With NextSlide, I just say it");
    banner(s, "Solution", [["Just say it", "say what the next slide should show; it is made while I keep talking"]]);
    card(s);
    ["What I said", "Text first, in my preview", "The finished slide"].forEach((t, i) => bracket(s, COL3[i], 2.7, CW3, t));
    chev(s, 4.9, 4.15); chev(s, 8.95, 4.15);
    // 말한 문장(말풍선)
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 1.45, y: 3.45, w: 3.2, h: 1.95, rectRadius: 0.2, fill: { color: "FFFFFF" }, line: { color: H.accent3, width: 1.75 }, objectName: "Speech bubble" });
    s.addShape(pres.shapes.ISOSCELES_TRIANGLE, { x: 2.0, y: 5.38, w: 0.28, h: 0.22, flipV: true, fill: { color: H.accent3 }, line: { type: "none" }, objectName: "Bubble tail" });
    T(s, [
      { text: "다음 슬라이드에서는", options: { breakLine: true } },
      { text: "과적합을 시험 문제를 외운", options: { breakLine: true } },
      { text: "학생에 비유해서 설명하겠습니다." },
    ], { x: 1.55, y: 3.45, w: 3.0, h: 1.95, fontFace: F.EB, fontSize: 14.5, align: "center", valign: "middle", lineSpacingMultiple: 1.2 });
    T(s, "“In the next slide, I'll explain overfitting by comparing it to a student who memorized the exam questions.”",
      { x: 1.45, y: 5.75, w: 3.2, h: 1.0, fontFace: F.L, fontSize: 11.5, color: TINT.sub, align: "center" });
    // 미리보기(글 먼저)
    const pw = 2.95, ph = pw * 672 / 796;
    img(s, "preview_text_first.jpg", COL3[1] + (CW3 - pw) / 2, 3.35, pw, ph, "Presenter preview: the title and points are ready while the image is still being generated", "Preview text first");
    T(s, "Title and points appear first; the picture follows.", { x: COL3[1], y: 6.0, w: CW3, h: 0.6, fontFace: F.L, fontSize: 11.5, color: TINT.sub, align: "center" });
    // 완성된 장
    const fw = 3.35, fh = fw * 9 / 16;
    img(s, "scene_overfit.jpg", COL3[2] + (CW3 - fw) / 2, 3.75, fw, fh, "The finished slide: overfitting explained as a student who memorized exam questions, with a title, three points and a picture", "Finished slide");
    T(s, "Real output from a test run with real APIs.", { x: COL3[2], y: 6.0, w: CW3, h: 0.6, fontFace: F.L, fontSize: 11.5, color: TINT.sub, align: "center" });
  }

  // 4. 동작
  pres.addSection({ title: "System" });
  {
    const s = S("CONTENT", "System");
    head(s, "02  |  How it works", "1. Three steps while I keep talking");
    banner(s, "System", [
      ["Listen → Decide → Make", "speech-to-text, a request detector, an LLM and an image model"],
      ["Presenter first", "the audience sees the new slide only when I advance"],
    ]);
    card(s);
    bracket(s, 1.32, 2.7, 4.75, "Three steps");
    bracket(s, 6.35, 2.7, 6.5, "My presenter screen");
    const steps = [
      ["LuMic", "Listen", "My speech is transcribed live (Gemini)."],
      ["LuFilter", "Decide", "Only clear requests like “in the next slide…” count. “Don't make…” and quotes are ignored."],
      ["LuSparkles", "Make", "An LLM writes the slide from the request and the last 90 s; then the picture is drawn."],
    ];
    for (let i = 0; i < steps.length; i++) {
      const y = 3.4 + i * 1.18;
      await iconCircle(s, steps[i][0], 1.45, y, 0.72);
      T(s, `${i + 1}  ${steps[i][1]}`, { x: 2.38, y: y - 0.02, w: 3.6, h: 0.34, fontFace: F.EB, fontSize: 16, color: C.text2 });
      T(s, steps[i][2], { x: 2.38, y: y + 0.34, w: 3.65, h: 0.75, fontFace: F.L, fontSize: 12, color: TINT.sub });
    }
    const x0 = 6.5, w = 5.95, sc = w / 1440, h = 760 * sc, y0 = 3.35;
    img(s, "presenter_ui.jpg", x0, y0, w, h, "NextSlide presenter screen: current slide on the left; next-slide preview, live transcript and detected request on the right", "Presenter screen");
    [[1, 364, 560], [2, 574, 750], [3, 14, 350]].forEach(([k, top, bot]) => {
      frame(s, x0 + 1025 * sc, y0 + top * sc, 398 * sc, (bot - top) * sc, "Step " + k + " area", H.accent2, 1.5);
      badge(s, k, x0 + w + 0.07, y0 + ((top + bot) / 2) * sc - 0.17, 0.34, H.accent2);
    });
    T(s, "1 live transcript   ·   2 detected request   ·   3 next-slide preview", { x: x0, y: y0 + h + 0.12, w, h: 0.32, fontFace: F.L, fontSize: 11.5, color: TINT.sub, align: "center" });
  }

  // 5. 핵심 아이디어
  {
    const s = S("CONTENT", "System");
    head(s, "02  |  How it works", "2. Key idea: it also uses what was said before");
    banner(s, "Key idea", [
      ["Said a minute before", "Joseon's civil service exam; a scholar walks to Hanyang to take it"],
      ["Then the request", "“In the next slide, show the exam hall.”"],
    ]);
    card(s);
    bracket(s, COL2[0], 2.7, CW2, "Request only");
    bracket(s, COL2[1], 2.7, CW2, "Request + lecture context", C.accent2);
    const iw = 5.1, ih = iw * 9 / 16;
    img(s, "s09_request_only.jpg", COL2[0] + (CW2 - iw) / 2, 3.32, iw, ih, "Image generated from the request only: a modern classroom", "Request only image");
    img(s, "s09_with_context.jpg", COL2[1] + (CW2 - iw) / 2, 3.32, iw, ih, "Image generated with the lecture context: a Joseon-era civil service exam ground", "With context image");
    T(s, "→  a modern classroom", { x: COL2[0], y: 6.32, w: CW2, h: 0.36, fontFace: F.EB, fontSize: 14, color: TINT.sub, align: "center" });
    T(s, "→  the Joseon exam ground the teacher meant", { x: COL2[1], y: 6.32, w: CW2, h: 0.36, fontFace: F.EB, fontSize: 14, color: C.accent2, align: "center" });
  }

  // 6. 형태 고르기
  {
    const s = S("CONTENT", "System");
    head(s, "02  |  How it works", "3. Pictures only when a picture helps");
    banner(s, "Design", [
      ["Lecture 17", "image models still get text, counts and relations wrong"],
      ["So", "the LLM picks the slide form first; only illustrations go to the image model"],
    ]);
    card(s);
    const shots = [
      ["real_v2_illustration.jpg", "Illustration", "drawn by the image model"],
      ["real_v2_equation_gd.jpg", "Equation", "typeset with KaTeX"],
      ["real_v4_comparison.jpg", "Comparison", "fixed two-column layout"],
    ];
    const iw = 3.25, ih = iw * 9 / 16;
    shots.forEach((sh, i) => {
      bracket(s, COL3[i], 2.7, CW3, sh[1]);
      img(s, sh[0], COL3[i] + (CW3 - iw) / 2, 3.45, iw, ih, sh[1] + " slide made by NextSlide", sh[1] + " example");
      T(s, sh[2], { x: COL3[i], y: 3.45 + ih + 0.2, w: CW3, h: 0.35, fontFace: F.L, fontSize: 13, color: TINT.sub, align: "center" });
    });
    T(s, "All three were made by the system with real APIs; the slide text is Korean.", { x: 1.32, y: 6.35, w: 11.5, h: 0.35, fontFace: F.L, fontSize: 11.5, color: TINT.sub, align: "center" });
  }

  // 7. 시연
  {
    const s = S("CONTENT", "System");
    head(s, "03  |  Live demo", "1. Live demo");
    banner(s, "Demo", [["Korean in, English out", "I speak the lecture lines to the system in Korean and translate as I go"]], H.accent3);
    card(s);
    bracket(s, 1.32, 2.7, 11.53, "Watch for four things");
    const rows = [
      ["LuMessageSquare", "I explain something", "Nothing is made", H.accent5, 2.4, false],
      ["LuFileText", "I ask for a slide", "The text appears first", H.accent2, 4.1, true],
      ["LuImage", "The picture forms", "Step by step, from noise", H.accent4, 4.6, false],
      ["LuBan", "I say “don't make it”", "Nothing is made", H.accent5, 2.4, false],
    ];
    for (let i = 0; i < rows.length; i++) {
      const [ic, label, result, color, bw, red] = rows[i];
      const y = 3.42 + i * 0.84;
      await iconCircle(s, ic, 1.65, y, 0.62, red);
      T(s, label, { x: 2.5, y, w: 3.6, h: 0.62, fontFace: F.EB, fontSize: 15.5, color: red ? C.accent2 : C.text1, valign: "middle" });
      dotted(s, 6.05, y + 0.31, 1.25);
      s.addShape(pres.shapes.RECTANGLE, { x: 7.45, y: y + 0.07, w: bw, h: 0.48, fill: { color }, line: { type: "none" }, objectName: "Result bar " + (i + 1) });
      T(s, result, { x: 7.6, y: y + 0.07, w: bw - 0.2, h: 0.48, fontFace: F.EB, fontSize: 14, color: "FFFFFF", valign: "middle" });
    }
    T(s, "Backup: a recorded video of the same steps", { x: 1.65, y: 6.72, w: 6, h: 0.3, fontFace: F.L, fontSize: 11, color: TINT.sub });
  }

  // 8. 확산 과정
  pres.addSection({ title: "Experiments" });
  {
    const s = S("CONTENT", "Experiments");
    head(s, "04  |  Course concepts & experiments", "1. You can watch the diffusion model draw");
    banner(s, "Course", [
      [[xhat(), { text: " (predicted image)" }], "at every step the model guesses the final image; I show that guess"],
      ["Cost", "almost none: a fixed linear map turns the guess into colors, no full decoding"],
    ]);
    card(s);
    bracket(s, 1.32, 2.7, 11.53, "Denoising preview  ·  Stable Diffusion 1.5, DDIM, 25 steps (about 12 s)");
    const sw = 11.1, sh = sw * 360 / 2632, sy = 3.45;
    img(s, "denoise_strip.jpg", 1.55, sy, sw, sh, "The model's guess of the finished image at steps 4, 12 and 22 of 25, and the final image", "Denoising strip");
    const pw = sw * 664 / 2632;
    ["Step 4 / 25", "Step 12 / 25", "Step 22 / 25", "Final image"].forEach((l, i) =>
      T(s, l, { x: 1.55 + i * pw, y: sy + sh + 0.15, w: pw - 0.1, h: 0.35, fontFace: F.EB, fontSize: 13.5, color: i === 3 ? C.accent2 : C.text2, align: "center" }));
    s.addShape(pres.shapes.LINE, { x: 1.55, y: sy + sh + 0.75, w: sw, h: 0, line: { color: H.accent5, width: 1.25, endArrowType: "triangle" }, objectName: "Time arrow" });
    T(s, "noise", { x: 1.55, y: sy + sh + 0.85, w: 2, h: 0.3, fontFace: F.L, fontSize: 11.5, color: TINT.sub });
    T(s, "image", { x: 1.55 + sw - 2, y: sy + sh + 0.85, w: 2, h: 0.3, fontFace: F.L, fontSize: 11.5, color: TINT.sub, align: "right" });
    T(s, "In the demo, both the presenter and the audience screens show these previews while the picture is made.", { x: 1.55, y: 6.25, w: sw, h: 0.4, fontFace: F.L, fontSize: 12.5, color: TINT.sub, align: "center" });
  }

  // 9. 실험 1: 속도
  {
    const s = S("CONTENT", "Experiments");
    head(s, "04  |  Course concepts & experiments", "2. Experiment 1 · Is it fast enough for a live lecture?");
    banner(s, "Result", [
      ["0.7 s per image", "SD-Turbo with 2 steps, about 16× faster than SD 1.5 with 25 steps"],
      ["About 6 s", "from my sentence to a finished slide (one test run)"],
    ], H.accent2);
    card(s);
    bracket(s, 1.32, 2.7, 6.25, "Seconds per image on my laptop");
    bracket(s, 7.85, 2.7, 5.0, "Why it is fast");
    s.addChart(pres.charts.BAR, [{ name: "Seconds per image", labels: ["Stable Diffusion 1.5 · 25 steps", "SD-Turbo · 2 steps"], values: [11.1, 0.68] }], {
      x: 1.45, y: 3.35, w: 6.0, h: 3.3, ...chartBase(), barDir: "bar",
      chartColors: [H.accent4, H.accent2], dataLabelPosition: "outEnd", dataLabelFormatCode: "0.0#\" s\"", dataLabelFontSize: 15,
      valAxisHidden: true, valAxisMinVal: 0, valAxisMaxVal: 14, valGridLine: { style: "none" }, barGapWidthPct: 55, catAxisOrientation: "maxMin", catAxisLabelFontSize: 12.5,
      objectName: "Speed chart",
    });
    T(s, [{ text: "16×", options: { fontFace: F.H, fontSize: 44, color: C.text2 } }, { text: "  faster", options: { fontFace: F.EB, fontSize: 18, color: C.text2 } }],
      { x: 8.1, y: 3.3, w: 4.6, h: 0.85, valign: "middle" });
    T(s, "0.68 s vs 11.1 s per image", { x: 8.1, y: 4.15, w: 4.6, h: 0.35, fontFace: F.L, fontSize: 13, color: TINT.sub });
    dotted(s, 8.1, 4.7, 4.5);
    T(s, "SD-Turbo is distilled from a larger diffusion model, so it needs only 1–4 steps.", { x: 8.1, y: 4.85, w: 4.55, h: 0.75, fontSize: 13.5 });
    dotted(s, 8.1, 5.75, 4.5);
    T(s, [{ text: "Prompt match: " }, { text: "CLIP 28.2 vs 25.0", options: { color: C.accent2, fontFace: F.EB } }, { text: ", slightly better too." }], { x: 8.1, y: 5.9, w: 4.55, h: 0.7, fontSize: 13.5 });
  }

  // 10. 실험 2: 가이던스
  {
    const s = S("CONTENT", "Experiments");
    head(s, "04  |  Course concepts & experiments", "3. Experiment 2 · What does the guidance scale change?");
    banner(s, "Result", [
      ["Higher guidance", "closer to the prompt: CLIP 21.5 → 25.7, then flat after 5"],
      ["But", "less variety between seeds: 0.27 → 0.18"],
    ], H.accent2);
    card(s);
    bracket(s, 1.32, 2.7, 11.53, "Same prompt and seed; only the guidance scale changes");
    const iw = 2.5, ih = iw * 9 / 16, gap = 0.45, iy = 3.3;
    [["cfg_1.jpg", "1"], ["cfg_3.jpg", "3"], ["cfg_7_5.jpg", "7.5"], ["cfg_12.jpg", "12"]].forEach(([f, l], i) => {
      const x = 1.45 + i * (iw + gap);
      img(s, f, x, iy, iw, ih, "Stable Diffusion 1.5 image of a hiker walking down a foggy valley at guidance scale " + l, "Guidance " + l + " image");
      T(s, "Guidance " + l, { x, y: iy + ih + 0.07, w: iw, h: 0.3, fontFace: F.EB, fontSize: 12.5, color: C.text2, align: "center" });
      if (i < 3) chev(s, x + iw + 0.12, iy + ih / 2 - 0.22, 0.2, 0.44);
    });
    const labels = ["1", "3", "5", "7.5", "12"];
    const mini = (min, max, fmt, color) => ({
      ...chartBase(), chartColors: [color], lineSize: 2.25, lineDataSymbol: "circle", lineDataSymbolSize: 7,
      dataLabelPosition: "t", dataLabelFontSize: 10, valAxisMinVal: min, valAxisMaxVal: max, dataLabelFormatCode: fmt, valAxisLabelFormatCode: fmt,
      valAxisLabelFontSize: 9, catAxisLabelFontSize: 10,
    });
    T(s, "Prompt match (CLIP), 12 scenes × 2 seeds", { x: 1.45, y: 5.12, w: 5.5, h: 0.3, fontFace: F.EB, fontSize: 12, color: C.text2 });
    T(s, "Variety between seeds (1 − cosine)", { x: 7.25, y: 5.12, w: 5.5, h: 0.3, fontFace: F.EB, fontSize: 12, color: C.accent2 });
    s.addChart(pres.charts.LINE, [{ name: "Prompt match", labels, values: [21.5, 24.6, 25.7, 25.0, 25.6] }],
      { x: 1.35, y: 5.38, w: 5.6, h: 1.7, ...mini(20, 27, "0.0", H.dk2), objectName: "Guidance vs prompt match" });
    s.addChart(pres.charts.LINE, [{ name: "Variety", labels, values: [0.269, 0.209, 0.213, 0.182, 0.177] }],
      { x: 7.15, y: 5.38, w: 5.6, h: 1.7, ...mini(0.15, 0.28, "0.00", H.accent2), objectName: "Guidance vs variety" });
  }

  // 11. 실험 3: 강의 맥락
  {
    const s = S("CONTENT", "Experiments");
    head(s, "04  |  Course concepts & experiments", "4. Experiment 3 · Does the lecture context actually help?");
    banner(s, "Result", [
      ["+2.1 CLIP points", "B's images were closer to the intended scene (p = 0.010, 28 pairs)"],
      ["7 → 0", "times the system had to ask what I meant, out of 42"],
    ], H.accent2);
    card(s);
    bracket(s, 1.32, 2.7, 4.65, "How it was tested");
    bracket(s, 6.25, 2.7, 6.6, "B − A for each scenario (CLIP points)");
    const steps = [
      "42 lecture scenarios, 30 from this course's lectures",
      "Each request twice — A: request only; B: + recent speech + current slide",
      "Intended scene written and committed to git before any image was made",
    ];
    steps.forEach((t, i) => {
      const y = 3.35 + i * 1.12;
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 1.45, y, w: 4.4, h: 0.92, rectRadius: 0.08, fill: { color: TINT.blue }, line: { type: "none" }, objectName: "Setup step " + (i + 1) });
      badge(s, i + 1, 1.62, y + 0.29);
      T(s, t, { x: 2.12, y, w: 3.6, h: 0.92, fontSize: 12.5, valign: "middle" });
    });
    const ids = Object.keys(X4_DIFF).sort((a, b) => X4_DIFF[b] - X4_DIFF[a]);
    s.addChart(pres.charts.BAR, [{ name: "B minus A", labels: ids, values: ids.map((k) => X4_DIFF[k]) }], {
      x: 6.35, y: 3.25, w: 6.4, h: 3.35, ...chartBase(), barDir: "col",
      chartColors: [H.dk2], invertedColors: [H.accent5], showValue: false, catAxisHidden: true,
      valAxisMinVal: -6, valAxisMaxVal: 12, valAxisMajorUnit: 3, valAxisLabelFormatCode: "+0;-0;0", barGapWidthPct: 40,
      objectName: "X4 per-scenario difference",
    });
    T(s, "17 of the 28 scenarios where both versions drew a picture moved closer.", { x: 6.35, y: 6.62, w: 6.4, h: 0.32, fontFace: F.L, fontSize: 11.5, color: TINT.sub, align: "center" });
  }

  // 12. 한계
  pres.addSection({ title: "Closing" });
  {
    const s = S("CONTENT", "Closing");
    head(s, "05  |  Limits", "1. What still goes wrong");
    banner(s, "Limits", [
      ["Fake text", "the fast model draws gibberish text on paper and signs (about 9 of 34 images)"],
      ["Evaluation", "CLIP is the only automatic judge, and I wrote the test scenarios myself"],
    ], TINT.dark);
    card(s);
    bracket(s, COL2[0], 2.7, CW2, "Fake text example");
    bracket(s, COL2[1], 2.7, CW2, "Next steps");
    const iw = 5.1, ih = iw * 9 / 16;
    img(s, "fake_text.jpg", COL2[0] + (CW2 - iw) / 2, 3.32, iw, ih, "SD-Turbo image with fake text: lines on the papers look like writing but are meaningless", "Fake text example");
    T(s, "SD-Turbo, scene “a student peeking at the answer key”: the lines on the papers are fake text. Telling the planner to draw blank surfaces didn't reduce it.",
      { x: COL2[0] + 0.25, y: 6.28, w: CW2 - 0.5, h: 0.6, fontFace: F.L, fontSize: 11.5, color: TINT.sub, align: "center" });
    const items = [
      "Blind evaluation by people (fit, breakage, fake text)",
      "Real speech-recognition transcripts in the detector test set",
      "Latency measured over 10+ runs",
      "gpt-image-2 when picture quality matters more than speed",
    ];
    for (let i = 0; i < items.length; i++) {
      const y = 3.4 + i * 0.82;
      s.addImage({ data: await icon("LuCheckCircle", H.accent1), x: 7.45, y: y + 0.02, w: 0.38, h: 0.38, altText: "Check icon", objectName: "Check " + (i + 1) });
      T(s, items[i], { x: 7.98, y, w: 4.7, h: 0.42, fontSize: 14, valign: "middle" });
      if (i < items.length - 1) dotted(s, 7.45, y + 0.62, 5.2);
    }
  }

  // 13. 정리 (IR 마지막 장 형식)
  {
    const s = S("ENDING", "Closing");
    s.addShape(pres.shapes.OVAL, { x: 8.6, y: -0.6, w: 5.2, h: 5.2, fill: { color: "FFFFFF", transparency: 94 }, line: { type: "none" }, objectName: "Decor blob" });
    rect(s, 10.2, 1.5, 2.2, 1.64, "FFFFFF", "Decor mark", { fill: { color: "FFFFFF", transparency: 92 } });
    rect(s, 10.75, 2.05, 2.2, 1.64, "FFFFFF", "Decor mark", { fill: { color: "FFFFFF", transparency: 90 } });
    T(s, "To sum up,", { x: 0.72, y: 0.75, w: 8, h: 0.5, fontFace: F.L, fontSize: 20, color: "D9D9D9" });
    T(s, "Say what the next slide should show,", { x: 0.72, y: 1.35, w: 9.5, h: 0.7, fontFace: F.L, fontSize: 32, color: "FFFFFF" });
    T(s, "and it's ready in a few seconds.", { x: 0.72, y: 2.02, w: 9.5, h: 0.75, fontFace: F.H, fontSize: 34, color: "FFFFFF" });
    T(s, "Lecture context brings the picture closer to what you meant. The weak spot is still the image model.",
      { x: 0.72, y: 3.05, w: 9.6, h: 0.75, fontFace: F.L, fontSize: 16, color: "D9D9D9" });
    T(s, [{ text: "Thank you", options: { fontFace: F.H } }, { text: "  |  Questions?", options: { fontFace: F.L } }], { x: 0.72, y: 4.3, w: 8, h: 1.5, fontSize: 24, color: "FFFFFF", valign: "middle" });
    rect(s, 10.62, 4.78, 0.5, 0.37, "FFFFFF", "Logo back", { fill: { color: "FFFFFF", transparency: 45 } });
    rect(s, 10.74, 4.9, 0.5, 0.37, "FFFFFF", "Logo front");
    T(s, "NEXT\nSLIDE", { x: 11.42, y: 4.68, w: 1.6, h: 0.72, fontFace: F.H, fontSize: 18, color: "FFFFFF", lineSpacingMultiple: 0.85, valign: "middle" });
  }

  // 부록 1: 기존 도구 비교
  pres.addSection({ title: "Backup" });
  {
    const s = S("CONTENT", "Backup");
    head(s, "Backup", "A1. Compared with live-staging tools");
    banner(s, "Backup", [["Prior work", "ZeroPrep reacts to every utterance; NextSlide waits for a clear request"]], H.accent5);
    card(s);
    bracket(s, 1.32, 2.7, 11.53, "Live-staging tools vs. NextSlide");
    const hdr = (t) => ({ text: t, options: { fontFace: F.EB, color: "FFFFFF", fill: { color: H.dk2 }, align: "center" } });
    const hi = (t) => ({ text: t, options: { fontFace: F.EB, color: C.text2 } });
    const lab = (t) => ({ text: t, options: { fontFace: F.EB, fill: { color: TINT.bar } } });
    s.addTable([
      [hdr(""), hdr("Live-staging tools (e.g. ZeroPrep)"), hdr("NextSlide")],
      [lab("What triggers a slide"), "A realtime model interprets every utterance", hi("Only explicit requests (rule-based detector)")],
      [lab("Who sees it first"), "The audience, immediately", hi("The presenter; the audience sees it when I advance")],
      [lab("Slide forms"), "Cards, metrics, diagrams", hi("Illustration, equation, comparison, table, chart")],
      [lab("Context used"), "The current utterance", hi("Request + last 90 s of speech + current slide")],
    ], {
      x: 1.45, y: 3.35, w: 11.25, colW: [2.65, 4.2, 4.4], fontFace: F.B, fontSize: 13, color: C.text1,
      border: { type: "solid", pt: 0.75, color: TINT.line }, valign: "middle", rowH: [0.48, 0.62, 0.62, 0.62, 0.62], margin: 0.1,
      objectName: "Prior work comparison",
    });
    T(s, "ZeroPrep: github.com/ramsrigouthamg/zeroprep (README and app code read on 2026-11-05)", { x: 1.45, y: 6.5, w: 11.25, h: 0.3, fontFace: F.L, fontSize: 10.5, color: TINT.sub });
  }

  // 부록 2: 시스템 수치
  {
    const s = S("CONTENT", "Backup");
    head(s, "Backup", "A2. System numbers");
    banner(s, "Backup", [
      ["Detector", "56 of 60 test sentences right: 0 missed requests, 1 false slide"],
      ["Tests", "112 automated backend tests with mock providers (no API calls)"],
    ], H.accent5);
    card(s);
    bracket(s, 1.32, 2.7, 11.53, "End to end, one run each");
    const hdr = (t) => ({ text: t, options: { fontFace: F.EB, color: "FFFFFF", fill: { color: H.dk2 }, align: "center" } });
    s.addTable([
      [hdr("Path"), hdr("Text ready"), hdr("Image"), hdr("Slide ready")],
      [{ text: "Local SD-Turbo", options: { fontFace: F.EB } }, "5.0 s", "1.2 s", { text: "6.2 s", options: { fontFace: F.EB, color: C.accent2 } }],
      [{ text: "gpt-image-2 API", options: { fontFace: F.EB } }, "5.7 s", "14.3 s", { text: "20.0 s", options: { fontFace: F.EB } }],
    ], {
      x: 1.45, y: 3.4, w: 11.25, colW: [3.6, 2.55, 2.55, 2.55], fontFace: F.B, fontSize: 14, color: C.text1, align: "center",
      border: { type: "solid", pt: 0.75, color: TINT.line }, valign: "middle", rowH: [0.5, 0.62, 0.62], margin: 0.1,
      objectName: "Latency table",
    });
    T(s, "The other 3 detector errors were needless “which topic?” questions; I wrote the test set myself. Cost: the planner LLM is about $0.0002–0.0004 per slide, an API image about $0.0045, local images free.",
      { x: 1.45, y: 5.45, w: 11.25, h: 0.7, fontFace: F.L, fontSize: 12.5, color: TINT.sub });
  }

  // 부록 3: 측정 방법
  {
    const s = S("CONTENT", "Backup");
    head(s, "Backup", "A3. How the experiments were measured");
    banner(s, "Backup", [["Method", "one setting changed at a time, fixed seeds, a scorer that is not part of the generators"]], H.accent5);
    card(s);
    bracket(s, 1.32, 2.7, 11.53, "Details");
    const items = [
      "Score: CLIP ViT-B/32 cosine similarity × 100, a different model from the generators' text encoders",
      "X1–X3: 12 lecture scenes × 2 fixed seeds; 95% bootstrap confidence intervals",
      "X4: 28 paired scenarios, paired permutation test; intended scenes committed before any image was made",
      "X1: DDPM at 10 steps broke shapes and DDIM didn't, yet CLIP gave 25.5 vs 25.1",
      "X3 caveat: SD-Turbo is based on SD 2.1 with a larger text encoder, so the gain is not distillation alone",
      "Bug found: prompts over CLIP's 77-token limit lost their style words (18 of 18); fixed with token-aware trimming",
      "Dropped: CLIP as a fake-text detector (only 1 of its top 6 picks had text)",
    ];
    for (let i = 0; i < items.length; i++) {
      const y = 3.3 + i * 0.5;
      s.addImage({ data: await icon("LuCheckCircle", H.accent1), x: 1.55, y: y + 0.07, w: 0.28, h: 0.28, altText: "Check icon", objectName: "Check " + (i + 1) });
      T(s, items[i], { x: 2.0, y, w: 10.7, h: 0.42, fontSize: 13, valign: "middle" });
    }
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
  L.push("- 글꼴: 덱은 나눔스퀘어 네오(NanumSquare Neo, NAVER 무료 글꼴)를 씁니다. 발표할 컴퓨터에 먼저 설치하세요(`fonts/README.md`). 없으면 PowerPoint가 다른 글꼴로 바꿔 보여 줍니다.", "");
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
