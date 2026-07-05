import LogoMark from './LogoMark.jsx'
import Pill from './Pill.jsx'

const NAV = [
  ['overview', 'Overview'],
  ['bracket', 'Bracket'],
  ['groups', 'Groups'],
  ['fixtures', 'Fixtures'],
  ['matchlab', 'Match Lab'],
  ['players', 'Players'],
]

export default function Header({ view, setView }) {
  return (
    <header style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 13, flex: 1 }}>
        <div style={{ display: 'flex', flexDirection: 'column', lineHeight: 1, gap: 4 }}>
          <LogoMark size={44} />
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 9.5, letterSpacing: '.34em', color: 'var(--text-muted)' }}>
            WORLD CUP INTELLIGENCE
          </span>
        </div>
      </div>
      <nav
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 4,
          padding: 4,
          border: '1px solid rgba(255,255,255,.07)',
          borderRadius: 100,
          background: 'rgba(255,255,255,.02)',
          flex: 'none',
        }}
      >
        {NAV.map(([key, label]) => (
          <Pill key={key} active={view === key} onClick={() => setView(key)}>
            {label}
          </Pill>
        ))}
      </nav>
      {/* right side intentionally empty (LIVE badge + external link removed per spec) — balanced via equal flex */}
      <div style={{ flex: 1 }} />
    </header>
  )
}
