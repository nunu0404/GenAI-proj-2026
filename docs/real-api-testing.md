# 실제 API 테스트 절차

실제 호출은 **API 사용료가 발생**합니다. ChatGPT·Claude 구독과는 별도로 과금됩니다([model-cost-decision.md](model-cost-decision.md) §5).
결제 수단 등록, 충전, 사용 한도 설정은 계정 주인이 직접 정합니다. 아래 단계는 비용이 적은 것부터 하나씩 진행하도록 배열했습니다.

> API 키는 채팅, 이슈, 커밋에 절대 붙여 넣지 마세요. 실행하는 컴퓨터의 `backend/.env`에만 넣습니다. 이 파일은 `.gitignore`에 들어 있습니다(`git check-ignore -v backend/.env`로 확인).

## 0. 준비 (1회)

1. **키 발급** (현재 구성: 음성 인식은 Gemini, 기획과 이미지는 OpenAI)
   - OpenAI API 키: platform.openai.com → API keys. 기획과 이미지에 씁니다. 이미지 모델은 조직 인증이 필요할 수 있습니다.
   - Gemini API 키: Google AI Studio → API keys. 음성 인식에 씁니다.
     - ⚠ **Cloud Billing이 꺼진 프로젝트의 키는 무료 등급**입니다. 가격표상 무료 등급 입력(강의 음성)은 Google 제품 개선에 사용됩니다.
     - 유료 등급(결제 활성화)은 사용되지 않습니다. Google AI Pro의 월간 Cloud 크레딧도 결제 활성화가 전제입니다.
     - 어느 쪽으로 할지 먼저 정하세요.
   - (선택) Anthropic API 키: Claude Team 크레딧은 Owner만 받을 수 있습니다.
   - **현재 결정: Gemini는 무료 등급으로 씁니다(2026-11-05).**
     - AI Studio에서 결제를 켜지 않은 프로젝트로 키를 만들고, `.env`의 `PRICE_STT_PER_MIN=0`으로 둡니다.
     - 무료 등급 한도(분당·일당 요청 수 등)는 문서에 숫자가 없습니다. AI Studio의 해당 프로젝트 사용량 한도 화면에서 확인하세요. 한도를 넘으면 `429 RESOURCE_EXHAUSTED` 오류가 납니다.
     - 세션 교체(약 8분마다)와 재연결도 요청 수에 포함될 수 있습니다.
2. **권장**: 두 콘솔 모두 월 사용 한도와 알림을 낮게 설정해 둡니다(예: $5).
3. 설정 파일을 만듭니다.

   ```bash
   cd backend
   cp .env.example .env        # 이미 있다면 생략
   ```

   `.env`에서 아래 항목만 바꿉니다. 나머지는 임시 기본값을 그대로 둡니다.

   ```env
   STT_PROVIDER=gemini
   TEXT_PROVIDER=openai
   IMAGE_PROVIDER=openai
   OPENAI_API_KEY=여기에_직접_입력
   GEMINI_API_KEY=여기에_직접_입력
   ```

## 1. 제공자별 단일 호출 (`eval/check_providers.py`)

모든 명령은 저장소 루트에서 실행합니다. 결과는 `eval/results/provider_check_<시각>.json`에 저장되며 키는 저장되지 않습니다.
각 결과에는 `server_responded`(서버 응답) / `request_accepted`(요청 수락) / `result_valid`(유효한 결과)가 따로 기록됩니다.

| 단계 | 명령 | 확인하는 것 | 비용 가정 |
|---|---|---|---|
| A | `backend/.venv/bin/python eval/check_providers.py --stt` | STT 연결과 설정 완료 신호 수신 (Gemini는 `setupComplete`, 오디오 미전송) | 오디오를 보내지 않으므로 거의 0 |
| B | `… --stt --wav eval/samples/sample_ko.wav` | 한국어 전사 수신, 구간 종료 → 확정까지 걸린 시간 (WAV는 16kHz로 변환해 전송) | 약 6초 × $0.009/분 ≈ $0.001 (무료 등급이면 0) |
| C | `… --text` | `gpt-6-luna` 기획 1회: 구조화 JSON 검증, 지연, 토큰 | 1센트 미만 |
| D | `… --image --quality low` 그다음 `--quality medium` | 1536x864 생성 수락, 이미지 검증, 지연, 토큰 | 표 가격 기준 가정 약 $0.005 / $0.04. 1536x864 실제 가격은 응답 usage로 확인 |

**B에 쓸 음성 파일** (둘 중 하나):

```bash
mkdir -p eval/samples
# (1) macOS 한국어 TTS로 만든 파일 — 연결 점검용. 실제 사람 목소리가 아님
say -v Yuna -o /tmp/s.aiff "다음 슬라이드에서는 과적합을 시험 문제를 외운 학생에 비유해서 설명하겠습니다."
afconvert -f WAVE -d LEI16@24000 -c 1 /tmp/s.aiff eval/samples/sample_ko.wav
# (2) 직접 녹음 (QuickTime 등) 후 변환 — 전문용어·말투 확인용
afconvert -f WAVE -d LEI16@24000 -c 1 내녹음.m4a eval/samples/my_voice.wav
```

**실패했을 때 볼 곳**

- `stage=http_rejected` (401/403): 키나 권한 문제입니다.
- `stage=rejected`: 서버가 설정을 거부했습니다. 메시지에 이유가 나옵니다.
- `stage=unverifiable`: 승인 응답에 확인할 항목이 없습니다. 결과 JSON의 `effective_session`과 `session_check`를 보고 실제 응답 형식을 확인해 주세요. 형식이 문서와 다를 뿐 설정이 맞다면 그때 `STT_STRICT_SESSION_CHECK=false`로 진행하고, 이 사실을 DEVLOG에 기록합니다.
- 이미지 403이나 조직 인증 관련 메시지: OpenAI 조직 인증이 필요한 경우입니다.
- 이미지 400 (크기 관련): `IMAGE_SIZE=1536x1024`로 바꿔 다시 시도합니다.

## 2. 실제 마이크로 전체 흐름

```bash
# 터미널 1
cd backend && .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
# 터미널 2
cd frontend && npm run dev
```

1. Chrome에서 http://localhost:5173 을 열고 세션을 만든 뒤 **청중 화면 열기**를 누릅니다.
2. 상단 배지가 `STT: gemini-3.5-transcribe-live`, `텍스트: gpt-6-luna`, `이미지: gpt-image-2`이고 MOCK 표시가 없는지 확인합니다.
3. **● 마이크 시작** → 상태가 `STT 연결 중`에서 `듣는 중`으로 바뀌는지 확인합니다(설정 승인).
4. [lecture-scenarios.md](lecture-scenarios.md) 1번 시나리오를 말하면서 다음을 확인합니다.
   - 자막: 임시 결과 → 확정, 띄어쓰기, 전문용어
   - 감지 로그의 `생성 요청 확정`
   - 미리보기에 텍스트 → 이미지 → 준비 완료 순서로 나타나는지
   - 생성 중에도 자막이 계속 올라오는지
   - `→` 키로 넘겼을 때 청중 화면이 동기화되는지
5. **성능 지표** 패널의 `새로고침`으로 구간별 시간(n, 중앙값, p95)을 확인합니다.

## 3. 전체 흐름 5회 측정

```bash
backend/.venv/bin/python eval/latency_probe.py -n 5
# 비교가 필요할 때
backend/.venv/bin/python eval/latency_probe.py -n 5 --quality medium
# 다른 텍스트 모델과 비교하려면 .env 의 OPENAI_TEXT_MODEL / OPENAI_TEXT_REASONING 과 PRICE_TEXT_* 를 바꿔서 다시 실행
```

기획 시간, 이미지 시간, 총 대기 시간, 실패율, 토큰, 추정 비용이 `eval/results/latency_*.json`에 저장됩니다.

## 4. 기록

각 단계가 끝나면 `eval/results/`의 결과 파일을 커밋하고, `docs/DEVLOG.md`에 다음을 적습니다.

- 무엇을 실행했는지
- 성공한 단계 (응답 / 수락 / 결과)
- 측정값
- 실패와 원인

[model-cost-decision.md](model-cost-decision.md) §6 표의 '미검증' 칸도 갱신합니다. 측정이 끝나면 그 값을 근거로 텍스트 모델(Haiku 유지 여부)과 이미지 품질을 확정합니다.
