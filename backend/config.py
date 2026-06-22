"""핸즈프리 납땜 조교 설정. (senior-smile-project config.py 를 슬림화해 재사용)"""
import os
from pathlib import Path
from dotenv import load_dotenv

# .env 로드
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

# ── OpenAI ──
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# ── 모델 선택 (환경변수로 교체 가능) ──
# 비용 원칙: 실시간(gpt-4o-realtime) API를 쓰지 않는다. STT→LLM→TTS 분리 파이프라인이
# realtime 대비 대략 1/10~1/30 비용. 짧은 질의응답(공방 조교)에는 분리형이 충분하다.
#   · STT  whisper-1     : $0.006/분 (가장 저렴한 음성인식)
#   · Chat gpt-4o-mini   : 입력 $0.15 / 출력 $0.60 per 1M tok (동급 최저가, 반복 프롬프트 자동 캐시)
#   · TTS  tts-1         : $15 per 1M자. tts-1-hd(2배가)는 품질차 작아 미사용. realtime 음성 아님.
STT_MODEL = os.environ.get("STT_MODEL", "whisper-1")
CHAT_MODEL = os.environ.get("CHAT_MODEL", "gpt-4o-mini")
TTS_MODEL = os.environ.get("TTS_MODEL", "tts-1")
# nova: 밝고 또렷한 톤 → 공방 소음 속에서도 잘 들림(조교용으로 적합).
TTS_VOICE = os.environ.get("TTS_VOICE", "nova")
# 1.0: 학생이 '10킬로옴' 같은 수치를 또렷이 듣도록 표준속도. (이전 1.05보다 살짝 늦춰 명료성↑)
TTS_SPEED = float(os.environ.get("TTS_SPEED", "1.0"))

# ── 경로 ──
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
SOUNDS_DIR = BASE_DIR / "sounds"
SOUNDS_DIR.mkdir(exist_ok=True)

# 지식베이스(보드 데이터) — 엔진과 분리. 다른 보드로 교체하려면 이 경로만 바꾸면 된다.
BOARD_FILE = os.environ.get("BOARD_FILE", str(DATA_DIR / "board_atmega128.json"))

# ── CORS ──
CORS_ORIGINS = ["*"]
