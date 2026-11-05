# 모델·과금·검증 수준 결정 기록

작성일: 2026-11-05. 우선순위는 **실시간 반응과 낮은 비용**입니다.
모든 모델 ID와 주요 설정은 환경변수로 교체할 수 있고(`backend/.env.example`), 아래 기본값은 실측 전의 **임시 설정**입니다.

## 1. “Bearer 헤더로 확인했다”의 정확한 의미

| 수준 | 상태 | 근거 |
|---|---|---|
| 공식 문서 확인 | **간접 확인** | OpenAI 문서 검색 결과의 요약에서 서버 측 Realtime WebSocket이 `Authorization: Bearer <API 키>` 헤더를 쓴다는 내용을 확인했습니다. 해당 WebSocket 가이드 페이지를 직접 열면 404가 나서 원문은 읽지 못했습니다. |
| 실제 WebSocket 연결 성공 | **미검증** | API 키가 없어 OpenAI 서버에 연결해 본 적이 없습니다. |
| 실제 음성 전사 수신 | **미검증** | 위와 같습니다. |

이전 보고에서 “Bearer 헤더 확인”이라고 한 것은 `backend/tests/test_provider_contracts.py`의 계약 테스트를 가리킵니다. 이 테스트는 우리 어댑터가 **로컬 가짜 서버로** 그 헤더를 보내는지만 확인합니다. 실제 계정의 모델 접근 권한이나 API 동작을 증명하지 않습니다.

## 2. gpt-live-transcribe 설정 확인과 처리 방식

공식 문서([Realtime transcription](https://developers.openai.com/api/docs/guides/realtime-transcription), [Realtime server events](https://developers.openai.com/api/reference/resources/realtime/server-events))에서 확인한 내용과 코드의 대응은 다음과 같습니다.

| 항목 | 문서 | 코드 (`backend/app/providers/openai_stt.py`, `stt_stream.py`) |
|---|---|---|
| 연결 | `wss://api.openai.com/v1/realtime?intent=transcription` | 같음 |
| 세션 설정 | `session.update`, `session.type="transcription"` | 같음 |
| 오디오 형식 | `audio.input.format = {type: "audio/pcm", rate: 24000}`, mono PCM16 | 같음. 브라우저는 AudioWorklet에서 저역통과 필터 후 24kHz로 리샘플링하고, 서버는 `mic_start` 선언(24000/pcm_s16le/mono)을 검증해 다르면 거부 |
| 언어·지연 | `languages` 배열(단수 `language`와 함께 보내지 말 것), `delay` (`minimal`~`xhigh`) | `languages: ["ko"]`, `delay: "low"`. 단수 `language`는 보내지 않음(테스트로 확인) |
| 턴 감지 | `server_vad`, `semantic_vad` **미지원**. `turn_detection`은 생략하거나 `null` | `turn_detection: null` 고정. 서버가 돌려준 실제 설정에 턴 감지가 켜져 있으면 실패로 처리 |
| 발화 종료 | 클라이언트 측 VAD로 발화 끝을 감지해 `input_audio_buffer.commit` | 서버의 20ms RMS VAD. 유성 누적이 `VAD_MIN_SPEECH_MS` 이상일 때만 STT로 전송, 침묵 `VAD_SILENCE_MS` 후 commit |
| 설정 승인 | `session.update`가 적용되면 서버가 실제 반영된 설정을 담아 `session.updated`를 보냄 | **`session.updated` 수신 후, 실제 설정이 맞는지 검증까지 끝나야 ready**. 검증 항목: `session.type`=transcription, 전사 모델, `format.type`=audio/pcm, `format.rate`=24000, turn_detection(값이 있으면 null이어야 함). 값이 다르면 `mismatch`. 항목이 없으면 `unverifiable`로 실패(`STT_STRICT_SESSION_CHECK=false`면 '미검증 항목' 경고를 띄우고 진행). `error`는 `rejected`, 승인 시간 초과는 `ack_timeout` |
| 결과 순서 | 구간 간 완료 순서는 보장되지 않음, `item_id`로 매칭 | `committed(item_id)` ↔ VAD 구간 매핑 후 **commit 순서대로 재정렬**해 감지기에 전달 |

문서에 없어서 확인하지 못한 것:

- `delay`의 기본값
- commit에 필요한 최소 오디오 길이
- transcription 가이드에 나오지 않는 `input_audio_buffer.clear`

마지막 항목은 쓰지 않아도 되도록 설계했습니다. 잡음 구간은 처음부터 STT로 보내지 않습니다.

### 이번에 고친 세 가지 (리뷰 지적 사항)

1. **전사 결과 순서 뒤바뀜.** 완료 이벤트를 commit 순서대로 보관했다가 앞 구간부터 감지기에 전달합니다.
   - 앞 구간이 실패하면 즉시 건너뜁니다.
   - 뒤 구간이 도착했는데 앞 구간이 `STT_REORDER_TIMEOUT_MS`(3초) 넘게 오지 않으면 건너뜁니다.
   - 어떤 결과도 `STT_RESULT_TIMEOUT_MS`(10초) 넘게 오지 않으면 건너뜁니다.
   - 건너뛴 구간이 늦게 도착하면 자막과 기록에만 남기고 요청 감지에는 쓰지 않습니다.
   - 재연결로 잃은 구간은 어댑터가 즉시 실패로 알립니다.
   - 리뷰의 재현 사례(“과적합을 설명하겠습니다.”가 “다음 슬라이드에서는”보다 먼저 도착)는 테스트 `test_out_of_order_finals_are_delivered_in_commit_order`로 넣었습니다. 이 사례에서 정상 생성되고, 앞선 설명도 맥락에 포함됩니다.
2. **최소 발화 길이.** 유성 프레임이 시작되면 오디오를 서버에 보관만 합니다. 유성 누적이 250ms 이상이 되어야 보관분(프리롤 포함)을 STT로 보내고, 그 전에 침묵이 이어지면 버립니다. 리뷰의 재현(20ms 큰 잡음 + 700ms 침묵)에서 전송량 0바이트, commit 0회를 확인했습니다(`test_short_noise_is_not_sent_or_committed`).
3. **설정 승인 전 ‘연결됨’ 표시.** `session.updated`를 받기 전에는 `connecting`으로 둡니다. 거부나 시간 초과는 `error` 상태와 사유를 화면에 표시합니다. 승인 뒤 서버 오류는 `degraded` 상태로 표시합니다.
   - 2차 리뷰 반영: 처음 구현은 항목이 없으면 검증을 건너뛰었습니다. 그래서 빈 응답 `{}`나 `audio/pcmu` 형식도 통과했습니다. 이제 위 표의 필수 항목을 모두 확인합니다(새 테스트 4개는 이전 코드에서 실패).

이 수정을 검증하는 새 테스트 6개는 **이전 코드(e10b3dd)에서 5개가 실패하고 수정 후 모두 통과**합니다.

## 3. 텍스트 모델: 왜 Opus였고, 왜 지금은 Haiku인가

**처음 claude-opus-5-5를 고른 이유.** Claude API 사용 가이드의 기본 지침(“사용자가 다른 모델을 지정하지 않으면 claude-opus-5-5”)을 그대로 따랐을 뿐입니다. 이 작업에 맞춰 비용이나 지연을 비교한 결과가 아닙니다. 짧은 슬라이드 JSON(제목 1개, 문장 2~3개, 영어 장면 묘사 1개)에는 과한 선택이었습니다.

**비교** (가격은 [Anthropic 공식 가격표](https://platform.claude.com/docs/en/about-claude/pricing), 2026-11-05 확인):

| 모델 | 입력/출력 ($/1M tok) | 한 장당 추정 비용* | 지연 | 이 작업에 맞는지 |
|---|---|---|---|---|
| **claude-haiku-5-5** | 0.10 / 0.50 (프롬프트 10만 토큰 이하) | 약 $0.0007 | 문서상 “지연에 민감한 대량 작업용” 모델. **실측 없음** | 구조화 출력 지원. 짧은 추출·작성 작업에 적합. 서버 측 refusal fallback은 없음 |
| claude-sonnet-5-5 | 2 / 10 | 약 $0.015 | 실측 없음 | 품질 여유가 큼 |
| claude-opus-5-5 | 4 / 20 | 약 $0.03 | 실측 없음. 사고(thinking)를 끌 수 없음 | 과함 |

\* 가정: 입력 약 2,500토큰(시스템 프롬프트, 맥락 1,500자, 현재 장, 요청), 출력과 thinking 약 1,000토큰. 실측 전 추정입니다.

**임시 기본값: `claude-haiku-5-5`, `TEXT_EFFORT=low`, thinking 미전송.** 문서는 Haiku 5.5에서 thinking을 끄기보다 낮은 effort를 쓰라고 권하며, 그러면 단순한 요청에서는 thinking을 건너뛸 수 있습니다. 측정해 보고 더 빨라야 하면 `TEXT_THINKING=disabled`도 쓸 수 있습니다(effort가 high 이하일 때 허용).
어댑터는 이제 모델마다 허용되는 옵션만 보냅니다. Haiku에는 `fallbacks`와 beta 헤더를 보내지 않고, Opus 5.5에는 `thinking: disabled`를 보내지 않습니다.

**확정 절차:** 실제 키로 `eval/latency_probe.py -n 5`를 Haiku와 Sonnet에 대해 실행하고 기획 시간, 검증 실패(재요청) 횟수, 비용을 비교한 뒤 기본값을 확정합니다. 결과가 기록되기 전까지 지연 비교는 **미검증**입니다.

## 4. 이미지: gpt-image-2, 1536x864, 품질

- 문서([Image generation](https://developers.openai.com/api/docs/guides/image-generation))에 “`gpt-image-2`는 두 변이 16px 배수이고 총 픽셀이 655,360~8,294,400인 어떤 해상도든 받는다”고 명시되어 있습니다. 1536x864(1,327,104픽셀, 16:9)는 조건을 만족합니다. 실제 계정에서 받아들여지는지는 **미검증**입니다.
- 요청 설정은 모두 명시합니다: `size=1536x864`, `quality=low`(임시), `output_format=jpeg`, `n=1`.
  - 문서는 “빠른 초안에는 `quality: "low"`”, “지연이 중요하면 png보다 빠른 jpeg”를 권합니다.
- 문서의 장당 출력 비용표(gpt-image-2): 1536x1024는 low $0.005, medium $0.041, high $0.165이고, 1024x1024는 low $0.006, medium $0.053입니다. **1536x864는 표에 없습니다.** 다른 해상도의 가격에서 픽셀 수로 환산하는 방식은 상한을 보장하지 않으므로 쓰지 않습니다. 실제 비용은 응답의 `usage` 토큰 × 단가로만 판단하고, 그 값을 작업마다 기록합니다.
- **실제 생성 시간과 사용량 기록**: 작업마다 `jobs.metrics`에 다음을 저장하고, 호출마다 `usage_log`에도 남깁니다. 아직 실제 호출이 없어 **측정값은 없습니다**.
  - `image_ms`(생성 소요)
  - `image_settings`(크기, 품질, 형식)
  - `image_input_tokens`, `image_output_tokens`
  - `image_cost_estimate_usd`
  - `image_bytes`, 실제 반환 해상도
- 구조는 그대로 유지합니다. 제목과 본문은 웹(React 템플릿)에서 렌더링하고, 이미지 모델에는 글자·숫자·라벨을 넣지 말라는 설명용 일러스트만 요청합니다.
- **확정 절차:** `eval/check_providers.py --image --quality low`와 `--quality medium`으로 한 번씩 생성해 시간, 비용, 화면 품질을 비교합니다.

## 5. 계정과 과금 경로

이 앱은 **API 사용료**로 과금됩니다. ChatGPT나 Claude **구독에 포함되지 않습니다.**

| 용도 | 필요한 계정 | 과금 | 구독과의 관계 |
|---|---|---|---|
| 음성 인식 + 이미지 | OpenAI API 조직 (platform.openai.com) | 사용량에 따른 API 요금. API 결제 설정에서 결제 수단 또는 크레딧 필요 | ChatGPT Plus 등 구독과 **별도**이며 구독에 API 사용이 포함되지 않음 ([OpenAI 도움말](https://help.openai.com/en/articles/6950777-what-is-chatgpt-plus), [결제 관리](https://help.openai.com/en/articles/9039756-managing-billing-for-chatgpt-and-the-api-platform)). 이미지 모델은 조직 인증이 필요할 수 있음 |
| 슬라이드 기획 | Anthropic Console 조직 (API 키) | 사용량에 따른 API 요금 (Console 크레딧) | Claude Pro/Max/Team 구독과 **별도** ([Anthropic 도움말](https://support.claude.com/en/articles/9876003-i-have-a-paid-claude-subscription-pro-max-team-or-enterprise-plans-why-is-claude-api-usage-billed-separately-from-my-paid-claude-plan)). 단, Max·Ultra·Team 요금제에는 Console 조직을 연결해야 받는 **월간 API 크레딧**이 있고 Pro에는 없음 ([API credits for subscribers](https://platform.claude.com/docs/en/about-claude/api-credits-for-subscribers)) |

- 사용 중인 요금제는 제가 알 수 없습니다. 이 작업 중에 **결제, 충전, 결제 수단 등록, 키 발급을 하지 않았고, 실제 API를 한 번도 호출하지 않았습니다.**
- 이 Claude Code 세션의 사용량은 앱의 API 과금과 무관합니다.
- 현재 구성은 OpenAI와 Anthropic, **두 회사의 API 계정이 모두 필요합니다.** 계정을 하나로 줄이려면 OpenAI 텍스트 모델 어댑터를 추가하면 됩니다. 후보는 공식 가격표 기준 `gpt-6-luna` $0.10/$0.50, `gpt-5-nano` $0.05/$0.40입니다. 아직 구현하지 않았습니다.

**예산 가정** (실측이 아니며 확정 비용이 아닙니다. 예산을 잡기 위한 가정이고, 50분 강의와 생성 10장을 기준으로 합니다):

| 항목 | 계산 | 추정 |
|---|---|---|
| 음성 인식 | $0.017/분 × 실제 전송한 발화 오디오 약 35~50분. 침묵과 잡음은 보내지 않음 | $0.60~0.85 |
| 슬라이드 기획 (Haiku) | 10장 × 약 $0.0007 | 약 $0.01 (Opus라면 약 $0.30) |
| 이미지 (low) | 10장 × **가정값** $0.005. 1536x864 가격은 미확인이므로 1536x1024 표 가격을 대용으로 씀. 상한 아님 | 약 $0.06 (medium 가정 시 약 $0.42) |
| **합계 (가정)** | | **약 $0.7~0.9** (이미지 medium 가정 시 약 $1.1~1.3). 실제 값은 `check_providers.py`와 `latency_probe.py`의 usage 기록으로 대체할 것 |

STT 과금이 전송한 오디오 길이 기준인지 연결 시간 기준인지는 가격표에 “분당”으로만 나와 있어 **미확인**입니다.

## 6. 검증 수준 구분 (2026-11-05 현재)

| 구성 요소 | 모델명이 공식 문서에 있음 | 계정 권한 | 실제 호출 성공 | 전체 시스템 동작 |
|---|---|---|---|---|
| STT `gpt-live-transcribe` | ✅ 모델 목록·전사 가이드·가격표 | ❌ 미검증 (키 없음) | ❌ 미검증 | ❌ 미검증 |
| 텍스트 `claude-haiku-5-5` | ✅ Anthropic 가격표·모델 문서 | ❌ 미검증 | ❌ 미검증 | ❌ 미검증 |
| 이미지 `gpt-image-2` | ✅ 가격표·모델 페이지·가이드 | ❌ 미검증 (조직 인증 필요 여부 포함) | ❌ 미검증 | ❌ 미검증 |
| mock 구성 전체 흐름 | – | – | – | ✅ 자동 테스트 65개, 헤드리스 Chrome E2E |
| 어댑터 요청 형식 | – | – | 로컬 가짜 서버 계약 테스트만 | – |

### 실제 연결을 단계별로 확인하는 방법

`check_providers.py`는 제공자별로 다음 세 단계를 **따로** 기록합니다.

- `server_responded`: 서버 응답을 받았는가
- `request_accepted`: 요청이 정상적으로 받아들여졌는가 (HTTP 2xx, STT는 승인과 설정 검증 통과)
- `result_valid`: 유효한 결과를 받았는가

한도 초과(429), 잘못된 요청(400), 서버 오류(5xx)는 '응답 O, 수락 X'로 기록합니다. HTTP 200이어도 이미지가 없거나 형식이 잘못됐으면 '수락 O, 결과 X'로 기록합니다. 이 분류는 테스트로 고정했습니다(`test_check_image_does_not_report_errors_as_success`).

```bash
backend/.venv/bin/python eval/check_providers.py --stt                      # 연결과 설정 승인만 (오디오 미전송)
backend/.venv/bin/python eval/check_providers.py --stt --wav 녹음.wav        # 한국어 전사 수신
backend/.venv/bin/python eval/check_providers.py --text                     # 기획 1회
backend/.venv/bin/python eval/check_providers.py --image --quality low      # 이미지 1회
backend/.venv/bin/python eval/latency_probe.py -n 5                          # 전체 흐름 5회: 기획·이미지·총 시간·비용
```

각 실행 결과는 `eval/results/`에 저장됩니다. 키는 저장하지 않습니다. 이 결과로 위 표의 ❌를 채우고 `docs/DEVLOG.md`에 기록합니다.

## 7. 구독 사용량으로 쓸 수 있는가 (2026-11-05 확인)

| 구성 요소 | 구독 범위 안에서 쓰는 방법 | 비고 |
|---|---|---|
| 슬라이드 기획 (Claude) | **Claude Max·Ultra·Team 요금제의 월간 API 크레딧**: Max $100, Ultra $200, Team 좌석당 $20/$100(최대 $500) | claude.ai의 Settings > Billing에서 Console 조직을 연결해 받습니다. 결제 수단 등록은 필요 없습니다. 크레딧이 떨어지면 요금이 청구되지 않고 요청이 멈춥니다. 다음 달로 이월되지 않습니다. 가입 7일 뒤부터 받을 수 있고, **Free·Pro·Enterprise는 대상이 아닙니다** ([API credits for subscribers](https://platform.claude.com/docs/en/about-claude/api-credits-for-subscribers)). 이 앱은 일반 Claude API 호출이므로 코드 변경 없이 그 조직의 API 키를 `.env`에 넣으면 크레딧에서 차감됩니다. |
| (참고) claude.ai 로그인으로 호출 | 권장하지 않음 | Agent SDK 문서는 “사전 승인 없이 제3자 개발자가 자기 제품에 claude.ai 로그인이나 요금제 사용량을 제공하는 것을 허용하지 않는다”고 명시하고 API 키 인증을 쓰라고 합니다. 또 CLI 프로세스를 거치므로 실시간 응답에도 불리합니다. |
| 음성 인식·이미지 (OpenAI) | **방법 없음** | ChatGPT 구독에는 API 사용이 포함되지 않고 결제도 분리되어 있습니다 ([OpenAI 도움말](https://help.openai.com/en/articles/6950777-what-is-chatgpt-plus)). |

API 사용료를 줄일 수 있는 대안 (아직 구현하지 않음):

- **음성 인식 → 브라우저 Web Speech API**(Chrome 내장 인식). API 키와 사용료가 들지 않아 예산 가정상 가장 큰 항목인 STT 비용을 없앨 수 있습니다. 대신 다음과 같은 제약이 있습니다.
  - 음성이 브라우저 공급자(Chrome은 Google)의 서버로 전송됩니다.
  - 정확도, 구간 분할, 지연을 이 앱이 제어하거나 검증하기 어렵습니다.
  - 브라우저마다 지원이 다릅니다.
- **이미지**: 구독 경로가 없으므로 API 비용이 들거나 다른 제공자를 써야 합니다. 현재 기본값(quality low)이 가장 저렴한 설정입니다.

## 8. 사용자 요금제 기준 분석 (Claude 과학자용 Team · ChatGPT Plus · Google AI Pro, 2026-11-05)

| 요금제 | 이 앱에서 쓸 수 있는 것 | 조건과 주의 |
|---|---|---|
| Claude Team (과학자 할인) | **월간 API 크레딧 대상**: Standard 좌석 $20, Premium 좌석 $100, 팀 합산 최대 $500 | Team의 **Primary Owner 또는 Owner**만 받을 수 있습니다. Console 조직 1개에만 연결되며, 팀 전체가 같은 잔액을 씁니다. 크레딧이 떨어지면 요금이 청구되지 않고 요청이 멈춥니다. 팀(연구실 등) 공용 크레딧이라면 소유자의 허락이 필요합니다. |
| ChatGPT Plus | 없음 | API는 별도로 과금됩니다. 현재 구성(OpenAI 음성 인식과 이미지)은 전액 별도 비용입니다. |
| Google AI Pro | Google Developer Program의 월간 Google Cloud 크레딧 (검색 요약 기준 $10/월. 공식 Gemini 문서 페이지에는 금액이 없어 **미확인**) | Google Cloud 프로젝트와 **Cloud Billing 활성화가 필요**합니다(선불 방식은 잔액 $0 초과 필요). 앱의 API 키 호출에 적용되는지, 크레딧 소진 후 청구되는지 멈추는지는 문서에 명확히 나와 있지 않아 **미확인**입니다. 쓰려면 예산 알림이나 상한을 먼저 설정해야 합니다. |

Gemini API 가격 ([AI Studio 가격표](https://aistudio.google.com/docs/pricing), 2026-11-05):

- 음성 인식 `gemini-3.5-transcribe-live`
  - 무료 등급: 입력·출력 무료. 단, **무료 등급 콘텐츠는 Google 제품 개선에 사용**됩니다.
  - 유료: 오디오 입력 $0.005/분 + 텍스트 출력 $0.004/분, 문서상 혼합 약 $0.009/분. OpenAI `gpt-live-transcribe` $0.017/분의 약 절반입니다. 유료 등급은 제품 개선에 사용되지 않습니다.
- 이미지 생성: **무료 등급 없음**.
  - `gemini-3.1-flash-lite-image`: 1K(1024x1024) 장당 $0.0336
  - `gemini-3.1-flash-image`: 0.5K $0.045, 1K $0.067
  - gpt-image-2 low 표 가격($0.005)보다 비쌉니다. 16:9 비율을 지원하는지는 가격표에 없어 미확인입니다.
- 텍스트 `gemini-2.5-flash-lite`: 무료 등급 있음. 유료 $0.10/$0.40.

가능한 구성 (아직 구현하지 않음, 결정 필요):

| 구성 | 음성 인식 | 기획 | 이미지 | 별도 결제 | 해야 할 일 |
|---|---|---|---|---|---|
| A. 현재 | OpenAI | Claude (Team 크레딧) | OpenAI | OpenAI 결제 필요 | 없음 |
| B. OpenAI 제거 | Gemini transcribe-live | Claude (Team 크레딧) | Gemini 이미지 | Google Cloud Billing (Pro 크레딧이 적용되면 그 안에서) | Gemini 음성 인식·이미지 어댑터 구현, 오디오 형식 재확인, 새 검증 |
| C. Gemini 하나로 | Gemini | Gemini Flash-Lite | Gemini 이미지 | Google Cloud Billing | B에 더해 텍스트 어댑터 |

## 9. 결정: GPT + Gemini 구성 (2026-11-05)

**경위.** 사용자는 Claude 과학자용 Team의 **관리자(Admin)**이고 주 소유자는 아닙니다. 공식 도움말상 결제 설정(Organization settings > Billing)에는 Owner와 Primary Owner만 접근할 수 있고, API 크레딧은 그 메뉴에서 연결합니다. 따라서 Owner가 대신 받아 주지 않는 한 크레딧을 쓸 수 없습니다([Roles and permissions](https://support.claude.com/en/articles/9267276-roles-and-permissions)). 사용자 결정에 따라 **GPT + Gemini 구성**으로 바꿨습니다. Claude 어댑터는 `TEXT_PROVIDER=anthropic` 선택지로 남겨 두었습니다.

이 절은 3, 4, 6절의 기본값 설명을 대체합니다. 모든 값은 임시 설정이며 환경변수로 바꿀 수 있습니다.

| 기능 | 제공자 / 모델 (임시 기본) | 단가 (공식, 2026-11-05) | 고른 이유 |
|---|---|---|---|
| 음성 인식 | Gemini `gemini-3.5-transcribe-live` | 유료: 오디오 $0.005/분 + 텍스트 $0.004/분 (문서 각주의 혼합 추정 약 $0.009/분). 무료 등급 있음 | OpenAI `gpt-live-transcribe`($0.017/분)의 약 절반. 비용 가정에서 가장 큰 항목. Google AI Pro 크레딧이 적용될 가능성 |
| 기획 | OpenAI `gpt-6-luna`, reasoning effort `none` | $0.10 / $0.50 per 1M tok | 모델 페이지 설명이 "focused, high-volume tasks"용. 구조화 출력 지원. 이미지와 같은 계정 |
| 이미지 | OpenAI `gpt-image-2`, 1536x864, low, jpeg | 이미지 출력 $30 / 텍스트 입력 $5 per 1M tok (1536x1024 low 표 가격 $0.005) | Gemini 이미지 모델(최저 `gemini-3.1-flash-lite-image` 장당 $0.0336, 무료 등급 없음)보다 쌈. 임의 해상도 지원이 문서에 명시됨 |

**Gemini 전사 구현 요약** ([Live transcription 가이드](https://aistudio.google.com/docs/live-api/live-transcribe), [Live API reference](https://aistudio.google.com/api-reference/live)):

- **연결과 설정**
  - `BidiGenerateContent` WebSocket에 API 키를 `key` 쿼리로 넘깁니다. URL을 로그와 오류 메시지에 남기지 않으며, 테스트로 확인했습니다.
  - setup: `responseModalities: ["TEXT"]`, `inputAudioTranscription.languageCodes: ["ko-KR"]`, `realtimeInputConfig.automaticActivityDetection.disabled: true`
  - **`setupComplete`를 받은 뒤에만 ready**가 됩니다. 시간 초과(`ack_timeout`)나 setup 중 연결 종료(`rejected`)는 실패로 처리합니다.
  - Gemini는 OpenAI와 달리 실제 반영된 설정을 돌려주지 않습니다. 그래서 모델, 언어, 형식이 실제로 반영됐는지는 **프로토콜상 확인할 수 없고**, 점검 결과에 `not_verifiable_by_protocol`로 기록합니다.
- **오디오와 구간**
  - 16kHz PCM16입니다. 브라우저 AudioWorklet이 서버 설정의 샘플레이트를 읽어 리샘플링하며, 실제 Chrome에서 48k/44.1k → 16k 변환과 8kHz 초과 성분 감쇠(약 -52dB)를 확인했습니다.
  - 서버 VAD의 구간 경계를 `activityStart`/`activityEnd`로 전달합니다. 짧은 잡음은 보내지 않는다는 기존 규칙은 그대로 적용됩니다.
- **결과**
  - 임시 결과는 `interimInputTranscription`, 확정 결과는 `inputTranscription`입니다.
  - 구간 ID가 없어서, 한 연결 안에서는 순서대로 온다고 보고(`ordered_finals`) 바로 감지기에 넘깁니다.
- **세션 제한**: 세션은 최대 10분이라 `GEMINI_STT_ROTATE_S`(480초) 전후로 쉬는 구간에서 새 세션을 먼저 연 뒤 교체합니다. `goAway`를 받아도 교체합니다.

**새로 생긴 미검증 항목:**

- 모델 ID 표기 차이: Gemini API 문서는 `gemini-3.5-transcribe-live`, Google Cloud 문서는 `-preview` 접미사
- `customVocabulary` 요소 형식 (기본값은 보내지 않음)
- 한국어 정확도와 지연
- 무료 등급 속도 제한
- 확정 결과가 구간당 정확히 하나씩 오는지 (지표용 구간 매핑에만 영향)
- Google AI Pro 크레딧이 API 키 호출에 적용되는지, 크레딧 소진 후 청구되는지 멈추는지

**개인정보 주의.** Cloud Billing이 꺼진 프로젝트의 Gemini 키는 무료 등급이고, 가격표상 무료 등급 입력(강의 음성)은 **Google 제품 개선에 사용**됩니다. 유료 등급(결제 활성화)은 사용되지 않습니다. 실제 강의에 쓰기 전에 어느 등급으로 쓸지 정해야 합니다.

**예산 가정 (실측 아님).** 50분 강의, 생성 10장 기준입니다.

| 항목 | 가정 |
|---|---|
| 음성 인식 | 전송한 발화 35~50분 × $0.009 ≈ $0.3~0.45 (무료 등급이면 $0) |
| 기획 | 10장 × 1센트 미만 |
| 이미지 | 10장 × $0.005(대용 가정값) ≈ $0.06 |
| **합계** | **약 $0.4~0.5** (무료 등급 STT면 약 $0.07) |

**검증 수준 (2026-11-05):**

| 구성 요소 | 모델명 문서 확인 | 계정 권한 | 실제 호출 | 전체 시스템 |
|---|---|---|---|---|
| STT `gemini-3.5-transcribe-live` | ✅ (ID 표기 차이 있음) | ❌ 미검증 | ❌ | ❌ |
| 텍스트 `gpt-6-luna` | ✅ 모델 페이지 | ❌ 미검증 | ❌ | ❌ |
| 이미지 `gpt-image-2` | ✅ | ❌ 미검증 | ❌ | ❌ |
| 어댑터 요청 형식 | – | – | 로컬 가짜 서버 계약 테스트만 | mock·가짜 서버로 72개 테스트 |

### 9-1. 결정: Gemini 음성 인식은 무료 등급 (2026-11-05, 사용자 결정)

- 가격표상 무료 등급 입력(강의 음성)은 **Google 제품 개선에 사용**됩니다. 사용자는 이를 감수하고 무료 등급을 쓰기로 했습니다.
- 비용 추정에서 STT 단가는 `PRICE_STT_PER_MIN=0`으로 둡니다. 예산 가정 합계는 이미지와 기획만 남아 **50분 강의·10장 기준 약 $0.07**입니다(가정, 실측 아님).
- 무료 등급 한도는 문서에 숫자가 없습니다(프로젝트별로 AI Studio에서 확인, 초과 시 429). 50분 강의를 끝까지 버틸 수 있는지는 **미검증**입니다.
- 한도 초과로 끊기면 앱은 재연결을 시도하고 실패하면 오류 상태를 표시합니다. 그때는 텍스트 입력으로 계속 진행할 수 있습니다. 필요하면 결제를 켜 유료 등급(약 $0.009/분)으로 바꾸거나 `STT_PROVIDER=openai`로 바꿉니다.
