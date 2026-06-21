import { useEffect, useRef, useState } from 'react'
import { wsUrl, httpUrl } from '../utils/host'
import { getDeviceId } from '../utils/deviceId'
// @ricky0123/vad-web(+onnxruntime-web)은 무거워서(~400KB) 동적 import로 메인 번들에서 분리.

/**
 * 핸즈프리 음성 클라이언트 (브라우저 마이크 ↔ 서버 /ws/voice).
 * (senior-smile-project useVoiceClient.js 재사용 — half-duplex 에코 방지)
 *
 * - 입력: Silero VAD(@ricky0123/vad-web)로 발화 구간 분할 → encodeWAV(16kHz) → binary 업로드
 * - 출력: 서버 {type:'speak', url} 수신 → <audio> 재생
 * - half-duplex(서버 is_speaking과 정렬):
 *     · 재생 지시 수신 즉시 VAD 정지(캡처 OFF) → 마이크가 스피커 소리를 못 잡음(에코 방지)
 *     · 항목마다 재생 종료 시 playback_done 송신(서버는 emit마다 1:1로 대기)
 *     · 마지막 재생 후 grace 동안 새 재생 없으면 VAD 재개
 */

const WS_URL = wsUrl(`/ws/voice/${getDeviceId()}`)
// TTS 재생 베이스. 서버가 보내는 url은 /tts/... 같은 서버 기준 절대경로라
// 로컬 dev(프론트 5173 ↔ 백엔드 8000)에서 상대경로로 두면 5173으로 요청돼 404 → 무음.
const HTTP_BASE = httpUrl()
const VAD_VERSION = '0.0.30'
const ORT_VERSION = '1.26.0'
const RESUME_GRACE_MS = 500
// autoGainControl: false 가 핵심 — 조용한 환경에서 AGC가 노이즈 플로어를 증폭해
// VAD가 끊임없이 '발화'로 오판 → Whisper 환각 폭주.
const MIC_AUDIO = { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: false }

export function useVoiceClient(enabled) {
  const [connected, setConnected] = useState(false)
  const [micOpen, setMicOpen] = useState(false)

  const wsRef = useRef(null)
  const vadRef = useRef(null)
  const reconnectTimerRef = useRef(null)
  const resumeTimerRef = useRef(null)
  const playQueueRef = useRef([])
  const playingRef = useRef(false)
  const audioElRef = useRef(null)
  const pausedRef = useRef(false)

  // 모바일 자동재생 잠금 해제: 첫 사용자 터치/클릭에서 무음 1회 재생 → 이후 TTS .play() 허용.
  useEffect(() => {
    const SILENT = 'data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQAAAAA='
    const unlock = () => {
      try { new Audio(SILENT).play().catch(() => {}) } catch { /* 무시 */ }
      window.removeEventListener('pointerdown', unlock)
      window.removeEventListener('touchend', unlock)
    }
    window.addEventListener('pointerdown', unlock)
    window.addEventListener('touchend', unlock)
    return () => {
      window.removeEventListener('pointerdown', unlock)
      window.removeEventListener('touchend', unlock)
    }
  }, [])

  useEffect(() => {
    if (!enabled) return
    let cancelled = false

    const sendControl = (action) => {
      const ws = wsRef.current
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'control', action }))
      }
    }

    const pauseCapture = () => {
      clearTimeout(resumeTimerRef.current)
      pausedRef.current = true
      setMicOpen(false)
      try { vadRef.current?.pause() } catch { /* VAD 미초기화 무시 */ }
    }

    const scheduleResume = () => {
      clearTimeout(resumeTimerRef.current)
      resumeTimerRef.current = setTimeout(() => {
        if (!playingRef.current && playQueueRef.current.length === 0) {
          pausedRef.current = false
          try { vadRef.current?.start(); setMicOpen(true) } catch { /* 무시 */ }
        }
      }, RESUME_GRACE_MS)
    }

    const playNext = () => {
      const queue = playQueueRef.current
      if (queue.length === 0) {
        playingRef.current = false
        scheduleResume()
        return
      }
      playingRef.current = true
      const item = queue.shift()
      const absUrl = item.url.startsWith('http') ? item.url : HTTP_BASE + item.url
      const sep = absUrl.includes('?') ? '&' : '?'
      const audio = new Audio(absUrl + sep + 'ts=' + (item.ts || Date.now()))
      audioElRef.current = audio
      const onDone = () => {
        sendControl('playback_done')
        playNext()
      }
      audio.onended = onDone
      audio.onerror = onDone
      audio.play().catch(onDone)
    }

    const enqueuePlay = (item) => {
      pauseCapture()
      playQueueRef.current.push(item)
      if (!playingRef.current) playNext()
    }

    const connect = () => {
      const ws = new WebSocket(WS_URL)
      ws.binaryType = 'arraybuffer'
      wsRef.current = ws
      ws.onopen = () => { if (!cancelled) setConnected(true) }
      ws.onmessage = (e) => {
        let data
        try { data = JSON.parse(e.data) } catch { return }
        if (data.type === 'speak' || data.type === 'beep') {
          enqueuePlay({ url: data.url, ts: data.ts })
        }
      }
      ws.onclose = () => {
        if (cancelled) return
        setConnected(false)
        reconnectTimerRef.current = setTimeout(connect, 3000)
      }
      ws.onerror = () => { try { ws.close() } catch { /* 무시 */ } }
    }
    connect()

    import('@ricky0123/vad-web')
      .then(({ MicVAD, utils }) =>
        MicVAD.new({
          baseAssetPath: `https://cdn.jsdelivr.net/npm/@ricky0123/vad-web@${VAD_VERSION}/dist/`,
          onnxWASMBasePath: `https://cdn.jsdelivr.net/npm/onnxruntime-web@${ORT_VERSION}/dist/`,
          getStream: () => navigator.mediaDevices.getUserMedia({ audio: MIC_AUDIO }),
          resumeStream: () => navigator.mediaDevices.getUserMedia({ audio: MIC_AUDIO }),
          pauseStream: async (stream) => { stream.getTracks().forEach((t) => t.stop()) },
          redemptionMs: 1056,
          minSpeechFrames: 4,
          positiveSpeechThreshold: 0.6,
          negativeSpeechThreshold: 0.4,
          onSpeechEnd: (audio) => {
            // half-duplex 2차 방어: 정지/재생 중이면 업로드 금지
            if (cancelled || pausedRef.current || playingRef.current) return
            const ws = wsRef.current
            if (!ws || ws.readyState !== WebSocket.OPEN) return
            ws.send(utils.encodeWAV(audio))  // 16kHz mono WAV ArrayBuffer → binary 프레임
          },
        }),
      )
      .then((vad) => {
        if (cancelled) { try { vad.destroy() } catch { /* 무시 */ } return }
        vadRef.current = vad
        if (!pausedRef.current) { vad.start(); setMicOpen(true) }
      })
      .catch((err) => {
        console.warn('[voice] VAD 초기화 실패 (마이크 권한/네트워크 확인):', err)
      })

    return () => {
      cancelled = true
      clearTimeout(resumeTimerRef.current)
      clearTimeout(reconnectTimerRef.current)
      try { vadRef.current?.destroy() } catch { /* 무시 */ }
      vadRef.current = null
      try { audioElRef.current?.pause() } catch { /* 무시 */ }
      try { wsRef.current?.close() } catch { /* 무시 */ }
      wsRef.current = null
    }
  }, [enabled])

  return { voiceConnected: connected, micOpen }
}
