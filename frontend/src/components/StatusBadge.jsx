import './StatusBadge.css'

/**
 * 상단 상태 배지 — v0 시연 UI 재현(대기중/듣는중/생각중/답하는중).
 * status 는 App 에서 서버 state(listening/speaking/user/subtitle)로 파생.
 */
const CONFIG = {
  idle:      { label: '대기 중',   icon: '●',  cls: 'sb--idle' },
  listening: { label: '듣는 중',   icon: '🎤', cls: 'sb--listening', pulse: true },
  thinking:  { label: '생각 중',   icon: '…',  cls: 'sb--thinking' },
  speaking:  { label: '답하는 중', icon: '💬', cls: 'sb--speaking' },
}

export default function StatusBadge({ status, connected = true }) {
  const c = connected
    ? (CONFIG[status] || CONFIG.idle)
    : { label: '연결 중…', icon: '…', cls: 'sb--idle' }

  return (
    <div className={`status-badge ${c.cls}`} role="status" aria-live="polite">
      {c.pulse && <span className="status-badge__ping" />}
      <span className="status-badge__icon">{c.icon}</span>
      <span>{c.label}</span>
    </div>
  )
}
