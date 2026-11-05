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
