"""
핸즈프리 납땜 실습 조교 — 음성 엔진.

senior-smile-project/backend/voice_agent.py 의 음성 루프(Whisper STT → LLM → TTS,
half-duplex 에코 방지, 브라우저 오디오 I/O)를 재사용하고, 노인 케어 로직을 들어낸 뒤
조교용 시스템 프롬프트 + get_part_info function calling 으로 교체한 버전.

상태 머신(half-duplex, 에코 방지):
  LISTENING ──발화──▶ THINKING ──응답 TTS──▶ SPEAKING ──playback_done──▶ LISTENING
  · SPEAKING 동안 is_speaking=True → 인입 오디오 전량 드롭(서버측 최종 안전망)
"""
import os
import time
import json
import queue
import tempfile
import threading
import collections

from openai import OpenAI

import config
from part_info import get_part_info, board_context


SYSTEM_PROMPT = (
    "너는 ATmega128(TPK-128 V3.0) 납땜 실습 조교다. 학생은 양손으로 납땜 중이라 화면을 못 보고 "
    "음성만으로 부품의 값·극성·납땜 위치를 묻는다.\n"
    "\n"
    "[행동 원칙]\n"
    "- 부품의 값·극성·위치·색띠·조립순서는 반드시 get_part_info 도구로 조회해서 답한다. "
    "조회 없이 수치를 지어내지 마라. 도구가 못 찾으면(found=false) 추측하지 말고 '그건 데이터에 없어 모르겠어'라고 말한다.\n"
    "- 학생이 자주 헷갈리는 두 가지는 묻기 전에 먼저 짧게 경고한다: "
    "(1) 저항 색띠 읽는 방향, (2) 극성 부품(LED·전해 콘덴서·다이오드·IC)의 다리/홈 방향.\n"
    "- 답할 때 이유를 한 문장 덧붙인다. 예: '허용오차 띠가 끝이라 반대쪽부터 읽어.'\n"
    "- 음성으로 듣기 좋게: 2~3문장 이내, 짧고 명확하게, 한국어로. 기호·괄호 나열 대신 말하듯이.\n"
    "- 단위는 또박또박 읽어준다(예: '10킬로옴', '470옴').\n"
    "\n"
    "[보드 지식]\n" + board_context()
)

# get_part_info function calling 스키마
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_part_info",
            "description": (
                "TPK-128 보드 부품의 정확한 값·극성·색띠·납땜 위치·조립순서(봉투)를 조회한다. "
                "부품 값/극성/위치를 답하기 전에 반드시 호출한다."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "reference": {
                        "type": "string",
                        "description": "부품 레퍼런스 지정자. 예: R5, R13, D1, C2, U1, U4, AR1, TR5, X1, L1, BZ1",
                    }
                },
                "required": ["reference"],
            },
        },
    }
]


class VoiceAgent:
    def __init__(self, device_id: str = "default"):
        if not config.OPENAI_API_KEY or config.OPENAI_API_KEY.startswith("여기에"):
            print("[VoiceAgent] ⚠️ OPENAI_API_KEY 미설정. backend/.env 를 확인하세요.")
        self.client = OpenAI(api_key=config.OPENAI_API_KEY)

        self.device_id = device_id
        self.is_running = False
        self.is_active = True

        # 화면 자막용 상태(/ws 가 폴링해 프론트로 broadcast)
        self.current_subtitle = ""     # 조교(AI) 발화
        self.current_user_text = ""    # 학생 STT transcript
        self.is_listening = False

        self.chat_history = collections.deque(maxlen=8)

        # TTS 임시 파일(기기별 — 다중 기기 충돌 방지)
        self.temp_voice_path = str(config.SOUNDS_DIR / f"temp_voice_{device_id}.mp3")

        # ── 오디오 I/O (브라우저가 마이크/스피커 담당, transport-agnostic) ──
        self.audio_in: queue.Queue = queue.Queue()   # 브라우저 VAD가 끊은 발화 WAV bytes
        self.audio_out = None                          # {type:'speak',url} 송신 콜백(main.py 주입)
        self.is_speaking = False                       # half-duplex: 재생 중 인입 드롭
        self.playback_done = threading.Event()         # 클라 재생완료 신호

    # ──────────────────────────── 세션 ────────────────────────────
    def start_conversation(self):
        if self.is_running:
            return
        self.is_running = True
        self.chat_history.clear()
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def stop_conversation(self):
        self.is_running = False

    def _run_loop(self):
        """메인 루프: 브라우저 발화 큐 소비 → 조교 응답. 호출어 없이 항상 듣는 핸즈프리."""
        print(f"[VoiceAgent:{self.device_id}] 시작 — 납땜 조교 (브라우저 오디오 입력)")
        while self.is_running:
            try:
                if not self.is_active:
                    self.is_listening = False
                    time.sleep(0.3)
                    continue

                user_text = self.listen()
                if not user_text:
                    continue

                print(f"[학생] {user_text}")
                self._handle_user_input(user_text)
                time.sleep(0.2)
            except Exception as e:
                self.is_listening = False
                print(f"[VoiceAgent] 루프 에러: {e}")
                time.sleep(1)
        print(f"[VoiceAgent:{self.device_id}] 종료")

    def _handle_user_input(self, user_text: str):
        self.chat_history.append(f"학생: {user_text}")
        response_text = self.get_response(user_text)
        print(f"[조교] {response_text}")
        self.speak(response_text)
        self.chat_history.append(f"조교: {response_text}")

    # ──────────────────────── LLM + 함수콜 ────────────────────────
    def get_response(self, text: str) -> str:
        """GPT 응답 생성. get_part_info 함수콜이 오면 조회 결과를 다시 넣어 최종 답을 만든다."""
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for msg in self.chat_history:
            role = "user" if msg.startswith("학생") else "assistant"
            messages.append({"role": role, "content": msg})
        messages.append({"role": "user", "content": text})

        try:
            for _ in range(4):  # 함수콜 루프 가드
                resp = self.client.chat.completions.create(
                    model=config.CHAT_MODEL,
                    messages=messages,
                    tools=TOOLS,
                    tool_choice="auto",
                    temperature=0.3,
                    max_tokens=250,
                )
                msg = resp.choices[0].message

                if not msg.tool_calls:
                    return (msg.content or "").strip()

                # assistant(tool_calls) → tool 결과를 messages 에 누적 후 재호출
                messages.append({
                    "role": "assistant",
                    "content": msg.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                        }
                        for tc in msg.tool_calls
                    ],
                })
                for tc in msg.tool_calls:
                    if tc.function.name == "get_part_info":
                        try:
                            args = json.loads(tc.function.arguments or "{}")
                        except json.JSONDecodeError:
                            args = {}
                        result = get_part_info(args.get("reference", ""))
                    else:
                        result = {"error": f"unknown tool {tc.function.name}"}
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(result, ensure_ascii=False),
                    })

            return "조회가 좀 꼬였어요. 부품 번호를 다시 말해줄래요?"
        except Exception as e:
            print(f"[VoiceAgent] Chat API 에러: {e}")
            return "잠깐만요, 연결이 끊겼나 봐요. 다시 한 번 말해줄래요?"

    # ──────────────────────── 오디오 입력 ────────────────────────
    def listen(self) -> str:
        """브라우저 발화 큐(audio_in)에서 다음 발화를 꺼내 Whisper로 인식. half-duplex 드롭 적용."""
        if not self.is_active:
            self.is_listening = False
            return ""
        self.is_listening = True
        try:
            audio_bytes = self.audio_in.get(timeout=1.0)
        except queue.Empty:
            self.is_listening = False
            return ""

        # 재생 중 새어든 발화는 에코 위험 → 드롭
        if self.is_speaking or not self.is_active:
            self.is_listening = False
            return ""

        print(f"[VoiceAgent] 발화 수신 ({len(audio_bytes)}B), Whisper 인식 중...")
        text = self._transcribe_audio(audio_bytes)
        self.is_listening = False
        if text:
            self.current_user_text = text
            return text
        return ""

    # 무음/잡음에 Whisper가 흔히 지어내는 환각 문구(보수적으로만 차단)
    _HALLUCINATION_PHRASES = (
        "시청해주셔서 감사합니다",
        "시청해 주셔서 감사합니다",
        "구독과 좋아요",
        "구독 부탁",
    )

    def _transcribe_audio(self, audio_bytes: bytes, fmt: str = "wav") -> str:
        if not audio_bytes:
            return ""
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=f".{fmt}", delete=False) as tmp:
                tmp.write(audio_bytes)
                tmp_path = tmp.name
            with open(tmp_path, "rb") as f:
                transcript = self.client.audio.transcriptions.create(
                    model=config.STT_MODEL,
                    file=f,
                    language="ko",
                    response_format="verbose_json",
                    temperature=0,
                )
            text = (getattr(transcript, "text", "") or "").strip()
            if not text:
                return ""

            segments = getattr(transcript, "segments", None) or []
            probs = []
            for s in segments:
                p = s.get("no_speech_prob") if isinstance(s, dict) else getattr(s, "no_speech_prob", None)
                if p is not None:
                    probs.append(p)
            if probs and (sum(probs) / len(probs)) > 0.8:
                print(f"[VoiceAgent] ⚠️ 무음/잡음 추정 → 무시: '{text}'")
                return ""
            if any(ph in text for ph in self._HALLUCINATION_PHRASES):
                print(f"[VoiceAgent] ⚠️ 환각 문구 → 무시: '{text}'")
                return ""
            return text
        except Exception as e:
            print(f"[VoiceAgent] Whisper STT 에러: {e}")
            return ""
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    # ──────────────────────── 오디오 출력 ────────────────────────
    def _emit(self, payload: dict):
        if self.audio_out:
            try:
                self.audio_out(payload)
            except Exception as e:
                print(f"[VoiceAgent] audio_out 송신 실패: {e}")

    def _play_and_wait(self, payload: dict, timeout_sec: float):
        """half-duplex 재생: 클라에 재생 지시 → playback_done 대기. 대기 동안 is_speaking=True."""
        if not self.is_active:
            return
        self.is_speaking = True
        self.playback_done.clear()
        self._emit(payload)
        if not self.playback_done.wait(timeout=timeout_sec):
            print(f"[VoiceAgent] playback_done 타임아웃({timeout_sec}s) — 강제 진행")
        self.is_speaking = False

    def speak(self, text: str):
        """TTS(mp3) 생성 후 클라가 /tts/{device_id} 로 가져가 재생하도록 지시."""
        if not self.is_active or not text:
            return
        self.current_subtitle = text
        try:
            resp = self.client.audio.speech.create(
                model=config.TTS_MODEL,
                voice=config.TTS_VOICE,
                input=text,
                speed=config.TTS_SPEED,
            )
            resp.stream_to_file(self.temp_voice_path)
            self._play_and_wait(
                {"type": "speak", "url": f"/tts/{self.device_id}", "ts": time.time()},
                timeout_sec=20.0,
            )
        except Exception as e:
            print(f"[VoiceAgent] TTS 에러: {e}")
        finally:
            self.current_subtitle = ""

    # ──────────────────────── 자원 점유 제어 ────────────────────────
    def pause(self):
        if not self.is_active:
            return
        self.is_active = False
        self.is_listening = False
        self.playback_done.set()

    def resume(self):
        self.is_active = True


if __name__ == "__main__":
    # 단독 실행(오디오 미주입 — main.py /ws/voice 로 구동). board_context 로딩만 확인.
    agent = VoiceAgent()
    print(agent.get_response("R5 자리 저항 뭐야?"))
