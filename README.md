# 핸즈프리 음성 AI 납땜 조교 (ATmega128 / TPK-128 V3.0)

학생이 양손으로 납땜하는 동안 **음성만으로** 부품의 값·극성·납땜 위치를 묻고 답을 듣는
추론형 실습 조교. 정확한 수치는 추측하지 않고 `get_part_info` 함수콜로 조회하고(환각 방지),
이유 설명·능동 코칭은 시스템 프롬프트로 처리한다.

> 음성 파이프라인(Whisper STT → GPT → TTS, half-duplex 에코방지, 브라우저 VAD)은
> `senior-smile-project` 의 검증된 코드를 재사용·개조했다.

## 구조

```
backend/
  main.py              FastAPI — /ws/voice(음성), /ws(자막 broadcast), /tts, /sounds
  voice_agent.py       음성 엔진 — STT/TTS/half-duplex + get_part_info function calling
  voice_socket.py      스레드↔async 브리지 (그대로 재사용)
  audio_transport.py   WS 전송 계층 격리 (그대로 재사용)
  part_info.py         지식베이스 로더 + get_part_info(환각 방지 정확값 조회)
  config.py            설정/키 로딩
  data/
    board_atmega128.json   보드 지식베이스 (엔진과 분리 — 보드 교체 시 이 파일만 교체)
frontend/
  src/audio/useVoiceClient.js   브라우저 마이크·VAD·재생 (그대로 재사용)
  src/components/SubtitleBar.*  자막 UI (재사용)
  src/App.jsx                   음성 + 자막 화면
```

## 실행

### 백엔드
```bash
cd backend
python -m venv .venv && . .venv/Scripts/activate   # Windows
pip install -r requirements.txt
cp .env.example .env        # OPENAI_API_KEY 입력
uvicorn main:app --host 0.0.0.0 --port 8000
```

### 프론트엔드
```bash
cd frontend
npm install
npm run dev                  # http://localhost:5173 (마이크 권한 허용)
```
프로덕션: `npm run build` → `backend/dist` 로 빌드되어 백엔드가 같이 서빙.

## 핵심 원칙
- **부품 값·극성·위치는 절대 추측 금지** → `get_part_info(reference)` 로만 조회.
- 지식베이스는 엔진과 분리(`data/board_*.json`). 단일 보드라 지금은 컨텍스트 주입,
  확장 시 `part_info.py` 만 RAG 조회로 교체하면 됨.
- API 키는 서버에만. 브라우저는 오디오만 WS로 주고받음(키 노출 없음).

## Tier0 시나리오
1. "R5 자리 저항 뭐야?" → 10kΩ + 색띠 읽는 방향
2. "이 LED 긴 다리 어디로 가?" → 긴 다리가 +
3. "전해 콘덴서 방향?" → 짧은 다리(흰 띠)가 -
