# 측정 결과, 미검증 항목, 한계

작성일: 2026-11-05. 환경: macOS(arm64), Python 3.11.14, Node 20.20, Chrome(헤드리스, Playwright로 조작).

**전제: 이 저장소는 실제 API 자격증명 없이 개발했습니다.** 아래 결과 중 실제 API 호출 결과는 없습니다. mock 실행 결과는 성능 수치로 보고하지 않습니다.

> 모델 선택 근거, 과금 경로, 단계별 검증 수준(모델명, 계정 권한, 실제 호출, 전체 동작)은 [model-cost-decision.md](model-cost-decision.md)에 있습니다. 2026-11-05 리뷰에서 지적된 음성 처리 문제 3건(전사 순서, 최소 발화 길이, 설정 승인 전 ready 표시)을 고쳤습니다.

## 1. 실행한 테스트

| 항목 | 결과 | 비고 |
|---|---|---|
| 백엔드 자동 테스트 (`pytest`) | **72개 통과** (약 11초) | mock 제공자 주입, 실제 API 호출 없음 |
| 프런트엔드 타입 검사와 빌드 | 통과 | `tsc -b`, `vite build` |
| 브라우저 E2E (헤드리스 Chrome, mock) | 통과 | 아래 항목 참고 |
| 오디오 리샘플러 검증 (실제 Chrome AudioWorklet) | 통과 | 아래 항목 참고 |

명세 7절의 테스트 항목과 대응 관계는 다음과 같습니다(`backend/tests/`).

| 요구 | 테스트 |
|---|---|
| 일반 발화에서는 생성하지 않음 | `test_detector::test_normal_speech_does_not_generate` |
| 완성된 지시에서는 한 번만 생성 | `test_detector::test_complete_instruction_generates_once` |
| 여러 STT 구간으로 나뉜 지시 | `test_detector::test_instruction_split_across_stt_segments`, `test_partial_request_waits_until_completion` |
| 중복 확정 이벤트에도 한 번만 생성 | `test_detector::test_duplicate_final_event_generates_once`, `test_runtime::test_duplicate_final_events_create_one_job` |
| 부정 지시 | `test_detector::test_negated_instruction_does_not_generate`, `test_runtime::test_negated_and_quoted_do_not_create_jobs` |
| 불명확한 주제의 보완 | `test_detector::test_unclear_topic_needs_input`, `test_runtime::test_unclear_request_needs_input_then_clarify`, `test_model_requests_clarification` |
| API 실패 후에도 기존 슬라이드 유지 | `test_runtime::test_image_failure_keeps_existing_slides_and_retry`, `test_text_failure_adds_no_slide`, `test_retryable_image_error_is_retried_bounded` |
| 취소된 작업의 늦은 결과 무시 | `test_runtime::test_cancelled_late_result_is_ignored` (사용량 `ignored_cancelled` 기록 포함) |
| 생성 도중에도 음성 인식 이벤트 처리 | `test_runtime::test_speech_events_processed_during_generation` |
| 세션 복원 | `test_runtime::test_session_restore_marks_interrupted`, `test_api_ws::test_presenter_audience_flow` (새로고침 후 스냅샷) |
| (PPTX 대신) 웹 발표: 청중 필터링·동기화 | `test_api_ws::test_presenter_audience_flow` |
| 맥락 고정 | `test_runtime::test_request_flow_ready_and_context_frozen` |
| 대기열 상한 | `test_runtime::test_queue_limit` (실행 1개, 대기 3개, 5번째 거부) |
| 자동 전환 조건 | `test_runtime::test_auto_advance_only_when_enabled_and_presenting` |
| 오디오 형식 거부와 VAD 구간 | `test_api_ws::test_mic_wrong_format_rejected_and_vad_segments` |
| 최소 발화 길이 (짧은 잡음은 STT로 보내지 않음) | `test_stt_stream::test_short_noise_is_not_sent_or_committed`, `test_noise_bursts_shorter_than_min_speech_never_reach_stt` |
| 전사 완료 순서 보정 / 실패·시간 초과 건너뛰기 / 늦은 결과는 감지 제외 | `test_stt_stream::test_out_of_order_finals_are_delivered_in_commit_order`, `test_failed_head_segment_is_skipped_immediately`, `test_missing_head_times_out_and_late_result_skips_detection`, `test_hard_timeout_when_no_result_at_all` |
| STT 승인 응답의 실제 설정 검증: 빈 응답, pcmu 형식, 세션 유형·모델 불일치는 실패 | `test_provider_contracts::test_empty_ack_session_is_unverifiable`, `test_pcmu_format_in_ack_is_mismatch`, `test_wrong_session_type_or_model_is_mismatch`, `test_full_ack_is_verified_and_non_strict_missing_warns` |
| Gemini 전사: setup 형식, 16kHz, activityStart/End, setupComplete 전 미준비, 거부, goAway·시간 기반 세션 교체, 키 비노출, VAD → 감지 전체 경로 | `test_gemini_openai_providers::*` |
| OpenAI 텍스트(Responses): strict JSON 스키마, reasoning none, store=False, 거절·미완료·401 | `test_gemini_openai_providers::test_openai_text_request_shape_and_errors` |
| 점검 스크립트가 429/400/503, 200이지만 이미지 없음을 성공으로 기록하지 않음 | `test_provider_contracts::test_outcome_levels`, `test_check_image_does_not_report_errors_as_success` |
| STT 설정 승인(`session.updated`) 후에만 ready, 거부·시간 초과·불일치 설정은 실패 | `test_provider_contracts::test_openai_stt_not_ready_without_ack`, `test_openai_stt_rejected_config_is_error`, `test_openai_stt_mismatched_effective_session_is_error`, `test_openai_stt_failed_segment_and_lost_on_disconnect` |
| 모델별로 허용되는 옵션만 전송 (Haiku에는 fallback 없음) | `test_provider_contracts::test_anthropic_haiku_sends_only_supported_options`, `test_request_options_reject_invalid_combinations` |
| 구조화 출력 검증과 제한적 복구 | `test_planner_and_images::*` (재요청 1회 상한, 불릿 초과 절단, 길이 초과 거부) |
| 이미지 검증 | `test_planner_and_images::test_image_validation` (MIME, 크기, 깨진 데이터, 비율) |
| 키 미노출, 경로 조작 방지 | `test_api_ws::test_config_never_exposes_keys`, `test_image_path_traversal_rejected` |
| 실제 어댑터 계약 (가짜 서버) | `test_provider_contracts::*`: Realtime `session.update` 형태, base64 오디오, Bearer 헤더, `item_id` ↔ VAD 구간 매핑, 중복 completed 무시, 연결 끊김 시 재연결 / Messages `output_config`·`fallbacks`·beta 헤더, 거절·인증 오류 / Images 요청 형태, 이미지 없음·형식 오류·안전 거절·503 재시도 가능 |

> 계약 테스트는 **공식 문서를 제가 읽은 대로** 만든 가짜 서버를 상대로 한 것입니다. 실제 서버가 문서와 다르게 동작하면 통과하더라도 실패할 수 있습니다.

### 브라우저 E2E (mock, 헤드리스 Chrome)

다음 단계를 자동으로 확인했습니다.

- 홈 → 세션 생성 → 발표자 화면
- 일반 발화 입력 후 3구간으로 나뉜 요청 입력 → `이미지 생성 중` 상태에서 미리보기에 텍스트가 먼저 표시됨 → 이 동안 청중 화면은 표지를 유지함 → 준비 완료
- 입력창에 포커스가 있을 때 `→` 키를 눌러도 장이 바뀌지 않음, 본문에 포커스가 있을 때는 `→`로 이동하고 청중 화면이 동기화됨
- 청중 화면에 자막, 패널, 상태 칩, MOCK 배지, STT 표기가 없음
- 모호한 요청을 넣으면 `입력 보완 필요` 표시
- 전체 화면 발표 모드 진입과 방향키 이동, 좁은 화면(390px) 배치

이 과정에서 버그 두 가지를 발견해 고쳤습니다.

1. 텍스트 제출 후 응답이 오면 입력창을 비우는 구조라서, 그사이 새로 입력한 내용이 지워졌습니다.
2. 미완성 장을 청중에게서 숨기려고 보낸 `slide.removed` 이벤트가 발표자에게도 전달됐습니다.

### 오디오 리샘플러 (실제 Chrome AudioWorklet, 오실레이터 입력)

| 컨텍스트 샘플레이트 | 입력 톤 | 출력 청크 | 추정 주파수 | 최대 진폭 |
|---|---|---|---|---|
| 48,000 Hz | 440 Hz | 2400 샘플(100ms @ 24kHz) | 440 Hz | 16383 |
| 44,100 Hz | 1,000 Hz | 2400 | 1000 Hz | 16373 |
| 16,000 Hz | 440 Hz | 2400 | 440 Hz | 16383 |
| 48,000 Hz | 15,000 Hz (24kHz 나이퀴스트 초과) | 2400 | 0 | 0 (저역통과로 제거) |
| 48,000 Hz → **16kHz 목표** | 440 Hz | 1600 (100ms @ 16kHz) | 440 Hz | 16384 |
| 44,100 Hz → 16kHz 목표 | 1,000 Hz | 1600 | 1000 Hz | 16305 |
| 48,000 Hz → 16kHz 목표 | 9,000 Hz (16kHz 나이퀴스트 초과) | 1600 | (잔여 성분) | 42 (약 -52dB 감쇠) |

## 2. 실측 수치

### 요청 감지 정확도 (`eval/run_detection_eval.py`, 라벨 40개, 결정적, API 미사용)

- 전체 정확도(3분류: request / needs_input / none): **36/40 (90.0%)**
- 잘못 생성(정답이 request가 아닌데 생성): **1건**, 놓친 생성: **0건**

| 범주 | n | 정답 |
|---|---|---|
| 명확한 지시 | 10 | 10 |
| 여러 구간으로 나뉜 지시 | 4 | 4 |
| 일반 설명 | 8 | 6 |
| 부정 지시 | 5 | 5 |
| 인용된 지시 | 4 | 3 |
| 모호한 지시 | 5 | 4 |
| 중간에 끊긴 지시 | 4 | 4 |

오답 4건:

- `normal-06` “다음 페이지에 있는 표를 보시면 됩니다.”
- `normal-07` “지난 시간에 다음 장 내용을 미리 읽어 오라고 했죠.”
- `quoted-04` “…다음 슬라이드에서는 무엇을 설명하겠습니다 같은 문장을 인식합니다.”

위 세 건은 생성하지 않아야 할 발화를 입력 보완 요청으로 판단했습니다. 슬라이드는 생성되지 않지만 불필요한 카드가 생깁니다.

- `ambiguous-04` “그거, 아까 그 예시 설명할게요.”

이 한 건은 “예시”를 주제로 인정해 **잘못 생성**했습니다.

> 주의: 평가 세트는 감지 규칙을 만든 개발자가 직접 작성했으므로 결과가 낙관적일 수 있습니다. 실제 STT 출력(띄어쓰기, 구두점 오류)으로 측정한 결과가 아닙니다. 오답 사례에 맞춰 규칙을 다시 고치지는 않았습니다.

### 클라이언트 렌더링

mock 모드 E2E 두 번 실행에서 `준비 이벤트 수신 → 브라우저 렌더링 완료`가 각각 n=1, 12.5ms와 6.2ms였습니다. 로컬 이미지와 mock 조건이라 실제 사용 환경을 대표하지 않습니다.

### 생성 지연과 실패율 — **측정하지 않음**

명세 8절 3단계(“샘플 5개로 실제 생성 시간과 실패 형태 확인”)는 API 키가 없어 수행하지 못했습니다. 측정 도구는 준비되어 있고 mock으로 끝까지 동작함을 확인했습니다.

```bash
# backend/.env 에 키와 제공자를 설정한 뒤
backend/.venv/bin/python eval/latency_probe.py -n 5
```

이 스크립트는 기획, 이미지, 전체 구간의 n·평균·중앙값·p95, 실패율과 오류 코드를 출력하고 `eval/results/latency_*.json`에 저장합니다. 텍스트 입력 경로이므로 발화 종료 기준 지연은 “계산 불가”로 기록됩니다. 음성 경로의 `VAD 추정 발화 종료 → 준비 완료`는 실제 마이크로 사용할 때 앱의 **성능 지표** 패널에 쌓입니다.

### 맥락 효과 A/B — **평가하지 않음**

`eval/context_scenarios.json`(시나리오 12개)과 `eval/run_context_ab.py`(A: 요청만 / B: 요청 + 최근 발화 + 현재 장, 나머지 조건 고정)를 준비했습니다. 이 스크립트는 순서를 섞은 `review.html`, `rating_sheet.csv`, 별도의 `key.json`을 만들고, 집계는 `eval/score_ratings.py`로 합니다. mock으로 하네스가 동작함을 확인했을 뿐, **실제 생성과 사람 평가는 하지 않았으므로 점수가 없습니다.**

## 3. 미검증 항목

| 항목 | 상태 | 확인 방법 |
|---|---|---|
| OpenAI Realtime 전사 실제 연결 (`gpt-live-transcribe`, `languages`, `delay`, `turn_detection: null`) | 문서 기준 구현, 가짜 서버 계약 테스트만 수행 | `STT_PROVIDER=openai`로 마이크 시작 |
| Claude 실제 호출 (임시 기본 `claude-haiku-5-5`, effort low, `output_config.format`) | 문서와 SDK 시그니처 기준 구현, 가짜 서버 계약 테스트 | `eval/check_providers.py --text` |
| `gpt-image-2`의 사용자 지정 크기 1536x864, quality low | 문서에 “gpt-image-2는 조건을 만족하는 어떤 해상도든 받는다”고 명시. 실제 계정에서는 미확인 | 거부되면 `IMAGE_SIZE=1536x1024`. 비율 검증 기준도 자동으로 그 크기를 따름 |
| 실제 생성 지연, 실패 형태, 비용 | 미측정 | `eval/latency_probe.py` |
| 한국어 STT 정확도, VAD 임계값(450)의 적절성 | 미측정 | 실제 마이크와 강의실에서 `VAD_RMS_THRESHOLD` 조정 |
| 실제 마이크 캡처 (브라우저) | 헤드리스 Chrome에서는 이 환경의 `getUserMedia`가 응답하지 않아 자동화하지 못함. 리샘플러와 서버 오디오 경로는 각각 따로 검증 | 일반 Chrome에서 직접 확인 |
| Firefox / Safari 오디오 | 미확인 | |
| 생성 이미지에 글자가 섞이지 않는지 | 프롬프트로만 금지. 검사 단계 없음 | 실제 생성물을 눈으로 확인 |
| 맥락 A/B 효과 | 미평가 | `eval/run_context_ab.py` 실행 후 블라인드 평가 |

## 4. 알려진 한계

- **감지기는 규칙 기반입니다.** 위 오답처럼 “다음 장/페이지”가 들어간 일반 서술문을 입력 보완으로 띄우거나, 애매한 지시어 뒤의 일반 명사(“예시”)를 주제로 인정하는 경우가 있습니다. 명세에 있는 “필요한 경우 LLM으로 의도를 구조화”는 기획 단계 LLM의 `needs_clarification` 필드로만 반영했고, 경계 사례 전용의 별도 LLM 의도 분류 단계는 없습니다.
- 서버 VAD는 단순 에너지(RMS) 방식이라 소음이 큰 환경에서는 구간 분할이 부정확할 수 있습니다. VAD 추정 발화 종료 시각에는 브라우저→서버 전송 지연이 들어가지 않습니다.
- 새 장은 덱의 맨 뒤에 추가됩니다. 현재 장이 맨 뒤가 아닐 때(앞 장으로 돌아가 있을 때)는 바로 다음 위치에 끼워 넣지 않습니다.
- 레이아웃은 표지와 “제목 + 핵심 문장 + 큰 이미지” 하나뿐입니다. 좌우 비교형과 이미지 중심형, 음성 수정 명령(“그림만 다시”)은 구현하지 않았습니다.
- 단일 프로세스와 메모리 대기열을 사용합니다. 서버를 여러 워커로 띄우면 안 됩니다. 인증이 없으므로 `127.0.0.1`에 바인딩해 개인 환경에서만 사용해야 합니다.
- 비용은 응답의 토큰 사용량 × 환경변수 단가로 추정합니다. STT 비용은 서버가 실제로 보낸 오디오 길이(발화 구간과 프리롤)로 추정하므로 실제 청구 방식과 다를 수 있습니다.
- 한글 글꼴은 Google Fonts의 Noto Sans KR을 쓰고, 오프라인이면 Apple SD Gothic Neo / Malgun Gothic으로 대체됩니다. 텍스트가 넘치면 글자 크기를 최대 20%까지 줄이고, 그래도 넘치면 발표자 화면에 `텍스트 넘침` 경고를 띄웁니다.

## 5. 다음 개선점

1. 실제 키로 `latency_probe.py`(n≥5)를 실행해 지연, 실패율, 비용 기준선을 기록합니다. 그 결과로 `TEXT_EFFORT`와 `IMAGE_QUALITY`를 정합니다.
2. 실제 STT 출력을 모아 감지 평가 세트를 확장하고, 경계 사례(needs_input 후보)에만 작은 LLM 의도 분류를 붙입니다.
3. `run_context_ab.py`를 실행하고 평가자 2명 이상이 블라인드로 채점합니다(평가자 간 일치도 포함).
4. 신경망 기반 VAD로 교체하고, 소음 환경에서 임계값을 자동으로 보정합니다.
5. 레이아웃 2종을 추가하고, 그림만 다시 만들기·본문 줄이기 같은 음성 수정 명령을 지원합니다.
