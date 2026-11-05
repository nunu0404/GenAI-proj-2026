# 개발 기록 (DEVLOG)

변경 사항, 결정, 검증 결과를 날짜순으로 기록합니다. 새 항목은 맨 아래에 추가합니다.
각 항목에는 **무엇을 바꿨는지, 왜 바꿨는지, 어떻게 검증했는지, 남은 일**을 적습니다.

---

## 2026-11-05 — MVP 초기 구현

**범위**
- 명세를 수정해 결과물을 PPTX가 아닌 웹 슬라이드 쇼로 바꿨습니다. python-pptx와 PPTX 내보내기는 범위에서 뺐습니다.
- 백엔드: FastAPI, SQLite, WebSocket. 구성은 감지기, 세션 런타임(작업 대기열), 기획기, 제공자 어댑터, 서버 VAD입니다.
- 프런트엔드: React, TypeScript, Vite. 화면은 발표자 화면, 청중 화면(별도 창), 홈(세션 목록)입니다. 오디오는 AudioWorklet에서 24kHz로 리샘플링합니다.

**제공자 선택** (2026-11-05 공식 문서 확인)
- STT: OpenAI `gpt-live-transcribe`, `wss://api.openai.com/v1/realtime?intent=transcription`, `audio/pcm` 24kHz, `turn_detection: null`
  - 서버 VAD를 지원하지 않으므로 이 앱의 서버 VAD가 구간 끝에서 `input_audio_buffer.commit`을 보냅니다.
- 텍스트: Claude `claude-opus-5-5`, `output_config.format` JSON 스키마, `fallbacks: "default"` (beta `server-side-fallback-2026-07-01`)
- 이미지: OpenAI `gpt-image-2`, 사용자 지정 크기 1536x864 (16:9)
- 실제 API 키가 없어 세 제공자 모두 mock 모드로 개발했습니다.

**주요 결정**
- 요청 감지는 규칙 기반으로 하고, 일반 발화마다 LLM을 호출하지 않습니다. 완료 표현이 나오거나 2.5초 침묵하면 판단합니다.
- 맥락은 요청 확정 시점에 고정합니다(최근 90초, 최대 1500자, 현재 장 포함).
- 작업자 1개가 작업을 하나씩 실행하고, 대기는 최대 3개입니다. 취소할 때 외부 호출은 끊지 않고 결과만 버리며 사용량은 기록합니다.
- 슬라이드는 `ready` 상태인 장만 이동 대상이 되고 청중에게 전송됩니다. 자동 전환은 기본 OFF입니다.

**검증**
- pytest 47개 통과. 실제 어댑터는 로컬 가짜 서버로 계약 테스트를 했습니다.
- 프런트엔드 타입 검사와 빌드를 통과했고, 헤드리스 Chrome E2E(mock)도 통과했습니다.
- 요청 감지 평가: 40건 중 36건(90.0%), 잘못 생성 1건, 놓친 생성 0건 → `eval/results/detection_results.md`
- E2E에서 발견해 고친 버그: 입력창 지움 경합, 미완성 장을 숨기는 이벤트가 발표자에게도 전달되던 문제, 마이크 시작이 무한 대기하던 문제(시간 제한 추가)

**미완료 / 다음 할 일**
- 실제 API 키로 `eval/latency_probe.py -n 5` 실행해 지연, 실패율, 비용 기준선 기록
- 실제 브라우저에서 마이크와 STT 확인, `VAD_RMS_THRESHOLD` 조정
- `eval/run_context_ab.py` 실행 후 블라인드 평가
- 자세한 내용은 `docs/results.md` 참고

---

## 2026-11-05 (2) — 리뷰 반영: 음성 처리 3건 수정, 임시 모델·품질 기본값, 검증 수준 정리

**계기**
외부 리뷰(e10b3dd 기준)에서 실제 마이크 시연 전에 고쳐야 할 음성 처리 문제 3건이 지적됐습니다. 사용자는 실시간 반응과 낮은 비용을 우선하며, 모델은 임시 설정으로 두고 환경변수로 교체할 수 있게 해 달라고 요청했습니다.

**변경**
1. 전사 완료 순서 보정 (`stt_stream.py`)
   - commit 순서대로 보관했다가 앞 구간부터 감지기에 전달합니다.
   - 앞 구간이 실패하면 즉시 건너뜁니다. 뒤 구간이 도착한 상태에서 앞 구간이 3초 넘게 오지 않거나, 어떤 결과도 10초 넘게 오지 않아도 건너뜁니다.
   - 건너뛴 구간이 늦게 도착하면 자막과 기록에만 남기고 감지에는 쓰지 않습니다.
   - 어댑터는 재연결로 잃은 구간과 전사 실패 구간을 `segment_failed`로 알립니다.
2. 최소 발화 길이 실제 적용
   - 유성 누적이 `VAD_MIN_SPEECH_MS` 미만인 구간은 STT로 보내지도 commit하지도 않습니다(후보 구간을 서버에 보관해 두는 방식).
3. STT 설정 승인 확인
   - `session.update` 후 `session.updated`를 받고 실제 반영된 설정(모델, 샘플레이트, turn_detection=null)을 검증한 뒤에만 ready로 전환합니다.
   - 설정 거부(`error`), 승인 시간 초과, 설정 불일치는 `error` 상태와 사유로 표시합니다. 승인 이후의 서버 오류는 `degraded`로 표시합니다.
4. 텍스트 모델 임시 기본값을 `claude-opus-5-5`에서 **`claude-haiku-5-5`**로 바꾸고 effort는 low로 둡니다.
   - 어댑터는 모델마다 허용되는 옵션만 보냅니다. fallback은 Opus 5.5/Sonnet 5.5/Fable에만, `thinking: disabled`는 Haiku 5.5/Opus 5에서 effort가 high 이하일 때만 보냅니다.
5. 이미지 임시 기본 품질을 medium에서 **low**로 바꿨습니다(jpeg, 1536x864 명시).
   - 작업마다 이미지 설정, 생성 시간, 토큰, 추정 비용을 `jobs.metrics`에 기록하고, 텍스트 기획 토큰과 비용도 함께 기록합니다.
6. `eval/check_providers.py`를 추가했습니다.
   - 전사, 기획, 이미지를 각각 실제로 한 번씩 점검하고 결과를 단계별(설정 승인 또는 호출 성공, 결과 수신, 시간, 토큰, 비용)로 기록합니다.
7. `latency_probe.py`에 `--quality`, `--text-model`, `--effort` 비교 옵션을 추가했습니다.
8. 계약 테스트가 사용자 환경의 프록시를 타지 않도록 프록시 환경변수를 제거하고 `NO_PROXY`를 설정했습니다(리뷰어 환경에서 2개가 실패했던 원인).
9. 문서: `docs/model-cost-decision.md`(모델 선택 근거, 과금 경로, 예상 비용, 검증 수준)를 새로 만들고 README, results, architecture를 갱신했습니다.

**확인한 문서 (2026-11-05)**
- Realtime 전사: `server_vad`/`semantic_vad` 미지원, `turn_detection: null`, `languages`/`delay`, 완료 순서 비보장.
- Realtime 서버 이벤트: `session.update` 적용 시 `session.updated`.
- 이미지: gpt-image-2는 조건을 만족하는 임의 해상도를 지원. 1536x1024 기준 low $0.005, medium $0.041. low는 빠른 초안용, jpeg가 png보다 빠름.
- Anthropic 가격: Haiku 5.5 $0.10/$0.50, Sonnet 5.5 $2/$10, Opus 5.5 $4/$20.
- 과금: OpenAI와 Anthropic API 모두 구독과 별도. Claude Max/Ultra/Team에는 연결해서 쓰는 월간 API 크레딧이 있음.

**검증**
- pytest 59개 통과.
- 새 음성 처리 테스트 6개는 이전 코드(e10b3dd)에서 5개가 실패하고 수정 후 모두 통과합니다.
- 프런트엔드 타입 검사와 빌드를 통과했습니다.
- 키 없이 `check_providers.py`를 실행하면 세 단계 모두 "미검증"으로 보고하고 결과 파일을 만들지 않습니다.

**여전히 미검증**
- 실제 API 연결, 계정 권한, 호출 성공, 전체 흐름. 실제 지연과 비용.
- 결제, 충전, 키 발급은 하지 않았습니다.

**다음 할 일 (리뷰 권장 순서)**
1. `check_providers.py --stt`(승인만) → `--stt --wav`(한국어·전문용어·구간 분할 확인)
2. `--text`, `--image --quality low`/`medium` 각 1회
3. `latency_probe.py -n 5`로 기획, 이미지, 총 대기 시간, 비용 기록
4. 그 결과로 텍스트 모델(Haiku 유지 여부)과 이미지 품질 확정

---

## 2026-11-05 (3) — 2차 리뷰 반영: STT 승인 설정 엄격 검증, 점검 결과 단계 분리, 비용 표현 정정

**계기**
2차 리뷰(893ed3f 기준)에서 두 가지가 지적됐습니다.
- 승인 응답에 항목이 없으면 검증을 건너뛰어서, 빈 응답 `{}`나 `audio/pcmu` 형식도 통과했습니다.
- `check_providers.py`가 429/400/5xx를 '호출 성공'으로 기록할 수 있었습니다.

비용 수치는 실측이 아니라 예산 가정으로만 봐야 한다는 지적도 있었습니다.

**변경**
1. `openai_stt._check_effective`
   - 필수 항목을 모두 대조합니다: `session.type`=transcription, 전사 모델, `audio.input.format.type`=audio/pcm, `format.rate`=24000. turn_detection은 값이 있으면 null이어야 합니다.
   - 값이 다르면 `mismatch`로 실패합니다.
   - 항목이 없으면 `unverifiable`로 실패합니다(`STT_STRICT_SESSION_CHECK=true`가 기본). false로 두면 '미검증 항목' 경고를 띄우고 진행합니다.
   - `SttSessionError`에 실패 단계를 기록합니다: config / connect_failed / http_rejected / closed_before_ack / ack_timeout / rejected / mismatch / unverifiable.
2. `ProviderError`와 `PlanError`에 `http_status`를 추가했습니다. 응답을 받지 못했으면 None이고, 200인데 내용이 잘못됐으면 200입니다.
3. `check_providers.py`는 `server_responded` / `request_accepted` / `result_valid` / `http_status`를 따로 기록합니다. 실패해도 지연과 토큰을 남깁니다.
4. 문서: 비용을 **예산 가정**으로 정정했습니다. 1536x864 가격을 픽셀 수로 환산하던 문장을 없애고, 실제 비용은 usage × 단가로만 판단한다고 적었습니다.
5. `docs/real-api-testing.md`(실제 테스트 절차)와 `eval/samples/sample_ko.wav`(macOS 한국어 TTS 합성 음성, 연결 점검용)를 추가했습니다.

**검증**
- pytest 65개 통과.
- 리뷰 재현 사례(빈 응답, pcmu, 세션 유형·모델 불일치) 테스트 4개는 이전 코드에서 4개 모두 실패하고 수정 후 통과합니다.
- 가짜 이미지 서버로 429/400/503/'200인데 이미지 없음'/정상의 단계 기록을 테스트했습니다.
- 키 없이 `check_providers.py`를 실행하면 모든 단계가 None(미시도)이고 결과 파일을 만들지 않습니다.

**여전히 미검증**
- 실제 API의 `session.updated` 응답 형식(이 검증 로직이 실제 응답과 맞는지)
- 실제 호출, 지연, 비용 전부

**다음 할 일**: `docs/real-api-testing.md`의 1-A부터 차례로 진행합니다.
