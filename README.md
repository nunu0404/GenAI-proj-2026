# NextSlide — 말하면 만들어지는 다음 슬라이드

강의하면서 “다음 슬라이드에서는 ○○를 설명하겠습니다”라고 말하면, 최근 강의 맥락을 반영한 **설명용 이미지와 새 웹 슬라이드**를 만들어 다음 장으로 준비해 주는 웹 프레젠테이션 시스템입니다. 결과물은 PPT 파일이 아니라, 같은 웹 시스템 안에서 넘기며 발표하는 슬라이드 쇼입니다.

- 음성 인식: OpenAI Realtime 전사(`gpt-live-transcribe`), 서버 중계 + 서버 VAD
- 슬라이드 기획: Claude(`claude-opus-5-5`), JSON 스키마 구조화 출력 + Pydantic 검증
- 설명 이미지: OpenAI Images(`gpt-image-2`, 1536x864 = 16:9)
- 세 가지 모두 **어댑터로 분리**되어 있고, 자격증명이 없으면 **mock 모드**로 동작합니다(화면에 MOCK 표시).

> ⚠ 현재 저장소의 검증 상태: 실제 API 키 없이 개발했습니다. 실제 제공자 코드는 공식 문서 기준으로 구현했고, 문서 형식을 흉내 낸 로컬 가짜 서버로 계약 테스트만 했습니다. **실제 API 호출 결과와 실제 생성 지연은 아직 측정하지 않았습니다.** 자세한 내용은 [docs/results.md](docs/results.md)에 있습니다.

## 빠른 시작 (mock, 자격증명 불필요)

필요: Python 3.11+, Node 20+, [uv](https://docs.astral.sh/uv/)(또는 pip)

```bash
# 1) 백엔드
cd backend
uv venv --python 3.11 .venv && uv pip install -r requirements.txt --python .venv/bin/python
cp .env.example .env            # 기본값은 모두 mock
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# 2) 프런트엔드 (다른 터미널)
cd frontend
npm install
npm run dev                      # http://localhost:5173 (API/WS 는 8000 으로 프록시)
```

빌드한 프런트엔드를 백엔드가 직접 서빙하게 하려면 `cd frontend && npm run build` 후 http://127.0.0.1:8000 에 접속합니다.

mock 모드에서는 음성 구간 감지(VAD)까지만 동작하고 전사는 하지 않습니다. 대신 발표자 화면의 **텍스트 입력 → “발화로 입력”**으로 확정 발화를 흉내 낼 수 있습니다. `|`로 나누면 여러 STT 구간으로 들어갑니다(예: `다음 슬라이드에서는 | 과적합을 학생에 비유해 | 설명하겠습니다`).

## 실제 API로 실행

`backend/.env`에서 다음을 설정합니다.

```env
STT_PROVIDER=openai
TEXT_PROVIDER=anthropic
IMAGE_PROVIDER=openai
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

- OpenAI 이미지 모델은 조직 인증(API Organization Verification)이 필요할 수 있습니다(OpenAI 문서).
- 제공자를 하나만 바꿔도 됩니다. 예를 들어 `TEXT_PROVIDER=anthropic`만 켜고 STT·이미지는 mock으로 둘 수 있습니다.
- 모델 ID, 이미지 크기와 품질, 타임아웃, 재시도 횟수, 단가는 모두 환경변수로 조정합니다([backend/.env.example](backend/.env.example)).
- 마이크는 `localhost` 또는 HTTPS에서만 동작합니다.

## 사용 흐름

1. 홈에서 강의 제목과 청중 수준을 입력하고 **세션 시작**을 누릅니다.
2. 발표자 화면에서 **청중 화면 열기**(별도 창)를 누르고, 필요하면 **전체 화면 발표**로 들어갑니다.
3. **● 마이크 시작**을 누르고 강의합니다. 자막은 임시 결과(회색)와 확정 결과로 나뉘어 표시됩니다.
4. “다음 슬라이드에서는 … 설명하겠습니다”라고 말하면 *요청 확정 → 텍스트 준비(미리보기 표시) → 이미지 생성 → 준비 완료* 순서로 진행됩니다. 이 동안 현재 장과 음성 인식은 그대로 유지됩니다.
5. **다음 ▶**, `→`, `PageDown`, `Space`로 넘깁니다. 입력창에 포커스가 있으면 방향키는 이동으로 처리되지 않습니다.
6. 실패하면 현재 장은 유지되고, **재시도** 또는 **이미지 없이 완료**를 선택할 수 있습니다. 주제가 불분명하면 **입력 보완 필요** 카드에 주제를 입력합니다.
7. 세션은 SQLite와 이미지 파일로 저장됩니다. 홈의 저장된 세션 목록에서 다시 열어 발표할 수 있습니다.

## 테스트와 평가

```bash
cd backend && .venv/bin/python -m pytest -q          # 47개: 감지·기획 검증·대기열·취소·복원·API/WS·VAD·제공자 계약
cd frontend && npm run typecheck && npm run build
backend/.venv/bin/python eval/run_detection_eval.py   # 요청 감지 정확도 (라벨 40개, API 불필요)
backend/.venv/bin/python eval/latency_probe.py -n 5   # 실제 생성 지연·실패율 (실제 API 필요, 비용 발생)
backend/.venv/bin/python eval/run_context_ab.py --images   # 맥락 A/B 블라인드 평가 자료 생성 (실제 API 필요)
python eval/score_ratings.py eval/results/context_ab_<시각>  # 사람이 채운 평가 시트 집계
```

## 저장소 구조

```
backend/app/
  main.py          FastAPI: REST, WebSocket(/ws/sessions/{id}), 이미지 제공, 빌드된 프런트 서빙
  runtime.py       세션 런타임: 감지 → 대기열 → 기획 → 이미지, 취소·재시도·보완·자동 전환
  detector.py      규칙 기반 다음 슬라이드 요청 감지 (구간 누적, 부정/인용/모호/끊김, 중복 방지)
  planner.py       맥락 기반 슬라이드 기획 프롬프트, 구조화 출력 검증과 제한적 복구, 이미지 프롬프트 조립
  stt_stream.py    오디오 형식 검증, 서버 VAD(20ms RMS), STT 제공자 중계, 발화 종료 추정
  providers/       어댑터: anthropic_text, openai_image, openai_stt, mock, 이미지 검증
  db.py            SQLite (세션·확정 발화·슬라이드·작업·사용량). 원시 음성은 저장하지 않음
  metrics.py       구간별 지연 통계(n/평균/중앙값/p95), 실패율, 비용 추정
frontend/src/
  pages/Presenter.tsx  발표자 화면    pages/Audience.tsx  청중 화면    pages/Home.tsx  세션 목록
  components/SlideView.tsx  구조화 데이터 → 고정 React 템플릿 (AI 생성 HTML/JS 실행 안 함)
  audio/mic.ts + public/pcm-worklet.js  마이크 → 24kHz PCM16 리샘플링(저역통과 FIR)
eval/              평가 데이터(라벨), 평가 스크립트, 결과
docs/              구조·데이터 흐름, 예시 강의 시나리오, 3분 시연 대본, 측정 결과와 한계
```

## 문서

- [docs/architecture.md](docs/architecture.md): 구조, 데이터 흐름, 상태 관리, 시간 측정 방법
- [docs/lecture-scenarios.md](docs/lecture-scenarios.md): 예시 강의 시나리오 3개
- [docs/demo-script.md](docs/demo-script.md): 3분 발표 시연 대본
- [docs/results.md](docs/results.md): 실행한 테스트, 실측 수치, 미검증 항목, 알려진 한계와 개선점
- [docs/DEVLOG.md](docs/DEVLOG.md): 날짜별 변경 사항과 결정, 검증 기록
