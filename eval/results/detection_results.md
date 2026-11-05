# 요청 감지 평가 결과

- 실행 시각: 2026-11-05T15:12:26
- 표본 수: 60 (규칙 기반 감지기, API 호출 없음, 결정적)
- 시뮬레이션 조건: 확정 STT 구간 0.8초 간격 입력 후 침묵 2.6초 (REQUEST_SILENCE_MS=2500)
- 전체 정확도(3분류: request / needs_input / none): **93.3%** (56/60)
- 잘못 생성(정답이 request 가 아닌데 생성): 1건 · 놓친 생성(정답 request 인데 미생성): 0건

## 범주별

| 범주 | n | 정답 |
|---|---|---|
| clear | 10 | 10/10 |
| split | 4 | 4/4 |
| normal | 8 | 6/8 |
| negated | 5 | 5/5 |
| quoted | 4 | 3/4 |
| ambiguous | 5 | 4/5 |
| truncated | 4 | 4/4 |
| added | 7 | 7/7 |
| added_negative | 9 | 9/9 |
| real_user | 4 | 4/4 |

## 혼동 행렬 (행=정답, 열=예측)

| 정답 \ 예측 | request | needs_input | none | 기타 |
|---|---|---|---|---|
| request | 25 | 0 | 0 | 0 |
| needs_input | 1 | 7 | 0 | 0 |
| none | 0 | 3 | 24 | 0 |

## 사례별

| id | 범주 | 입력 | 정답 | 예측 | 주제 추출 | 결과 |
|---|---|---|---|---|---|---|
| clear-01 | clear | 다음 슬라이드에서는 과적합을 시험 문제를 외운 학생에 비유해서 설명하겠습니다. | request | request | 과적합을 시험 문제를 외운 학생에 비유해서 | ✅ |
| clear-02 | clear | 다음 장에는 결정 트리 예시를 보여주세요. | request | request | 결정 트리 예시 | ✅ |
| clear-03 | clear | 슬라이드를 만들어 주세요. 주제는 교차 검증입니다. | request | request | 교차 검증 | ✅ |
| clear-04 | clear | 그럼 이제 다음 슬라이드에서 활성화 함수를 소개할게요. | request | request | 활성화 함수 | ✅ |
| clear-05 | clear | 다음 장에서는 CNN 구조를 그림으로 보여드릴게요. | request | request | CNN 구조를 그림 | ✅ |
| clear-06 | clear | 다음슬라이드에서는 드롭아웃을 설명하겠습니다 | request | request | 드롭아웃 | ✅ |
| clear-07 | clear | 다음 장에서는 배치 정규화를 다뤄볼게요. | request | request | 배치 정규화 | ✅ |
| clear-08 | clear | 드롭아웃에 대한 슬라이드를 만들어 주세요. | request | request | 드롭아웃 | ✅ |
| clear-09 | clear | 편향은 모델이 너무 단순할 때 생기는 오차입니다. 다음 슬라이드에서는 분산을 설명하겠습니다. | request | request | 분산 | ✅ |
| clear-10 | clear | 다음 슬라이드에서는, 음, 학습률이 너무 크면 어떻게 되는지 보여주세요. | request | request | 음, 학습률이 너무 크면 어떻게 되는지 | ✅ |
| split-01 | split | 다음 슬라이드에서는 ▏과적합을 시험 문제를 외운 학생에 비유해서 ▏설명하겠습니다. | request | request | 과적합을 시험 문제를 외운 학생에 비유해서 | ✅ |
| split-02 | split | 다음 ▏슬라이드에서는 경사하강법을 산에서 내려오는 사람에 비유해 설명하겠습니다. | request | request | 경사하강법을 산에서 내려오는 사람에 비유해 | ✅ |
| split-03 | split | 슬라이드를 만들어 주세요. ▏주제는 정규화입니다. | request | request | 정규화 | ✅ |
| split-04 | split | 자 그러면 ▏다음 장에는 혼동 행렬을 ▏보여주세요. | request | request | 혼동 행렬 | ✅ |
| normal-01 | normal | 과적합은 학습 데이터에 지나치게 맞춰져서 새로운 데이터에는 잘 대응하지 못하는 현상입니다. | none | none |  | ✅ |
| normal-02 | normal | 다음 슬라이드를 보시면 그래프가 있습니다. | none | none |  | ✅ |
| normal-03 | normal | 자 다음 장으로 넘어가겠습니다. | none | none |  | ✅ |
| normal-04 | normal | 다음 슬라이드로 넘어가서 설명을 이어가겠습니다. | none | none |  | ✅ |
| normal-05 | normal | 이 슬라이드에서 가장 중요한 건 일반화입니다. | none | none |  | ✅ |
| normal-06 | normal | 다음 페이지에 있는 표를 보시면 됩니다. | none | needs_input | 있는 표를 보시면 됩니다 | ❌ |
| normal-07 | normal | 지난 시간에 다음 장 내용을 미리 읽어 오라고 했죠. | none | needs_input | 내용을 미리 읽어 오라고 했죠 | ❌ |
| normal-08 | normal | 슬라이드가 조금 작게 보이면 말씀해 주세요. | none | none |  | ✅ |
| negated-01 | negated | 다음 슬라이드는 만들지 마세요. | none | none |  | ✅ |
| negated-02 | negated | 다음 슬라이드를 만들지 말고 칠판에 설명하겠습니다. | none | none |  | ✅ |
| negated-03 | negated | 다음 슬라이드는 필요 없어요. | none | none |  | ✅ |
| negated-04 | negated | 다음 슬라이드에서는 과적합을 설명하지 않고 바로 실습하겠습니다. | none | none |  | ✅ |
| negated-05 | negated | 슬라이드를 만들지 마세요. 주제는 정규화입니다. | none | none |  | ✅ |
| quoted-01 | quoted | 여러분이 '다음 슬라이드에서는 과적합을 설명하겠습니다'라고 말하면 시스템이 슬라이드를 만듭니다. | none | none |  | ✅ |
| quoted-02 | quoted | 예를 들어 다음 슬라이드에서는 과적합을 설명하겠습니다 라고 하면 됩니다. | none | none |  | ✅ |
| quoted-03 | quoted | 제가 다음 장에는 그래프를 보여주세요라고 하면 그래프가 나옵니다. | none | none |  | ✅ |
| quoted-04 | quoted | 이 시스템은 다음 슬라이드에서는 무엇을 설명하겠습니다 같은 문장을 인식합니다. | none | needs_input | 무엇 | ❌ |
| ambiguous-01 | ambiguous | 다음 슬라이드에서는 이거 설명하겠습니다. | needs_input | needs_input | 이거 | ✅ |
| ambiguous-02 | ambiguous | 다음 슬라이드에서는 아까 말한 거 설명할게요. | needs_input | needs_input | 아까 말한 거 | ✅ |
| ambiguous-03 | ambiguous | 다음 장에는 그 내용을 보여주세요. | needs_input | needs_input | 그 내용 | ✅ |
| ambiguous-04 | ambiguous | 다음 슬라이드에서는 그거, 아까 그 예시 설명할게요. | needs_input | request | 그거, 아까 그 예시 | ❌ |
| ambiguous-05 | ambiguous | 슬라이드를 만들어 주세요. | needs_input | needs_input |  | ✅ |
| truncated-01 | truncated | 다음 슬라이드에서는 | needs_input | needs_input |  | ✅ |
| truncated-02 | truncated | 다음 슬라이드에서는 과적합을 | needs_input | needs_input | 과적합 | ✅ |
| truncated-03 | truncated | 다음 장에는 손실 함수와 | needs_input | needs_input | 손실 함수 | ✅ |
| truncated-04 | truncated | 다음 슬라이드에서는 경사하강법 | request | request | 경사하강법 | ✅ |
| added-01 | added | 다음으로 경사하강법을 설명하겠습니다. | request | request | 경사하강법 | ✅ |
| added-02 | added | 그다음으로 정규화를 살펴보겠습니다. | request | request | 정규화 | ✅ |
| added-03 | added | 경사하강법 슬라이드 부탁해요. | request | request | 경사하강법 | ✅ |
| added-04 | added | 교차 검증 슬라이드 부탁드립니다. | request | request | 교차 검증 | ✅ |
| added-05 | added | 자 그럼 이제 경사하강법 슬라이드 하나 만들어 주세요. | request | request | 경사하강법 | ✅ |
| added-06 | added | 다음으로 ▏드롭아웃에 대해 알아볼게요. | request | request | 드롭아웃 | ✅ |
| added-n01 | added_negative | 다음으로 넘어가겠습니다. | none | none |  | ✅ |
| added-n02 | added_negative | 다음으로 중요한 점은 데이터의 양입니다. | none | none |  | ✅ |
| added-n03 | added_negative | 이 방법 다음으로 많이 쓰이는 것은 랜덤 포레스트입니다. | none | none |  | ✅ |
| added-n04 | added_negative | 슬라이드 부탁드린 거 다들 받으셨나요? | none | none |  | ✅ |
| added-n05 | added_negative | 여러분이 경사하강법 슬라이드 부탁해요 라고 말하면 만들어집니다. | none | none |  | ✅ |
| added-n06 | added_negative | 다음으로 경사하강법은 설명하지 않겠습니다. | none | none |  | ✅ |
| added-n07 | added_negative | 그럼 경사하강법을 한번 봅시다. | none | none |  | ✅ |
| real-01 | real_user | 네, 안녕하십니까. 지금부터 머신러닝 기초에 대한 수업을 시작하도록 하겠습니다. 어, 다음 장에서는 우선 오늘 발표에 대한 목차를 설명드리도록 하겠습니다. | request | request | 우선 오늘 발표에 대한 목차 | ✅ |
| dorok-01 | added | 다음 슬라이드에서는 과적합을 설명하도록 하겠습니다. | request | request | 과적합 | ✅ |
| dorok-n01 | added_negative | 다음 장을 보도록 하겠습니다. | none | none |  | ✅ |
| dorok-n02 | added_negative | 다음 슬라이드로 넘어가도록 하겠습니다. | none | none |  | ✅ |
| real-02 | real_user | 안녕하십니까. 지금부터 어 머신러닝 기초 수업을 시작하도록 하겠습니다. 어 다음 슬라이드에선 우선 어 오늘 수업에 대한 목차를 설명드리도록 하겠습니다. | request | request | 우선 어 오늘 수업에 대한 목차 | ✅ |
| real-03 | real_user | 어 오늘 수업의 흐름으로는 어 먼저 머신러닝이 무엇인지 기본 개념 살펴보고 데이터와 패턴 이해하는 과정 이해하고 어 배운 마지막 간단한 적용 사례를 통해 배운 내용 요약합니다. | none | none |  | ✅ |
| real-04 | real_user | 다음 장에서는 우선 머신러닝 기본 개념을 살펴볼 건데요. ▏기본 개념이라고 한다면은 우선은 ▏수학적인 개념이 있을 거고 ▏그다음에는 ▏어. ▏컴퓨터적인 개념이겠죠? | request | request | 우선 머신러닝 기본 개념 | ✅ |

## 오답 분석

- `normal-06`: 정답 none → 예측 needs_input. 입력: “다음 페이지에 있는 표를 보시면 됩니다.”
- `normal-07`: 정답 none → 예측 needs_input. 입력: “지난 시간에 다음 장 내용을 미리 읽어 오라고 했죠.”
- `quoted-04`: 정답 none → 예측 needs_input. 입력: “이 시스템은 다음 슬라이드에서는 무엇을 설명하겠습니다 같은 문장을 인식합니다.”
- `ambiguous-04`: 정답 needs_input → 예측 request. 입력: “다음 슬라이드에서는 그거, 아까 그 예시 설명할게요.”
