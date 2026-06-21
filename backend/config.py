"""핸즈프리 납땜 조교 설정. (senior-smile-project config.py 를 슬림화해 재사용)"""
import os
from pathlib import Path
from dotenv import load_dotenv

# .env 로드
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

# ── OpenAI ──
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# 모델(환경변수로 교체 가능)
STT_MODEL = os.environ.get("STT_MODEL", "whisper-1")
CHAT_MODEL = os.environ.get("CHAT_MODEL", "gpt-4o-mini")
TTS_MODEL = os.environ.get("TTS_MODEL", "tts-1")
TTS_VOICE = os.environ.get("TTS_VOICE", "nova")

# ── 경로 ──
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
SOUNDS_DIR = BASE_DIR / "sounds"
SOUNDS_DIR.mkdir(exist_ok=True)

# 지식베이스(보드 데이터) — 엔진과 분리. 다른 보드로 교체하려면 이 경로만 바꾸면 된다.
BOARD_FILE = os.environ.get("BOARD_FILE", str(DATA_DIR / "board_atmega128.json"))

# ── CORS ──
CORS_ORIGINS = ["*"]
