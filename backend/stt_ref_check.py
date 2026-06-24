"""
6-1 실음성 E2E (마이크 없이): TTS → Whisper STT 라운드트립으로
한국어 STT가 'R5' 같은 영숫자 레퍼런스를 보존하는지 검증한다.

각 문장을 tts-1(nova)로 합성 → whisper-1(language=ko)로 재인식 →
정규화(_norm)한 인식문에서 기대 레퍼런스가 복원되는지 확인.

실행: backend/.env 에 OPENAI_API_KEY 설정 후
    PYTHONUTF8=1 python stt_ref_check.py
"""
import config
from openai import OpenAI
from part_info import _norm
from voice_agent import VoiceAgent

client = OpenAI(api_key=config.OPENAI_API_KEY)

# (발화문, 기대 레퍼런스) — 실제 학생이 말할 법한 자연 발화로
CASES = [
    ("R5 자리 저항 뭐야?",            "R5"),
    ("알5 저항 값 알려줘",            "R5"),
    ("R13 어디에 꽂아?",             "R13"),
    ("디원 다이오드 방향 어디야?",      "D1"),
    ("C2 콘덴서 극성 알려줘",         "C2"),
    ("유4 아이씨 홈 방향 어디로 가?",   "U4"),
    ("AR1 어레이 저항 1번 핀 어디야?", "AR1"),
    ("TR5 트랜지스터 방향 맞아?",      "TR5"),
    ("BZ1 부저 극성 있어?",          "BZ1"),
]


def synth(text: str) -> bytes:
    resp = client.audio.speech.create(
        model=config.TTS_MODEL, voice=config.TTS_VOICE,
        input=text, speed=config.TTS_SPEED,
    )
    return resp.content  # mp3 bytes


def main():
    agent = VoiceAgent()
    passed = 0
    print(f"TTS={config.TTS_MODEL}/{config.TTS_VOICE}  STT={config.STT_MODEL}\n")
    for utter, expect in CASES:
        mp3 = synth(utter)
        heard = agent._transcribe_audio(mp3, fmt="mp3")
        norm_heard = _norm(heard)
        ok = _norm(expect) in norm_heard
        passed += ok
        print(f"말함 : {utter}")
        print(f"들림 : {heard!r}")
        print(f"기대 : {expect}  → {'✅ 복원됨' if ok else '❌ 손실'}  (정규화: {norm_heard})\n")
    print(f"==== STT 레퍼런스 복원: {passed}/{len(CASES)} ====")


if __name__ == "__main__":
    main()
