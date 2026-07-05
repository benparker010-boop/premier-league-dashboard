import { TICKER_RESULTS, TICKER_R16 } from '../data/mock.js'

const seg = {
  fontFamily: 'var(--font-mono)',
  fontSize: 12,
  letterSpacing: '.04em',
  color: '#9fb0c2',
  padding: '0 26px',
  borderRight: '1px solid rgba(255,255,255,.06)',
  whiteSpace: 'nowrap',
}

export default function Ticker() {
  const block = (
    <>
      <span style={seg}>
        <span style={{ color: 'var(--teal)' }}>RESULTS</span>&nbsp;&nbsp;{TICKER_RESULTS}
      </span>
      <span style={seg}>
        <span style={{ color: 'var(--gold)' }}>ROUND OF 16</span>&nbsp;&nbsp;{TICKER_R16}
      </span>
    </>
  )
  return (
    <div
      style={{
        position: 'relative',
        zIndex: 2,
        marginTop: 32,
        borderTop: '1px solid rgba(255,255,255,.08)',
        background: 'rgba(6,10,18,.8)',
        overflow: 'hidden',
        whiteSpace: 'nowrap',
      }}
    >
      <div
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 0,
          padding: '13px 0',
          animation: 'mq 38s linear infinite',
          willChange: 'transform',
        }}
      >
        {block}
        {block}
      </div>
    </div>
  )
}
