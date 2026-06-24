import './PartCard.css'

/**
 * 하단 부품 카드 — v0 시연 UI 재현(위치 / 값 / 색 띠 / 극성).
 * 서버가 get_part_info 결과를 state.part 로 broadcast 할 때만 표시.
 */
function Field({ label, value, tone }) {
  return (
    <div className="part-card__field">
      <span className="part-card__label">{label}</span>
      <span className={`part-card__value ${tone ? `part-card__value--${tone}` : ''}`}>
        {value}
      </span>
    </div>
  )
}

export default function PartCard({ part }) {
  if (!part) return null
  return (
    <div className="part-card">
      <Field label="위치" value={part.reference} tone="accent" />
      {part.value && <><span className="part-card__divider" /><Field label="값" value={part.value} /></>}
      {part.colorBands && <><span className="part-card__divider" /><Field label="색 띠" value={part.colorBands} /></>}
      {part.polarity && <><span className="part-card__divider" /><Field label="극성" value={part.polarity} tone="amber" /></>}
    </div>
  )
}
