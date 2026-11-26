# NextSlide 발표 대본 (영어 / 한국어)

발표 파일: [NextSlide_final.pptx](NextSlide_final.pptx). 슬라이드 노트에도 같은 대본이 들어 있습니다. 이 파일과 노트는 `build_deck.js`가 함께 만듭니다.

- 예상 시간: 약 10분 5초(본문 22장, 시연 2분 포함). 부록 3장은 질문이 나올 때만 씁니다.
- 시연을 발표 끝에 하려면 PowerPoint에서 12번 슬라이드(Live demo)를 22번(To sum up) 앞으로 옮기면 됩니다. 대본 순서도 같이 옮깁니다.
- [name] 자리에 이름을 넣어 말하세요. 표지에는 이름이 없으니 필요하면 직접 추가하세요.
- 글꼴: 덱은 나눔스퀘어 네오(NanumSquare Neo, NAVER 무료 글꼴)를 씁니다. 발표할 컴퓨터에 먼저 설치하세요(`fonts/README.md`). 없으면 PowerPoint가 다른 글꼴로 바꿔 보여 줍니다.

## 1. Title (0:20)

**EN** Hi, I'm [name]. This is NextSlide. While I lecture, I say what the next slide should show, and it appears while I keep talking.

**KO** 안녕하세요, [이름]입니다. NextSlide를 소개하겠습니다. 강의하면서 다음 장에 보여 줄 내용을 말하면, 제가 계속 말하는 동안 그 장이 만들어집니다.

## 2. An idea mid-lecture (0:20)

**EN** Good lectures are partly improvised. Say the students look lost, so I come up with an analogy on the spot: overfitting is like a student who memorized the answers to old exams.

**KO** 좋은 강의는 어느 정도 즉흥적입니다. 학생들이 잘 못 따라오는 것 같아서 그 자리에서 비유를 떠올립니다. '과적합은 기출문제 답을 외운 학생과 같다.'

## 3. No slide for it (0:20)

**EN** It's a good explanation, but there's no slide for it. The slides were made before class, and making one now means stopping the lecture.

**KO** 좋은 설명인데 보여 줄 슬라이드가 없습니다. 슬라이드는 수업 전에 만들었고, 지금 만들려면 강의를 멈춰야 합니다.

## 4. Just say it (0:20)

**EN** With NextSlide, I just say it. I gave the system this Korean sentence: 'In the next slide, I'll explain overfitting by comparing it to a student who memorized the exam questions.'

**KO** NextSlide에서는 그냥 말하면 됩니다. 시스템에 이 한국어 문장을 넣었습니다. '다음 슬라이드에서는 과적합을 시험 문제를 외운 학생에 비유해서 설명하겠습니다.'

## 5. The slide it made (0:20)

**EN** And this slide appeared: a title, three short points, and a picture. This run used the image API and took about 20 seconds; with the local model it takes about six.

**KO** 그러자 이 장이 만들어졌습니다. 제목, 짧은 설명 세 줄, 그림입니다. 이 결과는 이미지 API로 약 20초 걸렸고, 로컬 모델로는 약 6초입니다.

## 6. How it works (0:25)

**EN** Inside, there are three steps. Listen: my speech is transcribed live. Decide: is this a request for a slide? Make: a language model writes the slide, and an image model draws the picture.

**KO** 내부는 세 단계입니다. 듣기: 제 말을 실시간으로 받아 적습니다. 판단: 이게 슬라이드 요청인가? 만들기: 언어 모델이 장을 쓰고 이미지 모델이 그림을 그립니다.

## 7. Only clear requests (0:25)

**EN** Deciding matters most, because a wrong slide interrupts the lecture. A rule-based detector reacts only to clear requests. 'Don't make the next slide' is ignored, and so is a quote, like when I explain how the system works. On 60 test sentences it was right 56 times and never missed a request.

**KO** 판단이 가장 중요합니다. 잘못 만들면 강의가 끊기기 때문입니다. 규칙 기반 감지기는 분명한 요청에만 반응합니다. '다음 슬라이드는 만들지 마세요'는 무시하고, 시스템 사용법을 설명할 때처럼 인용한 말도 무시합니다. 평가 문장 60개 중 56개를 맞혔고, 요청을 놓친 적은 없습니다.

## 8. You see it first (0:20)

**EN** The new slide comes to me first. The text shows up right away, the picture follows, and I can edit or cancel it. The audience only sees it when I advance.

**KO** 새 장은 저에게 먼저 옵니다. 글이 바로 뜨고 그림이 뒤따라오며, 고치거나 취소할 수 있습니다. 청중은 제가 넘길 때만 봅니다.

## 9. What was said before (0:25)

**EN** Here's the key idea. Requests in a lecture are often vague. In one of my test scenarios, a history teacher talks about the Joseon civil service exam and then says: 'In the next slide, show the exam hall.' NextSlide also passes along what was said in the last ninety seconds, and the current slide.

**KO** 핵심 아이디어입니다. 강의 중 요청은 모호한 경우가 많습니다. 제 평가 시나리오 하나에서 역사 선생님이 조선의 과거 시험 이야기를 하다가 '다음 슬라이드에서는 시험장 풍경을 보여 주세요'라고 합니다. NextSlide는 직전 90초 동안 한 말과 현재 장도 함께 넘깁니다.

## 10. Same request, different picture (0:25)

**EN** Same request, same model, same seed. With the request alone, we get a modern classroom. With the lecture before it, we get the Joseon exam ground the teacher meant. Nobody wrote a prompt; the context came from the lecture.

**KO** 요청, 모델, 시드는 같습니다. 요청만 주면 현대식 교실이 나옵니다. 앞의 강의까지 주면 선생님이 뜻한 조선의 과거 시험장이 나옵니다. 아무도 프롬프트를 쓰지 않았고, 맥락은 강의에서 왔습니다.

## 11. A picture only when it helps (0:25)

**EN** One more design choice, from Lecture 17: image models still get text and numbers wrong. So the language model first picks the kind of slide. Only illustrations go to the image model; equations are typeset, and comparisons use a fixed layout.

**KO** 17강에서 온 설계 선택이 하나 더 있습니다. 이미지 모델은 아직 글자와 숫자를 자주 틀립니다. 그래서 언어 모델이 먼저 장의 종류를 정합니다. 설명 그림만 이미지 모델에 보내고, 수식은 조판하고, 비교는 정해진 레이아웃을 씁니다.

## 12. Live demo (2:00)

**EN** Now let me show it live. The system is built for Korean lectures, so I'll speak the lecture lines in Korean and translate as I go. Watch for the four things on the slide. (Run the demo. See the demo script below.)

**KO** 이제 직접 보여 드리겠습니다. 한국어 강의용 시스템이라 강의 문장은 한국어로 말하고 바로 영어로 옮기겠습니다. 화면의 네 가지를 봐 주세요. (시연 진행. 아래 시연 대본 참고)

### 시연 대본 (Demo script)

준비: 백엔드를 `IMAGE_PROVIDER=local LOCAL_IMAGE_MODEL=sd15`로 켜면 디노이징 미리보기가 약 12초 동안 보입니다(SD-Turbo는 0.6초라 거의 안 보임). 청중 화면을 두 번째 창이나 프로젝터에 띄우고, 같은 흐름을 녹화한 백업 영상을 준비합니다.

**1. Normal speech → nothing happens** (0:20)

- 시스템에 말할 문장(한국어): 과적합은 모델이 학습 데이터에 지나치게 맞춰져서 새로운 데이터에는 잘 대응하지 못하는 현상입니다.
  - 뜻: Overfitting is when a model fits the training data too closely and fails on new data.
- 설명 EN: Point at the live caption. "I just explained overfitting in Korean. It's an explanation, not a request, so nothing is generated."
- 설명 KO: 자막을 가리키며: "방금 한국어로 과적합을 설명했습니다. 요청이 아니라 설명이라서 아무것도 생성되지 않습니다."

**2. Request → text first** (0:40)

- 시스템에 말할 문장(한국어): 다음 슬라이드에서는 과적합을 시험 문제를 외운 학생에 비유해서 설명하겠습니다.
  - 뜻: In the next slide, I'll explain overfitting with a student who memorized the exam answers.
- 설명 EN: "I said: in the next slide, I'll explain overfitting with a student who memorized the exam answers. The detector confirmed the request. The title and bullets appear first in my preview. The audience screen hasn't changed yet."
- 설명 KO: "방금 '다음 슬라이드에서는 과적합을 시험 문제를 외운 학생에 비유해서 설명하겠습니다'라고 했습니다. 감지기가 요청을 확정했고, 제목과 본문이 먼저 제 미리보기에 뜹니다. 청중 화면은 아직 그대로입니다."

**3. Denoising preview → advance** (0:30)

- 시스템에 말할 문장(한국어): (없음. 그림이 만들어지는 동안 영어로 계속 설명합니다.)
- 설명 EN: "This blurry picture is the model's current guess of the clean image, x-hat-zero, at each step. ... Now it's ready, so I advance, and the audience sees it." Press →.
- 설명 KO: "이 흐린 그림이 매 스텝 모델이 예측한 깨끗한 그림 x̂₀입니다. … 준비됐으니 넘기면 청중 화면에도 나타납니다." → 키.

**4. Negation → ignored** (0:20)

- 시스템에 말할 문장(한국어): 다음 슬라이드는 만들지 마세요.
  - 뜻: Don't make a next slide.
- 설명 EN: "I said: don't make a next slide. It is detected as a negation, so nothing is generated."
- 설명 KO: "'다음 슬라이드는 만들지 마세요'라고 했습니다. 부정 지시로 판단해 생성하지 않습니다."

문제가 생기면: "Let me switch to the recorded video." (녹화 영상으로 넘어가겠습니다.) 마이크가 안 되면 텍스트 입력의 "발화로 입력"에 같은 문장을 넣습니다.

## 13. Watching diffusion (0:25)

**EN** Now the course part. The picture in the demo came from a diffusion model running on my laptop. It starts from noise and removes it step by step, and at every step it predicts the final image: that's x-hat-zero from the lecture. I send that prediction to the screen, so you can watch the picture form.

**KO** 이제 수업 내용과 연결되는 부분입니다. 시연의 그림은 제 노트북에서 도는 확산 모델이 그렸습니다. 잡음에서 시작해 한 단계씩 걷어 내고, 매 단계 최종 그림을 예측합니다. 수업에서 배운 x̂₀입니다. 이 예측을 화면으로 보내서 그림이 만들어지는 과정을 보여 줍니다.

## 14. Three questions (0:15)

**EN** I ran experiments to answer three questions.

**KO** 세 가지 질문에 답하려고 실험했습니다.

## 15. Q1 · Fast enough? (0:25)

**EN** First: is it fast enough? Stable Diffusion 1.5 with 25 steps takes 11 seconds per image. SD-Turbo is a distilled model that needs only two steps: 0.7 seconds, about sixteen times faster, and it matched the prompts slightly better. So SD-Turbo is the default.

**KO** 첫째, 충분히 빠른가? Stable Diffusion 1.5로 25단계를 돌리면 그림 한 장에 11초가 걸립니다. 증류된 모델인 SD-Turbo는 2단계면 돼서 0.7초, 약 16배 빠르고 프롬프트 일치도도 조금 높았습니다. 그래서 SD-Turbo가 기본값입니다.

## 16. Q2 · Guidance pictures (0:20)

**EN** Second: what does classifier-free guidance change? Same prompt, same seed. At 1 the picture barely forms; by 7.5 the hiker in the valley is clear.

**KO** 둘째, classifier-free guidance는 무엇을 바꾸는가? 프롬프트와 시드는 같습니다. 1에서는 그림이 거의 안 만들어지고, 7.5쯤 되면 골짜기의 등산객이 분명히 보입니다.

## 17. Q2 · The trade-off (0:25)

**EN** Over 12 scenes, the match with the prompt rises and levels off around 5, while the variety between seeds keeps falling. That's the trade-off from the lecture. One caution: CLIP measures prompt match, not quality.

**KO** 장면 12개로 보면 프롬프트 일치도는 오르다가 5 근처에서 멈추고, 시드 간 다양성은 계속 줄어듭니다. 수업에서 배운 트레이드오프입니다. 주의할 점: CLIP은 프롬프트 일치를 볼 뿐 품질은 보지 못합니다.

## 18. Q3 · How it was tested (0:30)

**EN** Third, the main question: does the lecture context help? I wrote 42 lecture scenarios, 30 based on this course's lectures. Each request runs twice: A gets only the request; B also gets the recent speech and the current slide. Before generating anything, I wrote down the scene the lecturer meant and committed it to git.

**KO** 셋째, 핵심 질문입니다. 강의 맥락이 도움이 될까요? 강의 시나리오 42개를 만들었고, 30개는 이 수업 강의자료를 바탕으로 했습니다. 요청마다 두 번 돌립니다. A는 요청만, B는 최근 발화와 현재 장까지 받습니다. 생성 전에 강사가 뜻한 장면을 적어 git에 커밋했습니다.

## 19. Q3 · Closer to the intent (0:30)

**EN** Each bar is one scenario: how much closer B's picture is to that scene than A's. Most bars are above zero. On average B is 2.1 points closer, and a permutation test gives p = 0.010. To be honest, the gain was 6.4 in the text prompt, so the image model loses about two-thirds of it.

**KO** 막대 하나가 시나리오 하나이고, B의 그림이 A보다 그 장면에 얼마나 더 가까운지입니다. 대부분 0보다 위입니다. 평균 2.1점 더 가까웠고 순열 검정 p값은 0.010입니다. 솔직히 말하면 프롬프트 글에서는 6.4점 차이였으니, 이미지 모델에서 3분의 2가량이 사라집니다.

## 20. Q3 · No more guessing (0:20)

**EN** And without the context, the system had to ask me what I meant 7 times out of 42. With the context, never.

**KO** 그리고 맥락이 없으면 42번 중 7번은 시스템이 무슨 뜻인지 되물어야 했습니다. 맥락이 있으면 한 번도 없었습니다.

## 21. Still hard (0:25)

**EN** What's still hard: the fast model writes fake text on paper and signs, in about 9 of 34 images, and prompt rules didn't fix it. My only automatic judge is CLIP, and I wrote the scenarios myself with an AI assistant. So next comes a blind evaluation by people.

**KO** 아직 어려운 점: 빠른 모델이 종이나 간판에 가짜 글자를 그립니다. 34장 중 약 9장이고, 프롬프트 규칙으로도 고쳐지지 않았습니다. 자동 평가는 CLIP 하나뿐이고, 시나리오는 제가 AI 보조 도구와 함께 썼습니다. 그래서 다음은 사람이 보는 블라인드 평가입니다.

## 22. To sum up (0:25)

**EN** To sum up: say what the next slide should show, and it's ready in seconds. Using the lecture as context brings the picture closer to what you meant. The weak spot is still the image model. Thank you. I'm happy to take questions.

**KO** 정리하겠습니다. 다음 장에 보여 줄 것을 말하면 몇 초 안에 준비됩니다. 강의 자체를 맥락으로 쓰면 그림이 뜻한 장면에 더 가까워집니다. 약한 부분은 아직 이미지 모델입니다. 감사합니다. 질문 받겠습니다.

## 부록 (질문 대비)

### 23. Backup · Prior work

**EN** (Use if asked about prior work.) Live-staging tools such as ZeroPrep interpret every utterance and show the result to the audience right away. NextSlide reacts only to explicit requests, shows the presenter first, and picks the slide form instead of always making cards.

**KO** (이전 연구를 물으면 사용) ZeroPrep 같은 실시간 발표 도구는 모든 발화를 해석해 바로 청중에게 보여 줍니다. NextSlide는 명시적인 요청에만 반응하고, 발표자에게 먼저 보여 주며, 항상 카드를 만드는 대신 슬라이드 형태를 고릅니다.

### 24. Backup · System numbers

**EN** (Use if asked about the detector, tests or speed.) The detector got 56 of 60 test sentences right: no missed requests, one slide made when it shouldn't have been, and three unnecessary 'which topic?' questions. There are 112 automated backend tests with mock providers. End to end, one run took 6.2 seconds with local SD-Turbo and 20 seconds with the gpt-image-2 API.

**KO** (감지기·테스트·속도를 물으면 사용) 감지기는 평가 문장 60개 중 56개를 맞혔습니다. 놓친 요청 0건, 만들면 안 되는데 만든 경우 1건, 불필요하게 주제를 되물은 경우 3건입니다. 모의 제공자를 쓰는 자동 백엔드 테스트가 112개 있습니다. 전체 흐름은 로컬 SD-Turbo로 한 번 6.2초, gpt-image-2 API로 20초였습니다.

### 25. Backup · How it was measured

**EN** (Use if asked about the method.) Scores are cosine similarity from CLIP ViT-B/32, a different model from the generators' text encoders, times 100. X1 to X3 used 12 lecture scenes and 2 fixed seeds, changing one setting at a time, with bootstrap confidence intervals. X4 compared 28 paired scenarios with a permutation test. SD-Turbo is based on SD 2.1, so its gain is not distillation alone. The experiments also found a real bug: prompts longer than CLIP's 77 tokens lost their style words, now fixed.

**KO** (실험 방법을 물으면 사용) 점수는 생성 모델의 텍스트 인코더와 다른 CLIP ViT-B/32의 코사인 유사도에 100을 곱한 값입니다. X1~X3은 강의 장면 12개와 고정 시드 2개로 한 번에 설정 하나만 바꿨고, 부트스트랩 신뢰구간을 냈습니다. X4는 짝지은 시나리오 28개를 순열 검정으로 비교했습니다. SD-Turbo는 SD 2.1 기반이라 증류만의 효과는 아닙니다. 실험 중 실제 버그도 찾았습니다. CLIP의 77토큰을 넘는 프롬프트에서 화풍 문구가 잘리던 문제이고, 고쳤습니다.

## 예상 질문과 답변 (Q&A)

**Q1. Isn't this just chaining APIs?** (API를 이어 붙인 것 아닌가요?)

- EN: Two parts are my own work. First, the condition design: the condition is built automatically from the lecture, and I measured its effect (X4, p = 0.010). Second, the image stage now runs on local diffusion models that I benchmarked one setting at a time (X1 to X3), plus the x-hat-zero denoising preview.
- KO: 제 작업은 두 가지입니다. 첫째, 강의에서 조건을 자동으로 만드는 조건 설계이고, 그 효과를 측정했습니다(X4, p=0.010). 둘째, 이미지 단계를 로컬 확산 모델로 바꾸고 설정을 하나씩 바꿔 비교했으며(X1~X3), x̂₀ 디노이징 미리보기를 구현했습니다.

**Q2. Why rules instead of an LLM for detecting requests?** (요청 감지를 왜 LLM이 아니라 규칙으로 하나요?)

- EN: Cost, latency, and false triggers. An LLM call for every utterance is slow and expensive, and a false trigger interrupts the lecture. The rules got 56 of 60 right on my test set, with no missed requests and one false generation. The set was written by me, so it is optimistic.
- KO: 비용, 지연, 오작동 때문입니다. 발화마다 LLM을 부르면 느리고 비싸며, 잘못 생성되면 강의가 끊깁니다. 규칙은 평가 세트 60개 중 56개를 맞혔고, 놓친 요청 0건, 잘못 생성 1건이었습니다. 제가 쓴 평가 세트라 결과가 낙관적일 수 있습니다.

**Q3. What if the generated content is wrong?** (생성된 내용이 틀리면 어떻게 하나요?)

- EN: The audience never sees a slide until I advance to it. In the presenter preview I can edit the title and bullets, retry the image, or cancel the job.
- KO: 제가 넘기기 전에는 청중이 새 장을 보지 못합니다. 발표자 미리보기에서 제목·본문을 고치거나, 그림을 다시 만들거나, 작업을 취소할 수 있습니다.

**Q4. How fast and how expensive is it?** (속도와 비용은 어느 정도인가요?)

- EN: With local SD-Turbo: about 6 seconds from request to finished slide, and the image itself took 1.2 seconds (single measurement). The planner LLM costs about 0.02 to 0.04 cents per slide, and local images are free. With the gpt-image-2 API it was about 20 seconds and about 0.45 cents per image.
- KO: 로컬 SD-Turbo 기준으로 요청부터 완성까지 약 6초, 그림만 1.2초였습니다(1회 측정). 기획 LLM 비용은 장당 약 $0.0002~0.0004이고 로컬 그림은 무료입니다. gpt-image-2 API로는 약 20초, 그림당 약 $0.0045였습니다.

**Q5. How does the denoising preview work?** (디노이징 미리보기는 어떻게 동작하나요?)

- EN: At each step the scheduler already computes the predicted clean sample, x-hat-zero equals x_t minus the square root of one minus alpha-bar times the predicted noise, divided by the square root of alpha-bar. I capture it, project the 4 latent channels to RGB with a fixed linear matrix, and send a small JPEG over WebSocket. No VAE decoding is needed.
- KO: 스케줄러가 매 스텝 이미 계산하는 x̂₀ = (x_t − √(1−ᾱ_t)·ε̂) / √ᾱ_t 를 가로챕니다. 잠재 4채널을 고정 선형 행렬로 RGB에 투영하고, 작은 JPEG로 WebSocket을 통해 보냅니다. VAE 디코딩이 필요 없습니다.

**Q6. Can you trust the CLIP score?** (CLIP 점수를 믿을 수 있나요?)

- EN: Not on its own. X1 showed that CLIP misses broken images, and my CLIP-based text detector failed validation. I used a different CLIP model from the generators to reduce bias, and a blind human evaluation is the next step.
- KO: 단독으로는 아닙니다. X1에서 CLIP이 깨진 그림을 잡지 못했고, CLIP으로 글자를 판정하는 방법도 검증에서 실패했습니다. 편향을 줄이려고 생성 모델과 다른 CLIP을 썼고, 다음 단계는 블라인드 사람 평가입니다.

**Q7. Why SD-Turbo instead of gpt-image-2?** (왜 gpt-image-2 대신 SD-Turbo인가요?)

- EN: It is about sixteen to twenty times faster, it runs locally for free, and I can open up the sampling process. The trade-off is fake text in some images. Switching back is a single environment variable.
- KO: 약 16~20배 빠르고, 로컬에서 무료로 돌며, 샘플링 과정을 직접 다룰 수 있습니다. 대신 일부 그림에 가짜 글자가 생깁니다. 환경변수 하나로 다시 바꿀 수 있습니다.

**Q8. Does it work for English lectures?** (영어 강의에서도 되나요?)

- EN: Not yet. Speech recognition is set to Korean and the detector rules are Korean phrases. The planner LLM itself can write English slides, so adding English trigger phrases and switching the STT language is the main work.
- KO: 아직은 아닙니다. 음성 인식 언어가 한국어이고 감지 규칙도 한국어 표현입니다. 기획 LLM은 영어 슬라이드도 쓸 수 있으므로, 영어 요청 표현을 추가하고 STT 언어를 바꾸는 것이 주된 작업입니다.
