import { useEffect, useRef } from 'react'

/* Chat bubbles + "analysing…" pending state, shared by the Overview
   transcript panel and the docked bar (Phase 3). */

const badgeStyles = (role) =>
  role === 'user'
    ? { badge: 'YOU', bg: 'rgba(255,255,255,.05)', fg: '#9fb0c2', bd: 'rgba(255,255,255,.12)', color: '#cdd8e4' }
    : { badge: 'PK', bg: 'rgba(0,224,198,.12)', fg: '#00e0c6', bd: 'rgba(0,224,198,.3)', color: '#e8edf2' }

const dot = (delay) => (
  <span
    style={{
      display: 'inline-block',
      width: 3,
      height: 3,
      borderRadius: '50%',
      background: 'var(--teal)',
      marginLeft: delay === 0 ? 5 : 3,
      animation: `dotb 1.2s infinite ${delay}s`,
    }}
  />
)

export default function ChatMessages({ messages, pending, style }) {
  const ref = useRef(null)
  useEffect(() => {
    const el = ref.current
    if (el) el.scrollTop = el.scrollHeight
  }, [messages, pending])
  return (
    <div
      ref={ref}
      style={{
        overflowY: 'auto',
        display: 'flex',
        flexDirection: 'column',
        gap: 14,
        padding: 18,
        background: 'rgba(8,13,22,.7)',
        border: '1px solid rgba(255,255,255,.08)',
        borderRadius: 14,
        ...style,
      }}
    >
      {messages.map((m) => {
        const b = badgeStyles(m.role)
        return (
          <div key={m.id} style={{ display: 'flex', gap: 11, alignItems: 'flex-start' }}>
            <span
              style={{
                flex: 'none',
                width: 22,
                height: 22,
                borderRadius: 6,
                display: 'grid',
                placeItems: 'center',
                fontFamily: 'var(--font-mono)',
                fontSize: 9,
                fontWeight: 700,
                letterSpacing: '.04em',
                marginTop: 1,
                background: b.bg,
                color: b.fg,
                border: `1px solid ${b.bd}`,
              }}
            >
              {b.badge}
            </span>
            <div style={{ fontSize: 14.5, lineHeight: 1.55, color: b.color, whiteSpace: 'pre-wrap' }}>{m.content}</div>
          </div>
        )
      })}
      {pending && (
        <div style={{ display: 'flex', gap: 11, alignItems: 'center' }}>
          <span
            style={{
              flex: 'none',
              width: 22,
              height: 22,
              borderRadius: 6,
              display: 'grid',
              placeItems: 'center',
              fontFamily: 'var(--font-mono)',
              fontSize: 9,
              fontWeight: 700,
              background: 'rgba(0,224,198,.12)',
              color: 'var(--teal)',
              border: '1px solid rgba(0,224,198,.3)',
            }}
          >
            PK
          </span>
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: '#6f8093', letterSpacing: '.04em' }}>
            analysing{dot(0)}{dot(0.2)}{dot(0.4)}
          </span>
        </div>
      )}
    </div>
  )
}
