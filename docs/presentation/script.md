# NextSlide 발표 대본 (영어 / 한국어)

발표 파일: [NextSlide_final.pptx](NextSlide_final.pptx). 슬라이드 노트에도 같은 대본이 들어 있습니다. 이 파일과 노트는 `build_deck.js`가 함께 만듭니다.

- 예상 시간: 약 10분 5초(본문 25장, 시연 2분 포함, 영어 대본을 분당 약 140단어로 읽고 장마다 전환 4초를 더한 값). 부록 3장은 질문이 나올 때만 씁니다.
- 시연을 발표 끝에 하려면 PowerPoint에서 12번 슬라이드(Live demo)를 25번(To sum up) 앞으로 옮기면 됩니다. 대본 순서도 같이 옮깁니다.
- [name] 자리에 이름을 넣어 말하세요. 표지에는 이름이 없으니 필요하면 직접 추가하세요.
- 글꼴: 덱은 나눔스퀘어 네오(NanumSquare Neo, NAVER 무료 글꼴)를 씁니다. 발표할 컴퓨터에 먼저 설치하세요(`fonts/README.md`). 없으면 PowerPoint가 다른 글꼴로 바꿔 보여 줍니다.

## 1. Title (0:15)

**EN** Hi, I'm [name], and my project is NextSlide. While I lecture, I say what the next slide should show, and it gets made while I keep talking.

**KO** 안녕하세요, [이름]입니다. 제 프로젝트는 NextSlide입니다. 강의하다가 다음 장에 무엇을 보여 줄지 말하면, 제가 계속 말하는 동안 그 장이 만들어집니다.

## 2. An idea mid-lecture (0:20)

**EN** When I teach, I often think of an analogy on the spot. Say the students look lost, and I tell them that overfitting is like a student who memorized the answers to old exams.

**KO** 수업을 하다 보면 비유가 그 자리에서 떠오를 때가 많습니다. 학생들이 잘 못 따라오는 것 같아서, 과적합은 기출문제 답을 외운 학생과 같다고 설명한다고 해 봅시다.

## 3. No slide for it (0:15)

**EN** The explanation works, but there is no slide for it. I made the slides before class, and making a new one now would mean stopping the lecture.

**KO** 설명은 괜찮은데 보여 줄 슬라이드가 없습니다. 슬라이드는 수업 전에 만들었고, 지금 새로 만들려면 강의를 멈춰야 합니다.

## 4. Just say it (0:20)

**EN** With NextSlide, I just say it out loud. Here I said this sentence in Korean: 'In the next slide, I'll explain overfitting by comparing it to a student who memorized the exam questions.'

**KO** NextSlide를 쓰면 그냥 말로 하면 됩니다. 이번에는 한국어로 이렇게 말했습니다. '다음 슬라이드에서는 과적합을 시험 문제를 외운 학생에 비유해서 설명하겠습니다.'

## 5. The slide it made (0:20)

**EN** This is the slide it made, with a title, three short points and a picture. This run used the image API and took about 20 seconds. With the local model it takes about six.

**KO** 그렇게 해서 나온 장이 이것입니다. 제목과 짧은 설명 세 줄, 그림이 들어 있습니다. 이번에는 이미지 API를 써서 20초쯤 걸렸고, 로컬 모델로는 6초 정도 걸립니다.

## 6. How it works (0:20)

**EN** It works in three steps. First, my speech is turned into text as I talk. Second, the system decides whether I asked for a slide. Third, a language model writes the slide and an image model draws the picture.

**KO** 동작은 세 단계입니다. 먼저 제 말을 실시간으로 글로 옮깁니다. 다음으로 슬라이드를 만들어 달라는 요청인지 판단합니다. 마지막으로 언어 모델이 장을 쓰고 이미지 모델이 그림을 그립니다.

## 7. Only clear requests (0:20)

**EN** The second step matters most, because a wrong slide interrupts the lecture. So the detector only reacts to clear requests, and a negation or a quote is ignored. On 60 test sentences it was right 56 times and never missed a real request.

**KO** 두 번째 단계가 가장 중요합니다. 엉뚱한 장이 나오면 강의가 끊기기 때문입니다. 그래서 감지기는 분명한 요청에만 반응하고, 부정하는 말이나 인용한 말은 무시합니다. 평가 문장 60개 중 56개를 맞혔고, 실제 요청을 놓친 적은 없습니다.

## 8. You see it first (0:20)

**EN** The new slide comes to me first. The text shows up right away and the picture follows, and I can still edit or cancel it. The audience only sees it when I advance.

**KO** 새 장은 저한테 먼저 옵니다. 글이 바로 뜨고 그림이 뒤따라오며, 이때 고치거나 취소할 수 있습니다. 청중은 제가 넘길 때 비로소 봅니다.

## 9. What was said before (0:25)

**EN** This is the part I care about most. In this test scenario, a history teacher talks about the Joseon civil service exam and then says 'show the exam hall'. That request alone is vague, so NextSlide also sends the last ninety seconds of speech and the current slide.

**KO** 제가 가장 공들인 부분입니다. 이 평가 시나리오에서 역사 선생님은 조선의 과거 시험 이야기를 하다가 '시험장 풍경을 보여 주세요'라고 합니다. 이 요청만으로는 모호해서, NextSlide는 직전 90초 동안 한 말과 현재 장도 같이 보냅니다.

## 10. Same request, different picture (0:20)

**EN** The request, the model and the seed are the same. With the request alone, we get a modern classroom. With the lecture before it, we get the Joseon exam ground the teacher meant, and nobody had to write a prompt.

**KO** 요청도, 모델도, 시드도 같습니다. 요청만 주면 현대식 교실이 나옵니다. 앞의 강의까지 주면 선생님이 말한 조선의 과거 시험장이 나오고, 프롬프트는 아무도 쓰지 않았습니다.

## 11. A picture only when it helps (0:20)

**EN** We saw in Lecture 17 that image models still get text and numbers wrong. So the language model first picks what kind of slide to make. Only illustrations go to the image model. Equations are typeset, and comparisons use a fixed layout.

**KO** 17강에서 봤듯이 이미지 모델은 아직 글자와 숫자를 자주 틀립니다. 그래서 언어 모델이 먼저 어떤 종류의 장을 만들지 고릅니다. 설명 그림만 이미지 모델에 보내고, 수식은 조판하고, 비교는 정해진 레이아웃을 씁니다.

## 12. Live demo (2:00)

**EN** Now let me show it live. The system is built for Korean lectures, so I'll speak the lecture lines in Korean and translate as I go. Please watch for the four things on this slide. (Run the demo. See the demo script below.)

**KO** 이제 직접 보여 드리겠습니다. 한국어 강의용 시스템이라 강의 문장은 한국어로 말하고 바로 영어로 옮기겠습니다. 이 화면에 적은 네 가지를 봐 주세요. (시연 진행. 아래 시연 대본 참고)

### 시연 대본 (Demo script)

준비: 백엔드를 `IMAGE_PROVIDER=local LOCAL_IMAGE_MODEL=sd15`로 켜면 디노이징 미리보기가 약 12초 동안 보입니다(SD-Turbo는 0.6초라 거의 안 보임). 청중 화면을 두 번째 창이나 프로젝터에 띄우고, 같은 흐름을 녹화한 백업 영상을 준비합니다.

**1. Normal speech: nothing happens** (0:20)

- 시스템에 말할 문장(한국어): 과적합은 모델이 학습 데이터에 지나치게 맞춰져서 새로운 데이터에는 잘 대응하지 못하는 현상입니다.
  - 뜻: Overfitting is when a model fits the training data too closely and fails on new data.
- 설명 EN: Point at the live caption. "I just explained overfitting in Korean. It's an explanation, not a request, so nothing is generated."
- 설명 KO: 자막을 가리키며: "방금 한국어로 과적합을 설명했습니다. 요청이 아니라 설명이라서 아무것도 생성되지 않습니다."

**2. Request: the text comes first** (0:40)

- 시스템에 말할 문장(한국어): 다음 슬라이드에서는 과적합을 시험 문제를 외운 학생에 비유해서 설명하겠습니다.
  - 뜻: In the next slide, I'll explain overfitting with a student who memorized the exam answers.
- 설명 EN: "I said: in the next slide, I'll explain overfitting with a student who memorized the exam answers. The detector confirmed the request. The title and bullets appear first in my preview. The audience screen hasn't changed yet."
- 설명 KO: "방금 '다음 슬라이드에서는 과적합을 시험 문제를 외운 학생에 비유해서 설명하겠습니다'라고 했습니다. 감지기가 요청을 확정했고, 제목과 본문이 먼저 제 미리보기에 뜹니다. 청중 화면은 아직 그대로입니다."

**3. Denoising preview, then advance** (0:30)

- 시스템에 말할 문장(한국어): (없음. 그림이 만들어지는 동안 영어로 계속 설명합니다.)
- 설명 EN: "This blurry picture is the model's current guess of the clean image, x-hat-zero, at each step. ... Now it's ready, so I advance, and the audience sees it." Press →.
- 설명 KO: "이 흐린 그림이 매 스텝 모델이 예측한 깨끗한 그림 x̂₀입니다. … 준비됐으니 넘기면 청중 화면에도 나타납니다." → 키.

**4. Negation: ignored** (0:20)

- 시스템에 말할 문장(한국어): 다음 슬라이드는 만들지 마세요.
  - 뜻: Don't make a next slide.
- 설명 EN: "I said: don't make a next slide. It is detected as a negation, so nothing is generated."
- 설명 KO: "'다음 슬라이드는 만들지 마세요'라고 했습니다. 부정 지시로 판단해 생성하지 않습니다."

문제가 생기면: "Let me switch to the recorded video." (녹화 영상으로 넘어가겠습니다.) 마이크가 안 되면 텍스트 입력의 "발화로 입력"에 같은 문장을 넣습니다.

## 13. Watching diffusion (0:20)

**EN** Now the link to the course. The pictures come from a diffusion model on my laptop. At every step it predicts the final image, x-hat-zero from Lecture 17, and I show that prediction so you can watch the picture form.

**KO** 이제 수업 내용과 이어지는 부분입니다. 그림은 제 노트북의 확산 모델이 그립니다. 모델은 매 단계 최종 그림, 즉 17강에서 배운 x̂₀를 예측하는데, 이 예측을 화면에 띄워서 그림이 만들어지는 과정을 볼 수 있게 했습니다.

## 14. Three questions (0:15)

**EN** I ran experiments to answer three questions. For each one, I'll first show how I tested it, and then the result.

**KO** 세 가지 질문에 답하려고 실험을 했습니다. 질문마다 먼저 어떻게 실험했는지 보여 드리고, 그다음에 결과를 말씀드리겠습니다.

## 15. Q1 setup (0:25)

**EN** First, speed. I drew 12 lecture scenes with two seeds each on two models: Stable Diffusion 1.5 with 25 steps, and SD-Turbo, a distilled model that needs only two. I measured seconds per image on my laptop, and the CLIP score, which says how well the picture matches the scene sentence.

**KO** 첫 번째는 속도입니다. 강의 장면 12개를 시드 두 개씩, 두 모델로 그렸습니다. 25단계짜리 Stable Diffusion 1.5와, 2단계면 되는 증류 모델 SD-Turbo입니다. 제 노트북에서 그림 한 장에 걸린 시간을 재고, 그림이 장면 문장과 얼마나 맞는지 보는 CLIP 점수도 쟀습니다.

## 16. Q1 result (0:15)

**EN** Stable Diffusion 1.5 takes 11 seconds per image. SD-Turbo takes 0.7 seconds, about sixteen times faster, and its CLIP score was a bit higher too. So I made SD-Turbo the default.

**KO** Stable Diffusion 1.5는 그림 한 장에 11초, SD-Turbo는 0.7초가 걸려 16배쯤 빨랐고, CLIP 점수도 조금 높았습니다. 그래서 SD-Turbo를 기본값으로 정했습니다.

## 17. Q2 setup (0:20)

**EN** Second, guidance. Lecture 17 says stronger guidance follows the condition more closely but gives less variety. So I changed only the guidance scale and kept everything else from the first test. I also measured variety, meaning how different the two seeds' pictures are.

**KO** 두 번째는 가이던스입니다. 17강에서 가이던스를 세게 주면 조건은 더 잘 따르지만 다양성은 줄어든다고 배웠습니다. 그래서 첫 번째 실험의 조건은 그대로 두고 가이던스 스케일만 바꿨습니다. 두 시드로 그린 그림이 서로 얼마나 다른지를 다양성으로 함께 쟀습니다.

## 18. Q2 result: pictures (0:15)

**EN** This is one scene drawn with the same seed. At 1 the picture barely forms, and by 7.5 you can clearly see the hiker in the valley.

**KO** 같은 시드로 그린 장면 하나입니다. 1에서는 그림이 거의 형태를 갖추지 못하고, 7.5쯤 되면 골짜기를 걷는 등산객이 또렷하게 보입니다.

## 19. Q2 result: the trade-off (0:20)

**EN** Over all 12 scenes, the CLIP score goes up and levels off around 5, but the variety keeps falling. So the trade-off from the lecture shows up here too. Note that CLIP measures prompt match, not image quality.

**KO** 장면 12개 전체로 보면 CLIP 점수는 오르다가 5 근처에서 더 오르지 않고, 다양성은 계속 떨어집니다. 수업에서 배운 트레이드오프가 여기서도 보입니다. 다만 CLIP은 프롬프트와 맞는지만 볼 뿐, 그림의 질은 보지 못합니다.

## 20. Q3 test data (0:30)

**EN** Third, the main question: does the lecture context help? I wrote 42 lecture scenarios, 30 based on this course. In this one from the diffusion lecture, the lecturer compares adding noise to ink spreading in water, then asks for the reverse process with the same analogy. I wrote down the intended picture and committed it before generating.

**KO** 세 번째가 가장 중요한 질문입니다. 강의 맥락이 도움이 될까요? 강의 시나리오 42개를 만들었고, 그중 30개는 이 수업을 바탕으로 했습니다. 확산 모델 강의에서 가져온 이 예에서 강사는 잡음을 더하는 과정을 물에 퍼지는 잉크에 비유하고, 같은 비유로 역방향 과정을 보여 달라고 합니다. 강사가 뜻한 그림은 생성하기 전에 미리 적어 커밋해 두었습니다.

## 21. Q3 setup (0:25)

**EN** Each request runs twice. A gets only the request, and B also gets the last 90 seconds and the current slide. Everything else is the same. I scored each picture by CLIP similarity to the intended scene and compared A and B with a paired permutation test.

**KO** 요청마다 두 번 돌립니다. A는 요청만 받고, B는 직전 90초 발화와 현재 장까지 받습니다. 나머지는 모두 같습니다. 그림마다 정답 장면과의 CLIP 유사도로 점수를 매기고, A와 B를 짝지은 순열 검정으로 비교했습니다.

## 22. Q3 result: closer to the intent (0:25)

**EN** Each bar is one of the 28 scenarios where both made a picture, and most are above zero. On average B is 2.1 points closer, with p equal to 0.010. In the text prompt the gain was 6.4, though, so the image model loses about two-thirds of it.

**KO** 막대 하나가 A와 B 모두 그림을 만든 시나리오 28개 중 하나이고, 대부분 0보다 위에 있습니다. 평균으로 B가 2.1점 더 가까웠고 p값은 0.010입니다. 다만 프롬프트 글 단계에서는 6.4점 차이였으니, 이미지 모델을 거치면서 3분의 2쯤이 사라진 셈입니다.

## 23. Q3 result: no more guessing (0:15)

**EN** Also, without the context the system had to ask me what I meant 7 times out of 42. With the context it never had to ask.

**KO** 또 맥락이 없을 때는 42번 중 7번이나 시스템이 무슨 뜻인지 되물었습니다. 맥락이 있을 때는 한 번도 묻지 않았습니다.

## 24. Still hard (0:25)

**EN** Some problems remain. The fast model draws fake text in about 9 of 34 images, and prompt rules didn't fix it. CLIP is my only automatic judge, and I wrote the scenarios with an AI assistant, so a blind evaluation by people comes next.

**KO** 아직 남은 문제도 있습니다. 빠른 모델이 34장 중 9장 정도에 가짜 글자를 그렸고, 프롬프트 규칙으로도 나아지지 않았습니다. 자동 평가는 CLIP 하나뿐이고 시나리오는 AI 보조 도구와 함께 썼기 때문에, 다음에는 사람이 보는 블라인드 평가를 하려고 합니다.

## 25. To sum up (0:20)

**EN** So, you say what the next slide should show, and it's ready in seconds. The lecture context brings the picture closer to what you meant, and the weak part is still the image model. Thank you. I'm happy to take questions.

**KO** 정리하면, 다음 장에 보여 줄 것을 말하면 몇 초 안에 준비됩니다. 강의 맥락을 쓰면 그림이 뜻한 장면에 더 가까워지고, 아직 약한 부분은 이미지 모델입니다. 감사합니다. 질문 받겠습니다.

## 부록 (질문 대비)

### 26. Backup: prior work

**EN** (Use if asked about prior work.) Live-staging tools such as ZeroPrep interpret every utterance and show the result to the audience right away. NextSlide reacts only to explicit requests, shows the presenter first, and picks the slide form instead of always making cards.

**KO** (이전 연구를 물으면 사용) ZeroPrep 같은 실시간 발표 도구는 모든 발화를 해석해 바로 청중에게 보여 줍니다. NextSlide는 명시적인 요청에만 반응하고, 발표자에게 먼저 보여 주며, 항상 카드를 만드는 대신 슬라이드 형태를 고릅니다.

### 27. Backup: system numbers

**EN** (Use if asked about the detector, tests or speed.) The detector got 56 of 60 test sentences right. It missed no requests, made one slide it shouldn't have, and asked 'which topic?' three times when it didn't need to. There are 112 automated backend tests with mock providers. End to end, one run took 6.2 seconds with local SD-Turbo and 20 seconds with the gpt-image-2 API.

**KO** (감지기, 테스트, 속도를 물으면 사용) 감지기는 평가 문장 60개 중 56개를 맞혔습니다. 요청을 놓친 경우는 없었고, 만들면 안 되는데 만든 경우가 1건, 주제를 괜히 되물은 경우가 3건입니다. 모의 제공자를 쓰는 자동 백엔드 테스트가 112개 있습니다. 전체 흐름은 로컬 SD-Turbo로 한 번 6.2초, gpt-image-2 API로 20초였습니다.

### 28. Backup: how it was measured

**EN** (Use if asked about the method.) Scores are cosine similarity from CLIP ViT-B/32 times 100. It is a different model from the generators' text encoders. Times are medians on an Apple M5 laptop with 16 GB, with the first call excluded as warm-up. Confidence intervals come from resampling the scenes. The X4 test flips the sign of each paired difference 20,000 times. SD-Turbo is based on SD 2.1, so its gain is not from distillation alone. The experiments also found a real bug. Prompts longer than CLIP's 77 tokens lost their style words, and that is fixed now.

**KO** (실험 방법을 물으면 사용) 점수는 CLIP ViT-B/32로 잰 코사인 유사도에 100을 곱한 값이고, 생성 모델의 텍스트 인코더와는 다른 모델입니다. 시간은 Apple M5, 메모리 16GB 노트북에서 잰 중앙값이고, 첫 호출은 워밍업이라 뺐습니다. 신뢰구간은 장면을 다시 뽑는 부트스트랩으로 구했습니다. X4 검정은 짝 차이의 부호를 20,000번 무작위로 뒤집었습니다. SD-Turbo는 SD 2.1 기반이라 빨라진 것이 증류만의 효과는 아닙니다. 실험하다가 실제 버그도 찾았습니다. CLIP의 77토큰을 넘는 프롬프트에서 화풍 문구가 잘리던 문제였고, 지금은 고쳤습니다.

## 예상 질문과 답변 (Q&A)

**Q1. Isn't this just chaining APIs?** (API를 이어 붙인 것 아닌가요?)

- EN: Two parts are my own work. First, the condition design: the condition is built automatically from the lecture, and I measured its effect (X4, p = 0.010). Second, the image stage now runs on local diffusion models that I benchmarked one setting at a time (X1 to X3), plus the x-hat-zero denoising preview.
- KO: 제 작업은 두 가지입니다. 첫째, 강의에서 조건을 자동으로 만드는 조건 설계이고, 그 효과를 측정했습니다(X4, p=0.010). 둘째, 이미지 단계를 로컬 확산 모델로 바꾸고 설정을 하나씩 바꿔 비교했으며(X1~X3), x̂₀ 디노이징 미리보기를 구현했습니다.

**Q2. Why rules instead of an LLM for detecting requests?** (요청 감지를 왜 LLM이 아니라 규칙으로 하나요?)

- EN: Cost, latency, and false triggers. An LLM call for every utterance is slow and expensive, and a false trigger interrupts the lecture. The rules got 56 of 60 right on my test set, with no missed requests and one false generation. The set was written by me, so it is optimistic.
- KO: 비용, 지연, 오작동 때문입니다. 발화마다 LLM을 부르면 느리고 비싸며, 잘못 생성되면 강의가 끊깁니다. 규칙은 평가 세트 60개 중 56개를 맞혔고, 놓친 요청 0건, 잘못 생성 1건이었습니다. 제가 쓴 평가 세트라 결과가 낙관적일 수 있습니다.

**Q3. What if the generated content is wrong?** (생성된 내용이 틀리면 어떻게 하나요?)

- EN: The audience never sees a slide until I advance to it. In the presenter preview I can edit the title and bullets, retry the image, or cancel the job.
- KO: 제가 넘기기 전에는 청중이 새 장을 보지 못합니다. 발표자 미리보기에서 제목과 본문을 고치거나, 그림을 다시 만들거나, 작업을 취소할 수 있습니다.

**Q4. How fast and how expensive is it?** (속도와 비용은 어느 정도인가요?)

- EN: With local SD-Turbo: about 6 seconds from request to finished slide, and the image itself took 1.2 seconds (single measurement). The planner LLM costs about 0.02 to 0.04 cents per slide, and local images are free. With the gpt-image-2 API it was about 20 seconds and about 0.45 cents per image.
- KO: 로컬 SD-Turbo 기준으로 요청부터 완성까지 약 6초, 그림만 1.2초였습니다(1회 측정). 기획 LLM 비용은 장당 약 $0.0002~0.0004이고 로컬 그림은 무료입니다. gpt-image-2 API로는 약 20초, 그림당 약 $0.0045였습니다.

**Q5. How does the denoising preview work?** (디노이징 미리보기는 어떻게 동작하나요?)

- EN: At each step the scheduler already computes the predicted clean sample, x-hat-zero equals x_t minus the square root of one minus alpha-bar times the predicted noise, divided by the square root of alpha-bar. I capture it, project the 4 latent channels to RGB with a fixed linear matrix, and send a small JPEG over WebSocket. No VAE decoding is needed.
- KO: 스케줄러가 매 스텝 이미 계산하는 x̂₀ = (x_t − √(1−ᾱ_t) ε̂) / √ᾱ_t 를 가로챕니다. 잠재 4채널을 고정 선형 행렬로 RGB에 투영하고, 작은 JPEG로 WebSocket을 통해 보냅니다. VAE 디코딩이 필요 없습니다.

**Q6. Can you trust the CLIP score?** (CLIP 점수를 믿을 수 있나요?)

- EN: Not on its own. X1 showed that CLIP misses broken images, and my CLIP-based text detector failed validation. I used a different CLIP model from the generators to reduce bias, and a blind human evaluation is the next step.
- KO: 단독으로는 아닙니다. X1에서 CLIP이 깨진 그림을 잡지 못했고, CLIP으로 글자를 판정하는 방법도 검증에서 실패했습니다. 편향을 줄이려고 생성 모델과 다른 CLIP을 썼고, 다음 단계는 블라인드 사람 평가입니다.

**Q7. Why SD-Turbo instead of gpt-image-2?** (왜 gpt-image-2 대신 SD-Turbo인가요?)

- EN: It is about sixteen to twenty times faster, it runs locally for free, and I can open up the sampling process. The trade-off is fake text in some images. Switching back is a single environment variable.
- KO: 약 16~20배 빠르고, 로컬에서 무료로 돌며, 샘플링 과정을 직접 다룰 수 있습니다. 대신 일부 그림에 가짜 글자가 생깁니다. 환경변수 하나로 다시 바꿀 수 있습니다.

**Q8. Does it work for English lectures?** (영어 강의에서도 되나요?)

- EN: Not yet. Speech recognition is set to Korean and the detector rules are Korean phrases. The planner LLM itself can write English slides, so adding English trigger phrases and switching the STT language is the main work.
- KO: 아직은 아닙니다. 음성 인식 언어가 한국어이고 감지 규칙도 한국어 표현입니다. 기획 LLM은 영어 슬라이드도 쓸 수 있으므로, 영어 요청 표현을 추가하고 STT 언어를 바꾸는 것이 주된 작업입니다.
