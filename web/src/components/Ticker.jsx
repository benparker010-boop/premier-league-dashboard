import { useData } from '../data/DataContext.jsx'

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
  const { data } = useData()
  const fixtures = data?.fixtures || []
  const done = fixtures.filter((f) => f.status === 'done').slice(-10)
  const upcoming = fixtures.filter((f) => f.status === 'upcoming').slice(0, 6)
  const resultsText = done.map((f) => `${f.hCode} ${f.sh}–${f.sa} ${f.aCode}`).join(' · ')
  const upcomingText = upcoming.map((f) => `${f.hCode} v ${f.aCode} · ${f.date}`).join(' · ')
  if (!resultsText && !upcomingText) return null

  const block = (
    <>
      {resultsText && (
        <span style={seg}>
          <span style={{ color: 'var(--teal)' }}>RESULTS</span>&nbsp;&nbsp;{resultsText}
        </span>
      )}
      {upcomingText && (
        <span style={seg}>
          <span style={{ color: 'var(--gold)' }}>UPCOMING</span>&nbsp;&nbsp;{upcomingText}
        </span>
      )}
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
