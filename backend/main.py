"""
핸즈프리 납땜 조교 — FastAPI 백엔드.

senior-smile-project/backend/main.py 의 음성 배선만 발췌·슬림화.
- /ws/voice/{device_id} : 브라우저 마이크 ↔ 음성 파이프라인(양방향 WS)
- /ws/{device_id}       : 자막/상태 일방향 broadcast(프론트가 폴링 수신)
- /tts/{device_id}      : voice_agent.speak()가 만든 최신 TTS mp3
- /sounds/{filename}    : 준비된 효과음(선택)
API 키는 서버에만 있고 오디오만 WS로 오간다 → 브라우저 노출 없음.
"""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

import config
import audio_transport
from voice_agent import VoiceAgent
from voice_socket import VoiceSocketBridge
from part_info import load_board

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("handsfree")


class Device:
    """기기 1대 = voice agent + 브리지 + 자막 구독자."""
    def __init__(self, device_id: str):
        self.agent = VoiceAgent(device_id=device_id)
        self.bridge = VoiceSocketBridge()
        self.bridge.bind_agent(self.agent)


_devices: dict[str, Device] = {}


def get_device(device_id: str) -> Device:
    if device_id not in _devices:
        _devices[device_id] = Device(device_id)
    return _devices[device_id]


@asynccontextmanager
async def lifespan(app: FastAPI):
    board = load_board()
    logger.info(f"보드 로딩 완료: {board.get('board')} (부품 {len(board.get('parts', {}))}개)")
    yield


app = FastAPI(title="Hands-free Soldering Tutor", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.websocket("/ws/voice/{device_id}")
async def ws_voice(websocket: WebSocket, device_id: str):
    """브라우저 마이크 ↔ 음성 파이프라인.
    - 인바운드 오디오: VAD로 끊은 발화(binary) → voice_agent.audio_in
    - 인바운드 제어: {type:'control', action:'playback_done'} → half-duplex 재생 대기 해제
    - 아웃바운드: voice_agent가 {type:'speak', url} 송신(voice_socket 브리지)"""
    dev = get_device(device_id)
    await websocket.accept()
    loop = asyncio.get_running_loop()
    await dev.bridge.attach(websocket, loop)
    logger.info(f"[voice] /ws/voice/{device_id} 연결")

    if not dev.agent.is_running:
        dev.agent.start_conversation()

    try:
        while True:
            msg = await websocket.receive()
            if msg.get("type") == "websocket.disconnect":
                break
            audio = audio_transport.extract_audio(msg)
            if audio is not None:
                if not dev.agent.is_running:
                    dev.agent.start_conversation()
                dev.bridge.feed_audio(audio)
                continue
            ctrl = audio_transport.parse_control(msg)
            if ctrl and ctrl.get("action") == "playback_done":
                dev.bridge.signal_playback_done()
    except WebSocketDisconnect:
        pass
    finally:
        dev.bridge.detach(websocket)
        logger.info(f"[voice] /ws/voice/{device_id} 해제")


@app.websocket("/ws/{device_id}")
async def ws_state(websocket: WebSocket, device_id: str):
    """자막/상태 일방향 broadcast. 변화가 있을 때만 송신(폴링 0.25s)."""
    dev = get_device(device_id)
    await websocket.accept()
    last = None
    try:
        while True:
            ag = dev.agent
            part = ag.current_part
            state = {
                "type": "state",
                "subtitle": ag.current_subtitle or "",
                "user": ag.current_user_text or "",
                "listening": ag.is_listening,
                "speaking": ag.is_speaking,
                "part": part,
            }
            pkey = f"{(part or {}).get('reference', '')}|{(part or {}).get('value', '')}"
            key = (state["subtitle"], state["user"], state["listening"], state["speaking"], pkey)
            if key != last:
                last = key
                await websocket.send_json(state)
            await asyncio.sleep(0.25)
    except (WebSocketDisconnect, RuntimeError):
        pass


@app.get("/tts/{device_id}")
async def tts_latest(device_id: str):
    """해당 기기 voice_agent.speak()가 생성한 최신 TTS mp3. 클라는 ?ts= 캐시버스터로 요청."""
    p = config.SOUNDS_DIR / f"temp_voice_{device_id}.mp3"
    if not p.exists():
        return Response(status_code=404)
    return FileResponse(str(p), media_type="audio/mpeg")


@app.get("/sounds/{filename}")
async def serve_sound(filename: str):
    """효과음 서빙(선택). 경로 traversal 방지."""
    p = (config.SOUNDS_DIR / filename).resolve()
    if p.parent != config.SOUNDS_DIR.resolve() or not p.exists():
        return Response(status_code=404)
    return FileResponse(str(p))


@app.get("/health")
async def health():
    return {"ok": True, "devices": len(_devices)}


# 프로덕션: 프론트 빌드(../backend/dist)를 같이 서빙(존재할 때만)
_dist = config.BASE_DIR / "dist"
if _dist.exists():
    app.mount("/", StaticFiles(directory=str(_dist), html=True), name="static")
