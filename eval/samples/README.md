# 테스트 음성

- `sample_ko.wav`: macOS 한국어 TTS(Yuna)로 만든 합성 음성입니다. 사람 녹음이 아닙니다. 24kHz 모노 16bit, 약 5.8초.
  - 문장: "다음 슬라이드에서는 과적합을 시험 문제를 외운 학생에 비유해서 설명하겠습니다."
  - 용도: STT 연결과 전사 수신 점검(`eval/check_providers.py --stt --wav eval/samples/sample_ko.wav`).
  - 실제 강의 음성의 정확도를 대표하지 않습니다.
