import { useState, useEffect, useRef } from 'react'
import './SubtitleBar.css'

/**
 * 자막 패널 (senior-smile-project SubtitleBar.jsx 재사용 — 라벨만 조교용으로 교체).
 * 학생 STT transcript(userText) + 조교 답변(subtitle)을 화면에 표시.
 */
function SubtitleBar({ subtitle, userText, isListening, micOpen }) {
  const [displayText, setDisplayText] = useState('')
  const prevSubtitle = useRef('')
  const typingTimer = useRef(null)

  useEffect(() => {
    if (subtitle && subtitle !== prevSubtitle.current) {
      clearInterval(typingTimer.current)
      prevSubtitle.current = subtitle
      setDisplayText('')

      let i = 0
      typingTimer.current = setInterval(() => {
        i++
        setDisplayText(subtitle.slice(0, i))
        if (i >= subtitle.length) clearInterval(typingTimer.current)
      }, 35)
    }

    if (!subtitle && !isListening) {
      prevSubtitle.current = ''
      setDisplayText('')
    }

    return () => clearInterval(typingTimer.current)
  }, [subtitle, isListening])

  const isProcessing = (isListening || userText) && !subtitle
  const isEmpty = !subtitle && !isListening && !userText && !displayText
  const hasContent = userText || displayText

  return (
    <div className={`voice-panel ${isEmpty ? 'voice-panel--idle' : 'voice-panel--active'} ${hasContent ? 'voice-panel--has-content' : ''}`}>
      {userText && (
        <div className={`vp-user-text ${(displayText || isProcessing) ? '' : 'vp-user-text--alone'}`}>
          <span className="vp-user-text-label">내 질문</span>
          <span className="vp-user-text-content">{userText}</span>
        </div>
      )}

      {isProcessing ? (
        <div className="vp-listening">
          <span className="vp-listening-label">{isListening ? '듣는 중' : '생각하는 중...'}</span>
          <div className="vp-dots">
            <span className="vp-dot" />
            <span className="vp-dot" />
            <span className="vp-dot" />
          </div>
        </div>
      ) : displayText ? (
        <div className="vp-speech">
          <div className="vp-speaker">
            <span className="vp-speaker-dot" />
            <span className="vp-speaker-label">조교</span>
          </div>
          <p className="vp-text">{displayText}</p>
        </div>
      ) : !userText && (
        micOpen ? (
          <div className="vp-idle vp-idle--listening">
            <span className="vp-idle-icon">🎤</span>
            <span className="vp-idle-text">듣고 있어요 · 부품 번호를 말해보세요</span>
          </div>
        ) : (
          <div className="vp-idle">
            <span className="vp-idle-icon">⏳</span>
            <span className="vp-idle-text">잠시만요…</span>
          </div>
        )
      )}
    </div>
  )
}

export default SubtitleBar
