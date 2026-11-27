// NextSlide 기말 발표 PPT 생성 스크립트 (pptxgenjs).
// 실행: NODE_PATH=<pptxgenjs 가 설치된 node_modules> node docs/presentation/build_deck.js
// 결과: docs/presentation/NextSlide_final.pptx, docs/presentation/script.md (영어와 한국어 대본)
// 대본은 아래 SCRIPT 한 곳에서 관리하고, 슬라이드 노트와 script.md 를 함께 만든다.

const path = require("path");
const fs = require("fs");
const pptxgen = require("pptxgenjs");

const HERE = __dirname;
const A = (f) => path.join(HERE, "assets", f);
const OUT = path.join(HERE, "NextSlide_final.pptx");
const APPLY_THEME = process.env.APPLY_THEME_JS; // pptx 스킬의 scripts/apply_theme.js 경로 (선택)

// 디자인 원칙: 한 장에 문장 하나와 그림(또는 숫자) 하나. 흰 바탕, 큰 글씨, 파랑 하나로 강조.
// 템플릿 티가 나는 장식(대문자 머리표, 원 안의 아이콘, 가운뎃점 구분자, 줄표, 문장 속 화살표)은 쓰지 않는다.
// 글꼴: 나눔스퀘어 네오(NAVER). Light는 TTF, Bold/ExtraBold/Heavy는 OTF 패밀리 이름으로 지정한다.
const F = {
  L: "NanumSquare Neo Light",
  B: "NanumSquare Neo OTF Bold",
  EB: "NanumSquare Neo OTF ExtraBold",
  H: "NanumSquare Neo OTF Heavy",
  MATH: "Cambria Math", // x̂₀ (나눔스퀘어 네오에는 결합 기호 ̂ 이 없음)
};
const THEME = {
  name: "NextSlide Clean",
  headFontFace: F.H,
  bodyFontFace: F.B,
  colors: {
    dk1: "1E2430", // 본문 글자
    lt1: "FFFFFF",
    dk2: "6B7280", // 보조 글자
    lt2: "F3F5F8", // 옅은 면
    accent1: "2D66AD", // 파랑(강조 하나)
    accent2: "DD5C47", // 빨강(문제와 한계에만)
    accent3: "1F4E8C", // 짙은 파랑
    accent4: "A3AAB5", // 흐린 회색
    accent5: "E8F0FA", // 아주 옅은 파랑
    accent6: "D9DEE5", // 선
    hlink: "2D66AD", folHlink: "1F4E8C",
  },
};
const H = THEME.colors; // hex-only 옵션(차트, 그림자)용

// ───────────────────────── 대본 (영어 / 한국어) ─────────────────────────
// 장마다 메시지 하나. backup: true 인 장은 질문이 나올 때만 쓰는 부록이라 발표 시간에 넣지 않는다.
const SCRIPT = [
  {
    title: "Title",
    en: "Hi, I'm [name], and my project is NextSlide. While I lecture, I say what the next slide should show, and it gets made while I keep talking.",
    ko: "안녕하세요, [이름]입니다. 제 프로젝트는 NextSlide입니다. 강의하다가 다음 장에 무엇을 보여 줄지 말하면, 제가 계속 말하는 동안 그 장이 만들어집니다.",
  },
  {
    title: "An idea mid-lecture",
    en: "When I teach, I often think of an analogy on the spot. Say the students look lost, and I tell them that overfitting is like a student who memorized the answers to old exams.",
    ko: "수업을 하다 보면 비유가 그 자리에서 떠오를 때가 많습니다. 학생들이 잘 못 따라오는 것 같아서, 과적합은 기출문제 답을 외운 학생과 같다고 설명한다고 해 봅시다.",
  },
  {
    title: "No slide for it",
    en: "The explanation works, but there is no slide for it. I made the slides before class, and making a new one now would mean stopping the lecture.",
    ko: "설명은 괜찮은데 보여 줄 슬라이드가 없습니다. 슬라이드는 수업 전에 만들었고, 지금 새로 만들려면 강의를 멈춰야 합니다.",
  },
  {
    title: "Just say it",
    en: "With NextSlide, I just say it out loud. Here I said this sentence in Korean: 'In the next slide, I'll explain overfitting by comparing it to a student who memorized the exam questions.'",
    ko: "NextSlide를 쓰면 그냥 말로 하면 됩니다. 이번에는 한국어로 이렇게 말했습니다. '다음 슬라이드에서는 과적합을 시험 문제를 외운 학생에 비유해서 설명하겠습니다.'",
  },
  {
    title: "The slide it made",
    en: "This is the slide it made, with a title, three short points and a picture. This run used the image API and took about 20 seconds. With the local model it takes about six.",
    ko: "그렇게 해서 나온 장이 이것입니다. 제목과 짧은 설명 세 줄, 그림이 들어 있습니다. 이번에는 이미지 API를 써서 20초쯤 걸렸고, 로컬 모델로는 6초 정도 걸립니다.",
  },
  {
    title: "How it works",
    en: "It works in three steps. First, my speech is turned into text as I talk. Second, the system decides whether I asked for a slide. Third, a language model writes the slide and an image model draws the picture.",
    ko: "동작은 세 단계입니다. 먼저 제 말을 실시간으로 글로 옮깁니다. 다음으로 슬라이드를 만들어 달라는 요청인지 판단합니다. 마지막으로 언어 모델이 장을 쓰고 이미지 모델이 그림을 그립니다.",
  },
  {
    title: "Only clear requests",
    en: "The second step matters most, because a wrong slide interrupts the lecture. So the detector only reacts to clear requests, and a negation or a quote is ignored. On 60 test sentences it was right 56 times and never missed a real request.",
    ko: "두 번째 단계가 가장 중요합니다. 엉뚱한 장이 나오면 강의가 끊기기 때문입니다. 그래서 감지기는 분명한 요청에만 반응하고, 부정하는 말이나 인용한 말은 무시합니다. 평가 문장 60개 중 56개를 맞혔고, 실제 요청을 놓친 적은 없습니다.",
  },
  {
    title: "You see it first",
    en: "The new slide comes to me first. The text shows up right away and the picture follows, and I can still edit or cancel it. The audience only sees it when I advance.",
    ko: "새 장은 저한테 먼저 옵니다. 글이 바로 뜨고 그림이 뒤따라오며, 이때 고치거나 취소할 수 있습니다. 청중은 제가 넘길 때 비로소 봅니다.",
  },
  {
    title: "What was said before",
    en: "This is the part I care about most. In this test scenario, a history teacher talks about the Joseon civil service exam and then says 'show the exam hall'. That request alone is vague, so NextSlide also sends the last ninety seconds of speech and the current slide.",
    ko: "제가 가장 공들인 부분입니다. 이 평가 시나리오에서 역사 선생님은 조선의 과거 시험 이야기를 하다가 '시험장 풍경을 보여 주세요'라고 합니다. 이 요청만으로는 모호해서, NextSlide는 직전 90초 동안 한 말과 현재 장도 같이 보냅니다.",
  },
  {
    title: "Same request, different picture",
    en: "The request, the model and the seed are the same. With the request alone, we get a modern classroom. With the lecture before it, we get the Joseon exam ground the teacher meant, and nobody had to write a prompt.",
    ko: "요청도, 모델도, 시드도 같습니다. 요청만 주면 현대식 교실이 나옵니다. 앞의 강의까지 주면 선생님이 말한 조선의 과거 시험장이 나오고, 프롬프트는 아무도 쓰지 않았습니다.",
  },
  {
    title: "A picture only when it helps",
    en: "We saw in Lecture 17 that image models still get text and numbers wrong. So the language model first picks what kind of slide to make. Only illustrations go to the image model. Equations are typeset, and comparisons use a fixed layout.",
    ko: "17강에서 봤듯이 이미지 모델은 아직 글자와 숫자를 자주 틀립니다. 그래서 언어 모델이 먼저 어떤 종류의 장을 만들지 고릅니다. 설명 그림만 이미지 모델에 보내고, 수식은 조판하고, 비교는 정해진 레이아웃을 씁니다.",
  },
  {
    t: "2:00", title: "Live demo",
    en: "Now let me show it live. The system is built for Korean lectures, so I'll speak the lecture lines in Korean and translate as I go. Please watch for the four things on this slide. (Run the demo. See the demo script below.)",
    ko: "이제 직접 보여 드리겠습니다. 한국어 강의용 시스템이라 강의 문장은 한국어로 말하고 바로 영어로 옮기겠습니다. 이 화면에 적은 네 가지를 봐 주세요. (시연 진행. 아래 시연 대본 참고)",
  },
  {
    title: "Watching diffusion",
    en: "Now the link to the course. The pictures come from a diffusion model on my laptop. At every step it predicts the final image, x-hat-zero from Lecture 17, and I show that prediction so you can watch the picture form.",
    ko: "이제 수업 내용과 이어지는 부분입니다. 그림은 제 노트북의 확산 모델이 그립니다. 모델은 매 단계 최종 그림, 즉 17강에서 배운 x̂₀를 예측하는데, 이 예측을 화면에 띄워서 그림이 만들어지는 과정을 볼 수 있게 했습니다.",
  },
  {
    title: "Three questions",
    en: "I ran experiments to answer three questions. For each one, I'll first show how I tested it, and then the result.",
    ko: "세 가지 질문에 답하려고 실험을 했습니다. 질문마다 먼저 어떻게 실험했는지 보여 드리고, 그다음에 결과를 말씀드리겠습니다.",
  },
  {
    title: "Q1 setup",
    en: "First, speed. I drew 12 lecture scenes with two seeds each on two models: Stable Diffusion 1.5 with 25 steps, and SD-Turbo, a distilled model that needs only two. I measured seconds per image on my laptop, and the CLIP score, which says how well the picture matches the scene sentence.",
    ko: "첫 번째는 속도입니다. 강의 장면 12개를 시드 두 개씩, 두 모델로 그렸습니다. 25단계짜리 Stable Diffusion 1.5와, 2단계면 되는 증류 모델 SD-Turbo입니다. 제 노트북에서 그림 한 장에 걸린 시간을 재고, 그림이 장면 문장과 얼마나 맞는지 보는 CLIP 점수도 쟀습니다.",
  },
  {
    title: "Q1 result",
    en: "Stable Diffusion 1.5 takes 11 seconds per image. SD-Turbo takes 0.7 seconds, about sixteen times faster, and its CLIP score was a bit higher too. So I made SD-Turbo the default.",
    ko: "Stable Diffusion 1.5는 그림 한 장에 11초, SD-Turbo는 0.7초가 걸려 16배쯤 빨랐고, CLIP 점수도 조금 높았습니다. 그래서 SD-Turbo를 기본값으로 정했습니다.",
  },
  {
    title: "Q2 setup",
    en: "Second, guidance. Lecture 17 says stronger guidance follows the condition more closely but gives less variety. So I changed only the guidance scale and kept everything else from the first test. I also measured variety, meaning how different the two seeds' pictures are.",
    ko: "두 번째는 가이던스입니다. 17강에서 가이던스를 세게 주면 조건은 더 잘 따르지만 다양성은 줄어든다고 배웠습니다. 그래서 첫 번째 실험의 조건은 그대로 두고 가이던스 스케일만 바꿨습니다. 두 시드로 그린 그림이 서로 얼마나 다른지를 다양성으로 함께 쟀습니다.",
  },
  {
    title: "Q2 result: pictures",
    en: "This is one scene drawn with the same seed. At 1 the picture barely forms, and by 7.5 you can clearly see the hiker in the valley.",
    ko: "같은 시드로 그린 장면 하나입니다. 1에서는 그림이 거의 형태를 갖추지 못하고, 7.5쯤 되면 골짜기를 걷는 등산객이 또렷하게 보입니다.",
  },
  {
    title: "Q2 result: the trade-off",
    en: "Over all 12 scenes, the CLIP score goes up and levels off around 5, but the variety keeps falling. So the trade-off from the lecture shows up here too. Note that CLIP measures prompt match, not image quality.",
    ko: "장면 12개 전체로 보면 CLIP 점수는 오르다가 5 근처에서 더 오르지 않고, 다양성은 계속 떨어집니다. 수업에서 배운 트레이드오프가 여기서도 보입니다. 다만 CLIP은 프롬프트와 맞는지만 볼 뿐, 그림의 질은 보지 못합니다.",
  },
  {
    title: "Q3 test data",
    en: "Third, the main question: does the lecture context help? I wrote 42 lecture scenarios, 30 based on this course. In this one from the diffusion lecture, the lecturer compares adding noise to ink spreading in water, then asks for the reverse process with the same analogy. I wrote down the intended picture and committed it before generating.",
    ko: "세 번째가 가장 중요한 질문입니다. 강의 맥락이 도움이 될까요? 강의 시나리오 42개를 만들었고, 그중 30개는 이 수업을 바탕으로 했습니다. 확산 모델 강의에서 가져온 이 예에서 강사는 잡음을 더하는 과정을 물에 퍼지는 잉크에 비유하고, 같은 비유로 역방향 과정을 보여 달라고 합니다. 강사가 뜻한 그림은 생성하기 전에 미리 적어 커밋해 두었습니다.",
  },
  {
    title: "Q3 setup",
    en: "Each request runs twice. A gets only the request, and B also gets the last 90 seconds and the current slide. Everything else is the same. I scored each picture by CLIP similarity to the intended scene and compared A and B with a paired permutation test.",
    ko: "요청마다 두 번 돌립니다. A는 요청만 받고, B는 직전 90초 발화와 현재 장까지 받습니다. 나머지는 모두 같습니다. 그림마다 정답 장면과의 CLIP 유사도로 점수를 매기고, A와 B를 짝지은 순열 검정으로 비교했습니다.",
  },
  {
    title: "Q3 result: closer to the intent",
    en: "Each bar is one of the 28 scenarios where both made a picture, and most are above zero. On average B is 2.1 points closer, with p equal to 0.010. In the text prompt the gain was 6.4, though, so the image model loses about two-thirds of it.",
    ko: "막대 하나가 A와 B 모두 그림을 만든 시나리오 28개 중 하나이고, 대부분 0보다 위에 있습니다. 평균으로 B가 2.1점 더 가까웠고 p값은 0.010입니다. 다만 프롬프트 글 단계에서는 6.4점 차이였으니, 이미지 모델을 거치면서 3분의 2쯤이 사라진 셈입니다.",
  },
  {
    title: "Q3 result: no more guessing",
    en: "Also, without the context the system had to ask me what I meant 7 times out of 42. With the context it never had to ask.",
    ko: "또 맥락이 없을 때는 42번 중 7번이나 시스템이 무슨 뜻인지 되물었습니다. 맥락이 있을 때는 한 번도 묻지 않았습니다.",
  },
  {
    title: "Still hard",
    en: "Some problems remain. The fast model draws fake text in about 9 of 34 images, and prompt rules didn't fix it. CLIP is my only automatic judge, and I wrote the scenarios with an AI assistant, so a blind evaluation by people comes next.",
    ko: "아직 남은 문제도 있습니다. 빠른 모델이 34장 중 9장 정도에 가짜 글자를 그렸고, 프롬프트 규칙으로도 나아지지 않았습니다. 자동 평가는 CLIP 하나뿐이고 시나리오는 AI 보조 도구와 함께 썼기 때문에, 다음에는 사람이 보는 블라인드 평가를 하려고 합니다.",
  },
  {
    title: "To sum up",
    en: "So, you say what the next slide should show, and it's ready in seconds. The lecture context brings the picture closer to what you meant, and the weak part is still the image model. Thank you. I'm happy to take questions.",
    ko: "정리하면, 다음 장에 보여 줄 것을 말하면 몇 초 안에 준비됩니다. 강의 맥락을 쓰면 그림이 뜻한 장면에 더 가까워지고, 아직 약한 부분은 이미지 모델입니다. 감사합니다. 질문 받겠습니다.",
  },
  {
    t: "-", title: "Backup: prior work", backup: true,
    en: "(Use if asked about prior work.) Live-staging tools such as ZeroPrep interpret every utterance and show the result to the audience right away. NextSlide reacts only to explicit requests, shows the presenter first, and picks the slide form instead of always making cards.",
    ko: "(이전 연구를 물으면 사용) ZeroPrep 같은 실시간 발표 도구는 모든 발화를 해석해 바로 청중에게 보여 줍니다. NextSlide는 명시적인 요청에만 반응하고, 발표자에게 먼저 보여 주며, 항상 카드를 만드는 대신 슬라이드 형태를 고릅니다.",
  },
  {
    t: "-", title: "Backup: system numbers", backup: true,
    en: "(Use if asked about the detector, tests or speed.) The detector got 56 of 60 test sentences right. It missed no requests, made one slide it shouldn't have, and asked 'which topic?' three times when it didn't need to. There are 112 automated backend tests with mock providers. End to end, one run took 6.2 seconds with local SD-Turbo and 20 seconds with the gpt-image-2 API.",
    ko: "(감지기, 테스트, 속도를 물으면 사용) 감지기는 평가 문장 60개 중 56개를 맞혔습니다. 요청을 놓친 경우는 없었고, 만들면 안 되는데 만든 경우가 1건, 주제를 괜히 되물은 경우가 3건입니다. 모의 제공자를 쓰는 자동 백엔드 테스트가 112개 있습니다. 전체 흐름은 로컬 SD-Turbo로 한 번 6.2초, gpt-image-2 API로 20초였습니다.",
  },
  {
    t: "-", title: "Backup: how it was measured", backup: true,
    en: "(Use if asked about the method.) Scores are cosine similarity from CLIP ViT-B/32 times 100. It is a different model from the generators' text encoders. Times are medians on an Apple M5 laptop with 16 GB, with the first call excluded as warm-up. Confidence intervals come from resampling the scenes. The X4 test flips the sign of each paired difference 20,000 times. SD-Turbo is based on SD 2.1, so its gain is not from distillation alone. The experiments also found a real bug. Prompts longer than CLIP's 77 tokens lost their style words, and that is fixed now.",
    ko: "(실험 방법을 물으면 사용) 점수는 CLIP ViT-B/32로 잰 코사인 유사도에 100을 곱한 값이고, 생성 모델의 텍스트 인코더와는 다른 모델입니다. 시간은 Apple M5, 메모리 16GB 노트북에서 잰 중앙값이고, 첫 호출은 워밍업이라 뺐습니다. 신뢰구간은 장면을 다시 뽑는 부트스트랩으로 구했습니다. X4 검정은 짝 차이의 부호를 20,000번 무작위로 뒤집었습니다. SD-Turbo는 SD 2.1 기반이라 빨라진 것이 증류만의 효과는 아닙니다. 실험하다가 실제 버그도 찾았습니다. CLIP의 77토큰을 넘는 프롬프트에서 화풍 문구가 잘리던 문제였고, 지금은 고쳤습니다.",
  },
];

// 장별 예상 시간(초). 시연처럼 t 를 직접 적은 장은 그 값을, 나머지는 영어 대본을 분당 약 140단어로 읽고
// 장 전환에 4초를 더해 5초 단위로 반올림한다.
const WPS = 140 / 60;
function secondsOf(s) {
  if (s.t && s.t !== "-") { const [m, sec] = s.t.split(":").map(Number); return m * 60 + sec; }
  if (s.backup) return 0;
  return Math.round((s.en.split(/\s+/).length / WPS + 4) / 5) * 5;
}
const fmtTime = (sec) => `${Math.floor(sec / 60)}:${String(sec % 60).padStart(2, "0")}`;
const timeOf = (s) => (s.backup ? "-" : fmtTime(secondsOf(s)));

const DEMO = [
  {
    step: "1. Normal speech: nothing happens", time: "0:20",
    speak: "과적합은 모델이 학습 데이터에 지나치게 맞춰져서 새로운 데이터에는 잘 대응하지 못하는 현상입니다.",
    meaning: "Overfitting is when a model fits the training data too closely and fails on new data.",
    point_en: "Point at the live caption. \"I just explained overfitting in Korean. It's an explanation, not a request, so nothing is generated.\"",
    point_ko: "자막을 가리키며: \"방금 한국어로 과적합을 설명했습니다. 요청이 아니라 설명이라서 아무것도 생성되지 않습니다.\"",
  },
  {
    step: "2. Request: the text comes first", time: "0:40",
    speak: "다음 슬라이드에서는 과적합을 시험 문제를 외운 학생에 비유해서 설명하겠습니다.",
    meaning: "In the next slide, I'll explain overfitting with a student who memorized the exam answers.",
    point_en: "\"I said: in the next slide, I'll explain overfitting with a student who memorized the exam answers. The detector confirmed the request. The title and bullets appear first in my preview. The audience screen hasn't changed yet.\"",
    point_ko: "\"방금 '다음 슬라이드에서는 과적합을 시험 문제를 외운 학생에 비유해서 설명하겠습니다'라고 했습니다. 감지기가 요청을 확정했고, 제목과 본문이 먼저 제 미리보기에 뜹니다. 청중 화면은 아직 그대로입니다.\"",
  },
  {
    step: "3. Denoising preview, then advance", time: "0:30",
    speak: "(없음. 그림이 만들어지는 동안 영어로 계속 설명합니다.)",
    meaning: "",
    point_en: "\"This blurry picture is the model's current guess of the clean image, x-hat-zero, at each step. ... Now it's ready, so I advance, and the audience sees it.\" Press →.",
    point_ko: "\"이 흐린 그림이 매 스텝 모델이 예측한 깨끗한 그림 x̂₀입니다. … 준비됐으니 넘기면 청중 화면에도 나타납니다.\" → 키.",
  },
  {
    step: "4. Negation: ignored", time: "0:20",
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
    a_ko: "제가 넘기기 전에는 청중이 새 장을 보지 못합니다. 발표자 미리보기에서 제목과 본문을 고치거나, 그림을 다시 만들거나, 작업을 취소할 수 있습니다.",
  },
  {
    q_en: "How fast and how expensive is it?", q_ko: "속도와 비용은 어느 정도인가요?",
    a_en: "With local SD-Turbo: about 6 seconds from request to finished slide, and the image itself took 1.2 seconds (single measurement). The planner LLM costs about 0.02 to 0.04 cents per slide, and local images are free. With the gpt-image-2 API it was about 20 seconds and about 0.45 cents per image.",
    a_ko: "로컬 SD-Turbo 기준으로 요청부터 완성까지 약 6초, 그림만 1.2초였습니다(1회 측정). 기획 LLM 비용은 장당 약 $0.0002~0.0004이고 로컬 그림은 무료입니다. gpt-image-2 API로는 약 20초, 그림당 약 $0.0045였습니다.",
  },
  {
    q_en: "How does the denoising preview work?", q_ko: "디노이징 미리보기는 어떻게 동작하나요?",
    a_en: "At each step the scheduler already computes the predicted clean sample, x-hat-zero equals x_t minus the square root of one minus alpha-bar times the predicted noise, divided by the square root of alpha-bar. I capture it, project the 4 latent channels to RGB with a fixed linear matrix, and send a small JPEG over WebSocket. No VAE decoding is needed.",
    a_ko: "스케줄러가 매 스텝 이미 계산하는 x̂₀ = (x_t − √(1−ᾱ_t) ε̂) / √ᾱ_t 를 가로챕니다. 잠재 4채널을 고정 선형 행렬로 RGB에 투영하고, 작은 JPEG로 WebSocket을 통해 보냅니다. VAE 디코딩이 필요 없습니다.",
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

function notesFor(i) {
  const s = SCRIPT[i];
  let n = `[${timeOf(s)}] ${s.en}\n\n[KO] ${s.ko}`;
  if (s.title === "Live demo") {
    n += "\n\n" + DEMO.map((d) => `${d.step} (${d.time})\nSPEAK (KO): ${d.speak}${d.meaning ? `\n(= ${d.meaning})` : ""}\nEN: ${d.point_en}\n[KO] ${d.point_ko}`).join("\n\n");
  }
  return n;
}

// ───────────────────────── 덱 ─────────────────────────
// X4 시나리오별 B−A (CLIP 점수 차). 출처: eval/results/diffusion/x4_context_n42/summary.md (그림이 A와 B 모두 있는 28개)
const X4_DIFF = {
  L01: 1.43, L02: -0.01, L05: 3.24, L06: 10.78, L07: -0.16, L08: -3.03, L11: 1.51, L12: 1.75, L13: 4.89, L15: -3.98,
  L16: 3.98, L17: -5.0, L18: -0.21, L19: 2.84, L21: -0.65, L23: 2.16, L24: 6.21, L26: 9.62, L28: 6.72, L29: 4.96,
  L30: -1.53, S01: 0.27, S02: 1.57, S03: 1.97, S04: -0.2, S07: -0.26, S09: 10.82, S12: -0.9,
};

async function build() {
  const pres = new pptxgen();
  pres.layout = "LAYOUT_WIDE"; // 13.333 x 7.5
  pres.title = "NextSlide: Speak the Next Slide";
  pres.subject = "Generative AI final project";
  pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
  const C = pres.SchemeColor;
  const W = 13.333, M = 0.9, CW = W - 2 * M;

  // ── 레이아웃 ──
  const footer = (color) => [
    { text: { text: "NextSlide", options: { x: M, y: 6.95, w: 3, h: 0.25, fontFace: F.EB, fontSize: 9, color, margin: 0 } } },
  ];
  pres.defineSlideMaster({ title: "TITLE", background: { color: "FFFFFF" }, objects: [] });
  pres.defineSlideMaster({
    title: "CONTENT",
    background: { color: "FFFFFF" },
    objects: [
      ...footer(H.accent4),
      { placeholder: { options: { name: "title", type: "title", x: M, y: 0.85, w: CW, h: 0.85, fontFace: F.H, fontSize: 34, color: C.text1, valign: "middle", align: "left", margin: 0 }, text: "" } },
    ],
    slideNumber: { x: W - M - 0.6, y: 6.95, w: 0.6, h: 0.25, fontFace: F.B, fontSize: 9, color: H.accent4, align: "right", margin: 0 },
  });
  pres.defineSlideMaster({
    title: "STATEMENT",
    background: { color: "FFFFFF" },
    objects: [
      ...footer(H.accent4),
      { placeholder: { options: { name: "title", type: "title", x: M, y: 2.0, w: CW, h: 2.4, fontFace: F.H, fontSize: 40, color: C.text1, valign: "middle", align: "left", margin: 0 }, text: "" } },
    ],
    slideNumber: { x: W - M - 0.6, y: 6.95, w: 0.6, h: 0.25, fontFace: F.B, fontSize: 9, color: H.accent4, align: "right", margin: 0 },
  });
  pres.defineSlideMaster({
    title: "BLUE",
    background: { color: H.accent1 },
    objects: [
      ...footer("A9C1E3"),
      { placeholder: { options: { name: "title", type: "title", x: M, y: 0.85, w: CW, h: 1.1, fontFace: F.H, fontSize: 48, color: "FFFFFF", valign: "middle", align: "left", margin: 0 }, text: "" } },
    ],
    slideNumber: { x: W - M - 0.6, y: 6.95, w: 0.6, h: 0.25, fontFace: F.B, fontSize: 9, color: "A9C1E3", align: "right", margin: 0 },
  });

  // ── 공통 요소 ──
  const T = (s, t, o) => s.addText(t, { isTextBox: true, margin: 0, fontFace: F.B, fontSize: 18, color: C.text1, valign: "top", ...o });
  // 실험 장과 부록에만 붙이는 작은 표시(예: "Q1 setup"). 대문자나 자간 벌리기는 쓰지 않는다.
  const tag = (s, t, color = C.accent1) => T(s, t, { x: M, y: 0.45, w: 9, h: 0.35, fontFace: F.EB, fontSize: 15, color, objectName: "Section tag" });
  const shadow = () => ({ type: "outer", color: "1E2430", blur: 12, offset: 3, angle: 90, opacity: 0.14 });
  const img = (s, file, x, y, w, h, alt, name, opt = {}) => {
    s.addImage({ path: A(file), x, y, w, h, altText: alt, objectName: name });
    s.addShape(pres.shapes.RECTANGLE, { x, y, w, h, fill: { type: "none" }, line: { color: H.accent6, width: 0.75 }, objectName: name + " frame", ...(opt.shadow ? { shadow: shadow() } : {}) });
  };
  const arrow = (s, x, y, w, color = H.accent4, width = 2) =>
    s.addShape(pres.shapes.LINE, { x, y, w, h: 0, line: { color, width, endArrowType: "triangle" }, objectName: "Arrow" });
  const xhat = (o = {}) => ({ text: "x̂₀", options: { fontFace: F.MATH, ...o } });
  const chartBase = () => ({
    showTitle: false, catAxisLabelColor: H.dk2, valAxisLabelColor: H.accent4, catAxisLabelFontSize: 13, valAxisLabelFontSize: 11,
    catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt",
    valGridLine: { color: "EDF0F4", size: 0.75 }, catGridLine: { style: "none" },
    showLegend: false, showValue: true, dataLabelColor: H.dk1, dataLabelFontSize: 13, dataLabelFontFace: "+mj-lt",
    catAxisLineShow: true, catAxisLineColor: H.accent6, valAxisLineShow: false,
  });

  // 실험 설정 장: 논문의 실험 설정 표처럼 왼쪽에 항목, 오른쪽에 내용을 한 줄씩 적는다.
  // rows: [[항목, [[굵은 글, 이어지는 설명], ...]], ...]  설명은 앞의 쉼표나 괄호까지 포함해서 적는다.
  const setupRows = (s, rows, y0 = 2.05, lineH = 0.46, padH = 0.28) => {
    let y = y0;
    const rule = (yy, name) => s.addShape(pres.shapes.LINE, { x: M, y: yy, w: CW, h: 0, line: { color: H.accent6, width: 1 }, objectName: name });
    rows.forEach(([head, lines]) => {
      rule(y, head + " rule");
      T(s, head, { x: M, y: y + padH / 2, w: 2.3, h: lineH, fontFace: F.EB, fontSize: 18, color: C.accent1, valign: "middle" });
      lines.forEach(([b, l], i) =>
        T(s, [{ text: b, options: { fontFace: F.EB } }, ...(l ? [{ text: l, options: { fontFace: F.L, fontSize: 16, color: C.text2 } }] : [])],
          { x: M + 2.6, y: y + padH / 2 + i * lineH, w: CW - 2.6, h: lineH, fontSize: 19, valign: "middle" }));
      y += lines.length * lineH + padH;
    });
    rule(y, "Bottom rule");
    return y;
  };

  let n = 0;
  const S = (layout, section) => {
    const s = pres.addSlide({ masterName: layout, sectionTitle: section });
    s.addNotes(notesFor(n));
    n += 1;
    return s;
  };

  // 1. 표지
  pres.addSection({ title: "Opening" });
  {
    const s = S("TITLE", "Opening");
    s.addShape(pres.shapes.RECTANGLE, { x: 7.75, y: 0, w: W - 7.75, h: 7.5, fill: { color: H.accent5 }, line: { type: "none" }, objectName: "Right panel" });
    s.addText("NextSlide", { x: M, y: 2.1, w: 6.4, h: 1.25, fontFace: F.H, fontSize: 66, color: C.text1, margin: 0, valign: "middle", isTextBox: true, objectName: "Title" });
    T(s, [{ text: "Say what the next slide should show.", options: { breakLine: true } }, { text: "It appears while you keep talking." }],
      { x: M, y: 3.5, w: 6.3, h: 1.2, fontFace: F.L, fontSize: 22, color: C.text2, lineSpacingMultiple: 1.2 });
    T(s, "Generative AI final project, Fall 2026", { x: M, y: 6.4, w: 6, h: 0.35, fontFace: F.B, fontSize: 14, color: C.text2 });
    const iw = 5.7, ih = iw * 9 / 16;
    img(s, "real_v2_illustration.jpg", 6.85, 2.05, iw, ih, "A slide made by NextSlide: a learning rate that is too large, shown as a hiker overshooting the valley", "Generated slide example", { shadow: true });
    T(s, "A slide NextSlide made", { x: 6.85, y: 2.05 + ih + 0.18, w: iw, h: 0.3, fontSize: 12, color: C.text2 });
  }

  // 2. 즉석 비유
  pres.addSection({ title: "Problem" });
  {
    const s = S("STATEMENT", "Problem");
    s.addText("“Overfitting is like a student who memorized the answers to old exams.”", { placeholder: "title" });
    T(s, "An analogy I might come up with in the middle of a lecture", { x: M, y: 4.6, w: CW, h: 0.45, fontFace: F.L, fontSize: 20, color: C.text2 });
  }

  // 3. 그 장이 없다
  {
    const s = S("CONTENT", "Problem");
    s.addText("But there's no slide for it", { placeholder: "title" });
    const bw = 3.0, bh = bw * 9 / 16, gap = 0.6, x0 = (W - 3 * bw - 2 * gap) / 2, y = 2.55;
    [["Slide 4", false], ["?", true], ["Slide 5", false]].forEach(([l, missing], i) => {
      const x = x0 + i * (bw + gap);
      if (missing) {
        s.addShape(pres.shapes.RECTANGLE, { x, y, w: bw, h: bh, fill: { color: "FFFFFF" }, line: { color: H.accent2, width: 2, dashType: "dash" }, objectName: "Missing slide" });
        T(s, l, { x, y, w: bw, h: bh, fontFace: F.H, fontSize: 60, color: C.accent2, align: "center", valign: "middle" });
      } else {
        s.addShape(pres.shapes.RECTANGLE, { x, y, w: bw, h: bh, fill: { color: H.lt2 }, line: { type: "none" }, objectName: l });
        T(s, l, { x, y, w: bw, h: bh, fontSize: 20, color: C.text2, align: "center", valign: "middle" });
      }
    });
    arrow(s, x0, y + bh + 0.45, 3 * bw + 2 * gap);
    T(s, "prepared before class", { x: x0, y: y + bh + 0.6, w: 4, h: 0.3, fontFace: F.L, fontSize: 14, color: C.text2 });
    T(s, "the analogy", { x: x0 + bw + gap, y: y + bh + 0.6, w: bw, h: 0.3, fontFace: F.EB, fontSize: 14, color: C.accent2, align: "center" });
    T(s, "Making one now means stopping the lecture.", { x: M, y: 5.75, w: CW, h: 0.5, fontSize: 22, align: "center" });
  }

  // 4. 그냥 말한다
  pres.addSection({ title: "Idea" });
  {
    const s = S("CONTENT", "Idea");
    s.addText("With NextSlide, you just say it", { placeholder: "title" });
    T(s, "What I said, in Korean", { x: M, y: 2.0, w: CW, h: 0.35, fontSize: 15, color: C.text2 });
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: M, y: 2.45, w: CW, h: 2.1, rectRadius: 0.2, fill: { color: H.accent5 }, line: { type: "none" }, objectName: "What I said" });
    T(s, [{ text: "다음 슬라이드에서는 과적합을 시험 문제를", options: { breakLine: true } }, { text: "외운 학생에 비유해서 설명하겠습니다." }],
      { x: M + 0.45, y: 2.45, w: CW - 0.9, h: 2.1, fontFace: F.EB, fontSize: 30, valign: "middle", lineSpacingMultiple: 1.25 });
    T(s, "“In the next slide, I'll explain overfitting by comparing it to a student who memorized the exam questions.”",
      { x: M, y: 4.8, w: CW, h: 0.8, fontFace: F.L, fontSize: 18, color: C.text2 });
  }

  // 5. 만들어진 장
  {
    const s = S("CONTENT", "Idea");
    s.addText("And this is the slide it made", { placeholder: "title" });
    const iw = 7.9, ih = iw * 9 / 16, x = (W - iw) / 2;
    img(s, "scene_overfit.jpg", x, 1.95, iw, ih, "The slide NextSlide made: overfitting explained as a student who memorized exam questions, with a title, three points and a picture", "Generated slide", { shadow: true });
    T(s, "Real output from the real APIs. The slide text is in Korean.", { x, y: 1.95 + ih + 0.15, w: iw, h: 0.3, fontSize: 12, color: C.text2, align: "center" });
  }

  // 6. 세 단계
  pres.addSection({ title: "System" });
  {
    const s = S("CONTENT", "System");
    s.addText("It works in three steps", { placeholder: "title" });
    // 상자 세 개를 화살표로 잇는 단순한 흐름도. 가운데(판단)만 파랑으로 칠한다.
    const items = [
      ["1", "Listen", "My speech becomes text while I talk"],
      ["2", "Decide", "Did I ask for a slide? Rules check each sentence"],
      ["3", "Make", "An LLM writes the slide, an image model draws the picture"],
    ];
    const bw = 3.25, ga = (CW - 3 * bw) / 2, by = 2.35, bh = 2.6;
    items.forEach(([no, name, what], i) => {
      const x = M + i * (bw + ga), hi = i === 1;
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: by, w: bw, h: bh, rectRadius: 0.15, fill: { color: hi ? H.accent1 : H.lt2 }, line: { type: "none" }, objectName: "Step " + no });
      T(s, [{ text: no + "  ", options: { color: hi ? "A9C1E3" : H.accent4 } }, { text: name }],
        { x: x + 0.35, y: by + 0.35, w: bw - 0.7, h: 0.6, fontFace: F.H, fontSize: 28, color: hi ? "FFFFFF" : C.text1 });
      T(s, what, { x: x + 0.35, y: by + 1.1, w: bw - 0.7, h: 1.2, fontSize: 18, color: hi ? "FFFFFF" : C.text1, lineSpacingMultiple: 1.15 });
      if (i < 2) arrow(s, x + bw + 0.12, by + bh / 2, ga - 0.24, H.accent4, 2);
    });
    T(s, "Korean speech-to-text, a rule-based detector, a planner LLM and a diffusion model (or an image API)",
      { x: M, y: 5.35, w: CW, h: 0.4, fontFace: F.L, fontSize: 15, color: C.text2 });
  }

  // 7. 분명한 요청에만
  {
    const s = S("CONTENT", "System");
    s.addText("It reacts only to clear requests", { placeholder: "title" });
    // 표처럼: 왼쪽에 한 말(번역), 오른쪽에 결과. 줄 사이는 얇은 선.
    const rows = [
      [true, "“In the next slide, show a decision-tree example.”", "slide made"],
      [false, "“Don't make the next slide.”", "ignored"],
      [false, "“If you say ‘next slide…’, it makes one.”", "ignored (a quote)"],
    ];
    const rx = 9.6;
    T(s, "What I say (translated from Korean)", { x: M, y: 2.05, w: 7, h: 0.35, fontSize: 14, color: C.text2 });
    T(s, "What happens", { x: rx, y: 2.05, w: W - M - rx, h: 0.35, fontSize: 14, color: C.text2 });
    rows.forEach(([ok, said, res], i) => {
      const y = 2.5 + i * 0.95;
      s.addShape(pres.shapes.LINE, { x: M, y, w: CW, h: 0, line: { color: H.accent6, width: 1 }, objectName: "Row rule " + (i + 1) });
      T(s, said, { x: M, y: y + 0.1, w: rx - M - 0.3, h: 0.75, fontSize: 21, valign: "middle", color: ok ? C.text1 : C.text2 });
      T(s, res, { x: rx, y: y + 0.1, w: W - M - rx, h: 0.75, fontFace: F.EB, fontSize: 20, valign: "middle", color: ok ? C.accent1 : H.accent4 });
    });
    s.addShape(pres.shapes.LINE, { x: M, y: 2.5 + 3 * 0.95, w: CW, h: 0, line: { color: H.accent6, width: 1 }, objectName: "Row rule end" });
    T(s, "On 60 test sentences it was right 56 times and never missed a real request.",
      { x: M, y: 5.85, w: CW, h: 0.4, fontFace: F.L, fontSize: 16, color: C.text2 });
  }

  // 8. 발표자가 먼저
  {
    const s = S("CONTENT", "System");
    s.addText("You see it first", { placeholder: "title" });
    const iw = 4.65, ih = iw * 672 / 796;
    img(s, "preview_text_first.jpg", M + 0.2, 1.95, iw, ih, "Presenter preview: the title and points are ready while the picture is still being generated", "Presenter preview", { shadow: true });
    const lines = ["The text appears right away", "The picture follows", "The audience sees it when you advance"];
    lines.forEach((l, i) => {
      const y = 2.35 + i * 1.15;
      T(s, String(i + 1), { x: 6.6, y, w: 0.6, h: 0.6, fontFace: F.H, fontSize: 30, color: C.accent1, valign: "middle" });
      T(s, l, { x: 7.3, y, w: 5.2, h: 0.6, fontSize: 22, valign: "middle", color: i === 2 ? C.accent1 : C.text1, fontFace: i === 2 ? F.EB : F.B });
    });
  }

  // 9. 직전에 한 말
  {
    const s = S("CONTENT", "Idea");
    s.addText("It also listens to what you said before", { placeholder: "title" });
    T(s, "From one of my test scenarios, a history lesson (translated)", { x: 2.6, y: 1.9, w: 9, h: 0.35, fontSize: 14, color: C.text2 });
    const said = [
      "Joseon's civil service exam selected government officials.",
      "Today we're following a scholar on his way to Hanyang to take it.",
      "After walking for days, the scholar arrives in Hanyang.",
    ];
    said.forEach((t, i) => {
      const y = 2.4 + i * 0.72;
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 2.6, y, w: 8.2, h: 0.58, rectRadius: 0.12, fill: { color: H.lt2 }, line: { type: "none" }, objectName: "Earlier speech " + (i + 1) });
      T(s, t, { x: 2.85, y, w: 7.8, h: 0.58, fontFace: F.L, fontSize: 17, color: C.text2, valign: "middle" });
    });
    // 직전 90초 묶음 표시
    s.addShape(pres.shapes.LEFT_BRACE, { x: 2.2, y: 2.4, w: 0.25, h: 2.02, fill: { type: "none" }, line: { color: H.accent4, width: 1.25 }, objectName: "Last 90 s brace" });
    T(s, [{ text: "last 90 s", options: { breakLine: true } }, { text: "+ current slide", options: { fontSize: 12, fontFace: F.B } }],
      { x: M - 0.35, y: 3.0, w: 1.5, h: 0.75, fontSize: 16, fontFace: F.H, color: C.text2, align: "right" });
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 2.6, y: 4.75, w: 8.2, h: 0.8, rectRadius: 0.14, fill: { color: H.accent1 }, line: { type: "none" }, objectName: "The request" });
    T(s, "“In the next slide, show the exam hall scene.”", { x: 2.85, y: 4.75, w: 7.8, h: 0.8, fontFace: F.EB, fontSize: 21, color: "FFFFFF", valign: "middle" });
    T(s, "the request", { x: M - 0.35, y: 4.95, w: 1.5, h: 0.4, fontSize: 16, fontFace: F.H, color: C.accent1, align: "right" });
  }

  // 10. 같은 요청, 다른 그림
  {
    const s = S("CONTENT", "Idea");
    s.addText("Same request, different picture", { placeholder: "title" });
    const g = 0.45, iw = (CW - g) / 2, ih = iw * 9 / 16, y = 2.45;
    T(s, "Request only", { x: M, y: 1.95, w: iw, h: 0.4, fontFace: F.H, fontSize: 18, color: C.text2 });
    T(s, "With the lecture before it", { x: M + iw + g, y: 1.95, w: iw, h: 0.4, fontFace: F.H, fontSize: 18, color: C.accent1 });
    img(s, "s09_request_only.jpg", M, y, iw, ih, "Image from the request only: a modern classroom", "Request only image");
    img(s, "s09_with_context.jpg", M + iw + g, y, iw, ih, "Image with the lecture context: a Joseon-era civil service exam ground", "With context image");
    s.addShape(pres.shapes.RECTANGLE, { x: M + iw + g, y, w: iw, h: ih, fill: { type: "none" }, line: { color: H.accent1, width: 3 }, objectName: "Highlight frame" });
    T(s, "a modern classroom", { x: M, y: y + ih + 0.2, w: iw, h: 0.4, fontSize: 19, color: C.text2 });
    T(s, "the Joseon-era exam the teacher meant", { x: M + iw + g, y: y + ih + 0.2, w: iw, h: 0.4, fontFace: F.EB, fontSize: 19, color: C.accent1 });
  }

  // 11. 그림이 필요할 때만
  {
    const s = S("CONTENT", "System");
    s.addText("A picture only when a picture helps", { placeholder: "title" });
    T(s, "Image models still get text and numbers wrong (Lecture 17), so the kind of slide is chosen first.", { x: M, y: 1.85, w: CW, h: 0.45, fontFace: F.L, fontSize: 18, color: C.text2 });
    const shots = [["real_v2_illustration.jpg", "Illustration", "image model"], ["real_v2_equation_gd.jpg", "Equation", "KaTeX"], ["real_v4_comparison.jpg", "Comparison", "fixed layout"]];
    const g = 0.4, iw = (CW - 2 * g) / 3, ih = iw * 9 / 16, y = 2.75;
    shots.forEach((sh, i) => {
      const x = M + i * (iw + g);
      img(s, sh[0], x, y, iw, ih, sh[1] + " slide made by NextSlide", sh[1] + " example");
      T(s, [{ text: sh[1], options: { fontFace: F.H, fontSize: 20, breakLine: true } }, { text: sh[2], options: { fontFace: F.L, fontSize: 15, color: C.text2 } }],
        { x, y: y + ih + 0.2, w: iw, h: 0.8 });
    });
  }

  // 12. 시연
  {
    const s = S("BLUE", "System");
    s.addText("Live demo", { placeholder: "title" });
    T(s, "Watch for four things", { x: M, y: 2.0, w: 8, h: 0.4, fontFace: F.L, fontSize: 20, color: "D6E2F3" });
    // 왼쪽: 내가 하는 것, 오른쪽: 기대하는 결과
    const rows = [
      ["I explain something", "nothing happens"],
      ["I ask for a slide", "the text appears first"],
      ["The picture forms step by step", ""],
      ["I say “don't make it”", "nothing happens"],
    ];
    rows.forEach(([act, res], i) => {
      const y = 2.75 + i * 0.85;
      T(s, String(i + 1), { x: M, y, w: 0.5, h: 0.64, fontFace: F.H, fontSize: 26, color: "A9C1E3", valign: "middle" });
      T(s, act, { x: M + 0.6, y, w: 6.2, h: 0.64, fontFace: F.EB, fontSize: 26, color: "FFFFFF", valign: "middle" });
      if (res) T(s, res, { x: 7.45, y, w: W - M - 7.45, h: 0.64, fontFace: F.L, fontSize: 24, color: "D6E2F3", valign: "middle" });
    });
    T(s, "I'll speak in Korean and translate as I go. A recorded backup video is ready.", { x: M, y: 6.25, w: CW, h: 0.35, fontFace: F.L, fontSize: 14, color: "D6E2F3" });
  }

  // 13. 확산 모델이 그리는 과정
  pres.addSection({ title: "Experiments" });
  {
    const s = S("CONTENT", "Experiments");
    s.addText("Watch the diffusion model draw", { placeholder: "title" });
    T(s, "The scene is the overfitting analogy from the demo.",
      { x: M, y: 1.78, w: CW, h: 0.35, fontFace: F.L, fontSize: 16, color: C.text2 });
    // 그림 4칸: 실제 생성에서 가로챈 x̂₀ 미리보기(1, 3, 6단계, 시스템과 같은 잠재→RGB 근사)와 최종 그림. 칸 640px, 간격 24px.
    const sw = CW, sh = sw * 360 / 2632, y = 2.3;
    s.addImage({ path: A("denoise_strip.jpg"), x: M, y, w: sw, h: sh, altText: "The model's guess of the final image at steps 1, 3 and 6 of 25, and the final image: a student with stacks of exam papers", objectName: "Denoising strip" });
    const pw = sw * 664 / 2632;
    ["step 1 of 25", "step 3", "step 6", "final image"].forEach((l, i) =>
      T(s, l, { x: M + i * pw, y: y + sh + 0.15, w: pw - 0.1, h: 0.35, fontFace: F.EB, fontSize: 16, color: i === 3 ? C.accent1 : C.text2, align: "center" }));
    arrow(s, M, y + sh + 0.7, sw);
    T(s, [{ text: "At each step the model predicts the final image, " }, xhat(), { text: ", and the preview shows it." }],
      { x: M, y: 4.85, w: CW, h: 0.5, fontSize: 20, align: "center" });
    const m = (t, o = {}) => ({ text: t, options: { fontFace: F.MATH, ...o } });
    T(s, [m("x̂₀ = ( x"), m("t", { subscript: true }), m(" − √(1 − ᾱ"), m("t", { subscript: true }), m(") ε̂ ) / √ᾱ"), m("t", { subscript: true }),
      { text: "      from Lecture 17, “Estimate clean image”", options: { fontFace: F.L, fontSize: 14, color: C.text2 } }],
      { x: M, y: 5.45, w: CW, h: 0.45, fontSize: 18, color: C.text1, align: "center", valign: "middle" });
    T(s, "Stable Diffusion 1.5 with DDIM, 25 steps, about 11 s on my laptop. All four frames come from one real run.", { x: M, y: 6.1, w: CW, h: 0.35, fontFace: F.L, fontSize: 14, color: C.text2, align: "center" });
  }

  // 14. 세 질문
  {
    const s = S("CONTENT", "Experiments");
    s.addText("Three questions", { placeholder: "title" });
    ["Is it fast enough for a live lecture?", "What does guidance change?", "Does the lecture context help?"].forEach((q, i) => {
      const y = 2.25 + i * 1.25;
      T(s, String(i + 1), { x: M, y, w: 0.9, h: 0.95, fontFace: F.H, fontSize: 48, color: C.accent1, valign: "middle" });
      T(s, q, { x: M + 1.0, y, w: 10.5, h: 0.95, fontFace: F.EB, fontSize: 30, valign: "middle", color: i === 2 ? C.accent1 : C.text1 });
    });
  }

  // 15. Q1 실험 설정
  {
    const s = S("CONTENT", "Experiments");
    tag(s, "Q1 setup");
    s.addText("Two models draw the same 12 lecture scenes", { placeholder: "title" });
    setupRows(s, [
      ["Models", [["Stable Diffusion 1.5", ", 25 DDIM steps, guidance 7.5"], ["SD-Turbo", ", a distilled model that needs only 2 steps"]]],
      ["Data", [["12 lecture scenes I wrote", " (overfitting, GAN, attention and so on)"], ["2 seeds per scene", ", so 24 images per model at 768 × 432"]]],
      ["Measured", [["Seconds per image", ", median of 24 on my laptop (Apple M5, 16 GB)"], ["CLIP score", ", how well the picture matches the scene sentence"]]],
    ]);
    T(s, "Only the model changes. The scenes, seeds and image size are the same for both.", { x: M, y: 5.95, w: CW, h: 0.4, fontFace: F.L, fontSize: 16, color: C.text2 });
  }

  // 16. Q1 속도
  {
    const s = S("CONTENT", "Experiments");
    tag(s, "Q1 result");
    s.addText("SD-Turbo makes a picture in under a second", { placeholder: "title" });
    s.addChart(pres.charts.BAR, [{ name: "Seconds per image", labels: ["Stable Diffusion 1.5 (25 steps)", "SD-Turbo (2 steps)"], values: [11.1, 0.68] }], {
      x: M, y: 2.2, w: 7.4, h: 3.1, ...chartBase(), barDir: "bar",
      chartColors: [H.accent4, H.accent1], dataLabelPosition: "outEnd", dataLabelFormatCode: "0.0#\" s\"", dataLabelFontSize: 18,
      valAxisHidden: true, valAxisMinVal: 0, valAxisMaxVal: 14, valGridLine: { style: "none" }, barGapWidthPct: 45, catAxisOrientation: "maxMin", catAxisLabelFontSize: 14,
      objectName: "Seconds per image",
    });
    T(s, "seconds per image on my laptop", { x: M, y: 5.35, w: 7.4, h: 0.3, fontFace: F.L, fontSize: 13, color: C.text2, align: "center" });
    T(s, "16×", { x: 8.9, y: 2.2, w: 3.6, h: 1.3, fontFace: F.H, fontSize: 80, color: C.accent1, valign: "middle" });
    T(s, [{ text: "faster with SD-Turbo,", options: { breakLine: true } }, { text: "a distilled model" }], { x: 8.9, y: 3.55, w: 3.6, h: 0.9, fontSize: 20 });
    T(s, [{ text: "The CLIP score also rose,", options: { fontFace: F.L, color: C.text2, breakLine: true } }, { text: "from 25.0 to 28.2", options: { fontFace: F.EB } }],
      { x: 8.9, y: 4.7, w: 3.6, h: 0.7, fontSize: 15, lineSpacingMultiple: 1.15 });
    T(s, "About 6 s from my sentence to a finished slide (one test run)", { x: M, y: 6.0, w: CW, h: 0.4, fontFace: F.L, fontSize: 16, color: C.text2 });
  }

  // 17. Q2 실험 설정
  {
    const s = S("CONTENT", "Experiments");
    tag(s, "Q2 setup");
    s.addText("Change only the guidance scale", { placeholder: "title" });
    setupRows(s, [
      ["Model", [["Stable Diffusion 1.5", ", 25 DDIM steps"]]],
      ["Data", [["The same 12 scenes and 2 seeds", " as in Q1"]]],
      ["Changed", [["Guidance scale 1, 3, 5, 7.5 and 12", " (classifier-free guidance)"]]],
      ["Measured", [["CLIP score", ", how well the picture matches the scene sentence"], ["Variety", ", how different the two seeds' pictures are (1 − cosine)"]]],
    ]);
    T(s, [{ text: "Expected from Lecture 17: ", options: { fontFace: F.EB, color: C.text1 } }, { text: "stronger guidance follows the condition more, but variety drops." }],
      { x: M, y: 5.95, w: CW, h: 0.4, fontFace: F.L, fontSize: 16, color: C.text2 });
  }

  // 18. Q2 그림
  {
    const s = S("CONTENT", "Experiments");
    tag(s, "Q2 results");
    s.addText("Higher guidance follows the prompt more", { placeholder: "title" });
    const g = 0.25, iw = (CW - 3 * g) / 4, ih = iw * 9 / 16, y = 2.35;
    [["cfg_1.jpg", "1"], ["cfg_3.jpg", "3"], ["cfg_7_5.jpg", "7.5"], ["cfg_12.jpg", "12"]].forEach(([f, l], i) => {
      const x = M + i * (iw + g);
      img(s, f, x, y, iw, ih, "Stable Diffusion 1.5 image of a hiker walking down a foggy valley at guidance scale " + l, "Guidance " + l);
      T(s, l, { x, y: y + ih + 0.15, w: iw, h: 0.5, fontFace: F.H, fontSize: 26, color: i >= 2 ? C.accent1 : C.text2, align: "center" });
    });
    arrow(s, M, y + ih + 0.85, CW);
    T(s, "guidance scale", { x: M, y: y + ih + 0.95, w: CW, h: 0.3, fontFace: F.L, fontSize: 14, color: C.text2, align: "right" });
    T(s, "Prompt: “a hiker walking down a foggy valley”, with the same seed in all four", { x: M, y: 5.65, w: CW, h: 0.35, fontFace: F.L, fontSize: 15, color: C.text2 });
  }

  // 19. Q2 트레이드오프
  {
    const s = S("CONTENT", "Experiments");
    tag(s, "Q2 results");
    s.addText("But the pictures become less varied", { placeholder: "title" });
    const labels = ["1", "3", "5", "7.5", "12"];
    const line = (min, max, fmt, color) => ({
      ...chartBase(), chartColors: [color], lineSize: 3, lineDataSymbol: "circle", lineDataSymbolSize: 9,
      dataLabelPosition: "t", dataLabelFontSize: 12, valAxisMinVal: min, valAxisMaxVal: max, dataLabelFormatCode: fmt, valAxisLabelFormatCode: fmt,
      valAxisHidden: true, valGridLine: { style: "none" }, catAxisLabelFontSize: 13,
    });
    const cw = (CW - 0.6) / 2;
    T(s, "CLIP score", { x: M, y: 1.95, w: cw, h: 0.4, fontFace: F.H, fontSize: 20, color: C.accent1 });
    T(s, "match with the scene rises, then levels off", { x: M, y: 2.35, w: cw, h: 0.35, fontFace: F.L, fontSize: 15, color: C.text2 });
    T(s, "Variety", { x: M + cw + 0.6, y: 1.95, w: cw, h: 0.4, fontFace: F.H, fontSize: 20, color: C.accent2 });
    T(s, "the two seeds' pictures keep getting more alike", { x: M + cw + 0.6, y: 2.35, w: cw, h: 0.35, fontFace: F.L, fontSize: 15, color: C.text2 });
    s.addChart(pres.charts.LINE, [{ name: "Prompt match (CLIP)", labels, values: [21.5, 24.6, 25.7, 25.0, 25.6] }],
      { x: M, y: 2.85, w: cw, h: 2.9, ...line(20, 27, "0.0", H.accent1), objectName: "Guidance vs prompt match" });
    s.addChart(pres.charts.LINE, [{ name: "Variety (1 - cosine)", labels, values: [0.269, 0.209, 0.213, 0.182, 0.177] }],
      { x: M + cw + 0.6, y: 2.85, w: cw, h: 2.9, ...line(0.15, 0.29, "0.00", H.accent2), objectName: "Guidance vs variety" });
    T(s, "Guidance scale on the x-axis. Averages over 12 scenes and 2 seeds. CLIP measures prompt match, not quality.", { x: M, y: 6.0, w: CW, h: 0.35, fontFace: F.L, fontSize: 14, color: C.text2 });
  }

  // 20. Q3 시험 데이터
  {
    const s = S("CONTENT", "Experiments");
    tag(s, "Q3 test data");
    s.addText("42 lecture scenarios as test data", { placeholder: "title" });
    // 왼쪽: 시나리오 한 개의 구성(L06, 이 수업 '확산 모델 I' 강의 기반, 한국어를 번역)
    const cx = M, cw = 8.0, cy = 2.35;
    T(s, "One scenario, from the lecture “Diffusion Models I” (translated)", { x: cx, y: 1.92, w: cw, h: 0.35, fontSize: 14, color: C.text2 });
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: cx, y: cy, w: cw, h: 3.9, rectRadius: 0.15, fill: { color: H.lt2 }, line: { type: "none" }, objectName: "Scenario card" });
    const lx = cx + 0.3, vx = cx + 2.05, vw = cw - 2.3;
    const label = (t, y, h) => T(s, t, { x: lx, y, w: 1.7, h, fontFace: F.EB, fontSize: 14, color: C.text2, valign: "middle" });
    label("Said before", 2.55, 0.85);
    T(s, [{ text: "“The forward process adds noise bit by bit.”", options: { breakLine: true } }, { text: "“It's like ink spreading in water until it's even.”" }],
      { x: vx, y: 2.55, w: vw, h: 0.85, fontFace: F.L, fontSize: 15, color: C.text1, valign: "middle", lineSpacingMultiple: 1.25 });
    label("Current slide", 3.55, 0.5);
    T(s, "Forward: adding noise", { x: vx, y: 3.55, w: vw, h: 0.5, fontSize: 16, valign: "middle" });
    label("Request", 4.25, 0.7);
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: vx - 0.15, y: 4.25, w: vw + 0.15, h: 0.7, rectRadius: 0.12, fill: { color: H.accent1 }, line: { type: "none" }, objectName: "The request" });
    T(s, "“Show the reverse process with the same analogy.”", { x: vx, y: 4.25, w: vw - 0.1, h: 0.7, fontFace: F.EB, fontSize: 14, color: "FFFFFF", valign: "middle" });
    label("Intended scene", 5.2, 0.85);
    T(s, [{ text: "spread-out ink gathering back into one drop", options: { fontFace: F.EB, color: C.accent1, breakLine: true } }, { text: "written and committed to git before generating", options: { fontFace: F.L, fontSize: 13, color: C.text2 } }],
      { x: vx, y: 5.2, w: vw, h: 0.85, fontSize: 16, valign: "middle" });
    // 오른쪽: 데이터 구성
    const rx = 9.5, rw = W - M - rx;
    [["30", "based on this course's lectures", C.accent1], ["12", "from other subjects, such as history and biology", C.text2]].forEach(([k, v, col], i) => {
      const y = 2.3 + i * 1.95;
      T(s, k, { x: rx, y, w: rw, h: 0.95, fontFace: F.H, fontSize: 60, color: col, valign: "middle" });
      T(s, v, { x: rx, y: y + 1.0, w: rw, h: 0.7, fontSize: 16, color: C.text1 });
    });
  }

  // 21. Q3 실험 설계 (A/B)
  {
    const s = S("CONTENT", "Experiments");
    tag(s, "Q3 setup");
    s.addText("A and B differ only in the lecture context", { placeholder: "title" });
    const box = (x, y, w, h, fill, lines, name, color = C.text1) => {
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.12, fill: { color: fill }, line: { type: "none" }, objectName: name });
      T(s, lines, { x: x + 0.2, y, w: w - 0.4, h, fontSize: 18, valign: "middle", align: "center", color });
    };
    box(M, 2.55, 2.3, 1.05, H.lt2, [{ text: "the same", options: { breakLine: true } }, { text: "request" }], "Same request");
    box(3.95, 1.95, 4.4, 0.85, H.lt2, [{ text: "A  ", options: { fontFace: F.H } }, { text: "request only" }], "Condition A", C.text2);
    box(3.95, 3.35, 4.4, 0.85, H.accent1, [{ text: "B  ", options: { fontFace: F.H } }, { text: "+ last 90 s + current slide" }], "Condition B", "FFFFFF");
    s.addShape(pres.shapes.LINE, { x: M + 2.4, y: 2.375, w: 0.55, h: 0.7, flipV: true, line: { color: H.accent4, width: 1.5, endArrowType: "triangle" }, objectName: "Arrow to A" });
    s.addShape(pres.shapes.LINE, { x: M + 2.4, y: 3.075, w: 0.55, h: 0.7, line: { color: H.accent4, width: 1.5, endArrowType: "triangle" }, objectName: "Arrow to B" });
    box(9.35, 1.95, W - M - 9.35, 2.25, H.accent5, [{ text: "CLIP similarity to the intended scene", options: { fontFace: F.EB, breakLine: true } }, { text: "for every picture", options: { fontFace: F.L, fontSize: 14, color: C.text2 } }], "Score");
    arrow(s, 8.45, 2.375, 0.8); arrow(s, 8.45, 3.775, 0.8);
    setupRows(s, [
      ["Planner LLM", [["gpt-6-luna (API)", ", the same prompt for A and B"]]],
      ["Image model", [["SD-Turbo, 2 steps", ", seeds 0 and 1 for both"]]],
      ["Test", [["Paired permutation test", " on B − A per scenario, 20,000 sign flips"]]],
    ], 4.6, 0.44, 0.22);
  }

  // 22. Q3 결과
  {
    const s = S("CONTENT", "Experiments");
    tag(s, "Q3 results");
    s.addText("The pictures got closer to the intended scene", { placeholder: "title" });
    T(s, "+2.1", { x: M, y: 2.2, w: 4.0, h: 1.4, fontFace: F.H, fontSize: 88, color: C.accent1, valign: "middle" });
    T(s, [{ text: "CLIP points closer", options: { breakLine: true } }, { text: "on average" }], { x: M, y: 3.7, w: 4.0, h: 0.9, fontSize: 22 });
    T(s, "p = 0.010 (paired permutation test)", { x: M, y: 4.75, w: 4.0, h: 0.35, fontFace: F.L, fontSize: 15, color: C.text2 });
    const ids = Object.keys(X4_DIFF).sort((a, b) => X4_DIFF[b] - X4_DIFF[a]);
    s.addChart(pres.charts.BAR, [{ name: "B minus A", labels: ids, values: ids.map((k) => X4_DIFF[k]) }], {
      x: 5.4, y: 2.0, w: W - M - 5.4, h: 3.9, ...chartBase(), barDir: "col",
      chartColors: [H.accent1], invertedColors: [H.accent4], showValue: false, catAxisHidden: true,
      valAxisMinVal: -6, valAxisMaxVal: 12, valAxisMajorUnit: 3, valAxisLabelFormatCode: "+0;-0;0", barGapWidthPct: 35,
      objectName: "Per-scenario difference",
    });
    T(s, "Each bar is one scenario (B − A). 28 scenarios had a picture in both.", { x: 5.4, y: 5.95, w: W - M - 5.4, h: 0.35, fontFace: F.L, fontSize: 14, color: C.text2, align: "center" });
  }

  // 23. Q3 되묻기
  {
    const s = S("CONTENT", "Experiments");
    tag(s, "Q3 results");
    s.addText("It stopped asking what I meant", { placeholder: "title" });
    // 숫자 두 개를 나란히: 맥락 없음 7번, 맥락 있음 0번 (요청 42개 중)
    const half = CW / 2;
    [["7", "times without the context", C.text2], ["0", "times with the context", C.accent1]].forEach(([k, v, col], i) => {
      const x = M + i * half;
      T(s, k, { x, y: 2.2, w: half - 0.4, h: 1.9, fontFace: F.H, fontSize: 120, color: col, valign: "middle" });
      T(s, v, { x, y: 4.2, w: half - 0.4, h: 0.5, fontFace: F.EB, fontSize: 24, color: i ? C.accent1 : C.text1 });
    });
    s.addShape(pres.shapes.LINE, { x: M + half - 0.4, y: 2.3, w: 0, h: 2.4, line: { color: H.accent6, width: 1 }, objectName: "Divider" });
    T(s, "Out of 42 requests, how often the system had to ask me which scene I wanted", { x: M, y: 5.3, w: CW, h: 0.4, fontFace: F.L, fontSize: 18, color: C.text2 });
  }

  // 24. 한계
  pres.addSection({ title: "Closing" });
  {
    const s = S("CONTENT", "Closing");
    s.addText("The fast model still draws fake text", { placeholder: "title" });
    const iw = 6.3, ih = iw * 9 / 16;
    img(s, "fake_text.jpg", M, 2.05, iw, ih, "SD-Turbo image with fake text: the lines on the papers look like writing but are meaningless", "Fake text example");
    const rx = 7.75, rw = W - M - rx;
    T(s, "About 9 of 34", { x: rx, y: 2.05, w: rw, h: 0.9, fontFace: F.H, fontSize: 40, color: C.accent2, valign: "middle" });
    T(s, "images had fake text, and rules in the prompt didn't fix it.", { x: rx, y: 3.0, w: rw, h: 0.75, fontSize: 18 });
    T(s, "Next step", { x: rx, y: 4.2, w: rw, h: 0.35, fontFace: F.EB, fontSize: 16, color: C.accent1 });
    T(s, "A blind evaluation by people. So far CLIP is my only judge.", { x: rx, y: 4.6, w: rw, h: 0.8, fontSize: 18 });
  }

  // 25. 정리
  {
    const s = S("BLUE", "Closing");
    s.addText([{ text: "Say it, and the next slide is ready", options: { fontSize: 40 } }], { placeholder: "title" });
    T(s, [
      { text: "The lecture itself is a good condition for the picture.", options: { breakLine: true } },
      { text: "The weak spot is still the image model." },
    ], { x: M, y: 2.35, w: CW, h: 1.2, fontFace: F.L, fontSize: 22, color: "E4ECF7", lineSpacingMultiple: 1.35 });
    T(s, "Thank you. Any questions?", { x: M, y: 4.9, w: CW, h: 0.9, fontFace: F.H, fontSize: 40, color: "FFFFFF", valign: "middle" });
  }

  // 부록 1: 기존 도구 비교
  pres.addSection({ title: "Backup" });
  {
    const s = S("CONTENT", "Backup");
    tag(s, "Backup", H.accent4);
    s.addText("Compared with live-staging tools", { placeholder: "title" });
    const hdr = (t, hi) => ({ text: t, options: { fontFace: F.EB, color: hi ? "FFFFFF" : C.text1, fill: { color: hi ? H.accent1 : H.lt2 } } });
    const hi = (t) => ({ text: t, options: { fontFace: F.EB, color: C.accent1 } });
    const lab = (t) => ({ text: t, options: { fontFace: F.EB } });
    s.addTable([
      [hdr(""), hdr("Live-staging tools (e.g. ZeroPrep)"), hdr("NextSlide", true)],
      [lab("What triggers a slide"), "A realtime model interprets every utterance", hi("Only explicit requests")],
      [lab("Who sees it first"), "The audience, immediately", hi("The presenter")],
      [lab("Slide forms"), "Cards, metrics, diagrams", hi("Illustration, equation, comparison, table, chart")],
      [lab("Context used"), "The current utterance", hi("Request + last 90 s + current slide")],
    ], {
      x: M, y: 2.0, w: CW, colW: [2.8, 4.3, CW - 7.1], fontFace: F.B, fontSize: 15, color: C.text1,
      border: { type: "solid", pt: 0.75, color: H.accent6 }, valign: "middle", rowH: [0.55, 0.75, 0.75, 0.75, 0.75], margin: 0.12,
      objectName: "Prior work comparison",
    });
    T(s, "ZeroPrep: github.com/ramsrigouthamg/zeroprep (README and app code read on 2026-11-05)", { x: M, y: 6.0, w: CW, h: 0.3, fontFace: F.L, fontSize: 12, color: C.text2 });
  }

  // 부록 2: 시스템 수치
  {
    const s = S("CONTENT", "Backup");
    tag(s, "Backup", H.accent4);
    s.addText("System numbers", { placeholder: "title" });
    T(s, "56 / 60", { x: M, y: 1.95, w: 3, h: 0.9, fontFace: F.H, fontSize: 44, color: C.accent1, valign: "middle" });
    T(s, [{ text: "detector test sentences right", options: { breakLine: true, fontFace: F.EB } }, { text: "0 missed, 1 false slide, 3 needless “which topic?” questions. I wrote the test set myself.", options: { fontFace: F.L, fontSize: 14, color: C.text2 } }],
      { x: M + 3.0, y: 1.95, w: CW - 3.0, h: 0.9, fontSize: 18, valign: "middle" });
    T(s, "112", { x: M, y: 3.0, w: 3, h: 0.9, fontFace: F.H, fontSize: 44, color: C.accent1, valign: "middle" });
    T(s, [{ text: "automated backend tests", options: { breakLine: true, fontFace: F.EB } }, { text: "mock providers, no API calls", options: { fontFace: F.L, fontSize: 14, color: C.text2 } }],
      { x: M + 3.0, y: 3.0, w: CW - 3.0, h: 0.9, fontSize: 18, valign: "middle" });
    const hdr = (t) => ({ text: t, options: { fontFace: F.EB, fill: { color: H.lt2 } } });
    s.addTable([
      [hdr("End to end, one run each"), hdr("Text ready"), hdr("Image"), hdr("Slide ready")],
      [{ text: "Local SD-Turbo", options: { fontFace: F.EB } }, "5.0 s", "1.2 s", { text: "6.2 s", options: { fontFace: F.EB, color: C.accent1 } }],
      [{ text: "gpt-image-2 API", options: { fontFace: F.EB } }, "5.7 s", "14.3 s", { text: "20.0 s", options: { fontFace: F.EB } }],
    ], {
      x: M, y: 4.25, w: CW, colW: [4.3, 2.4, 2.4, CW - 9.1], fontFace: F.B, fontSize: 15, color: C.text1,
      border: { type: "solid", pt: 0.75, color: H.accent6 }, valign: "middle", rowH: [0.5, 0.55, 0.55], margin: 0.12,
      objectName: "Latency table",
    });
    T(s, "Cost: about $0.0002–0.0004 per slide for the planner LLM and $0.0045 per API image. Local images are free.", { x: M, y: 6.0, w: CW, h: 0.3, fontFace: F.L, fontSize: 13, color: C.text2 });
  }

  // 부록 3: 측정 방법
  {
    const s = S("CONTENT", "Backup");
    tag(s, "Backup", H.accent4);
    s.addText("How the experiments were measured", { placeholder: "title" });
    const b = (t, last) => ({ text: t, options: { bullet: { indent: 18 }, breakLine: !last } });
    T(s, [
      b("Score: CLIP ViT-B/32 cosine similarity × 100, not the generators' own text encoder"),
      b("X1–X3 (Questions 1–2): 12 lecture scenes × 2 fixed seeds, one setting at a time, 95% bootstrap CIs"),
      b("X4 (Question 3): 42 scenarios, 28 with a picture in both A and B; two-sided test, 20,000 sign flips"),
      b("Times: medians on an Apple M5 laptop (16 GB, MPS); first call excluded as warm-up"),
      b("X1: DDPM at 10 steps broke shapes and DDIM didn't, yet CLIP gave 25.5 vs 25.1"),
      b("X3: SD-Turbo is based on SD 2.1 (larger text encoder), so not distillation alone"),
      b("Bug found: prompts over CLIP's 77 tokens lost their style words; fixed"),
      b("Dropped: CLIP as a fake-text detector (1 of its top 6 picks had text)", true),
    ], { x: M, y: 1.95, w: CW, h: 4.7, fontSize: 15, paraSpaceAfter: 8 });
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
  const total = main.reduce((a, s) => a + secondsOf(s), 0);
  const demoNo = SCRIPT.findIndex((s) => s.title === "Live demo") + 1;
  const L = [];
  L.push("# NextSlide 발표 대본 (영어 / 한국어)", "");
  L.push(`발표 파일: [NextSlide_final.pptx](NextSlide_final.pptx). 슬라이드 노트에도 같은 대본이 들어 있습니다. 이 파일과 노트는 \`build_deck.js\`가 함께 만듭니다.`, "");
  L.push(`- 예상 시간: 약 ${Math.floor(total / 60)}분 ${total % 60}초(본문 ${main.length}장, 시연 2분 포함, 영어 대본을 분당 약 140단어로 읽고 장마다 전환 4초를 더한 값). 부록 ${SCRIPT.length - main.length}장은 질문이 나올 때만 씁니다.`);
  L.push(`- 시연을 발표 끝에 하려면 PowerPoint에서 ${demoNo}번 슬라이드(Live demo)를 ${main.length}번(To sum up) 앞으로 옮기면 됩니다. 대본 순서도 같이 옮깁니다.`);
  L.push("- [name] 자리에 이름을 넣어 말하세요. 표지에는 이름이 없으니 필요하면 직접 추가하세요.");
  L.push("- 글꼴: 덱은 나눔스퀘어 네오(NanumSquare Neo, NAVER 무료 글꼴)를 씁니다. 발표할 컴퓨터에 먼저 설치하세요(`fonts/README.md`). 없으면 PowerPoint가 다른 글꼴로 바꿔 보여 줍니다.", "");
  SCRIPT.forEach((s, i) => {
    if (s.backup && !SCRIPT[i - 1].backup) L.push("## 부록 (질문 대비)", "");
    L.push(`${s.backup ? "###" : "##"} ${i + 1}. ${s.title}${s.backup ? "" : ` (${timeOf(s)})`}`, "", `**EN** ${s.en}`, "", `**KO** ${s.ko}`, "");
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
