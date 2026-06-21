import { useEffect, useRef, useState } from 'react'
import { useVoiceClient } from './audio/useVoiceClient'
import { wsUrl } from './utils/host'
import { getDeviceId } from './utils/deviceId'
import SubtitleBar from './components/SubtitleBar'
import './App.css'

/**
 * 핸즈프리 납땜 조교 — 메인 화면.
 * - useVoiceClient: 브라우저 마이크 ↔ /ws/voice (핸즈프리 음성 루프)
 * - /ws/{deviceId}: 자막/상태 broadcast 구독 → SubtitleBar 표시
 */
export default function App() {
  const { voiceConnected, micOpen } = useVoiceClient(true)
  const [state, setState] = useState({ subtitle: '', user: '', listening: false, speaking: false })
  const wsRef = useRef(null)

  // 자막/상태 WebSocket (일방향 수신)
  useEffect(() => {
    let cancelled = false
    let retry = null
    const connect = () => {
      const ws = new WebSocket(wsUrl(`/ws/${getDeviceId()}`))
      wsRef.current = ws
      ws.onmessage = (e) => {
        try {
          const d = JSON.parse(e.data)
          if (d.type === 'state') setState(d)
        } catch { /* 무시 */ }
      }
      ws.onclose = () => {
        if (cancelled) return
        retry = setTimeout(connect, 3000)
      }
      ws.onerror = () => { try { ws.close() } catch { /* 무시 */ } }
    }
    connect()
    return () => {
      cancelled = true
      clearTimeout(retry)
      try { wsRef.current?.close() } catch { /* 무시 */ }
    }
  }, [])

  return (
    <div className="app">
      <header className="app-header">
        <h1 className="app-title">납땜 조교</h1>
        <span className={`app-status ${voiceConnected ? 'ok' : 'off'}`}>
          {voiceConnected ? '연결됨' : '연결 중…'}
        </span>
      </header>

      <main className="app-main">
        <SubtitleBar
          subtitle={state.subtitle}
          userText={state.user}
          isListening={state.listening}
          micOpen={micOpen}
        />
      </main>

      <footer className="app-footer">
        TPK-128 V3.0 · "R5 자리 저항 뭐야?" 처럼 물어보세요
      </footer>
    </div>
  )
}
