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

export default function Header({ view, setView, onLogoClick, hideLogo }) {
  return (
    <header className="pk-header" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 13, flex: 1 }}>
        <div style={{ display: 'flex', alignItems: 'flex-end', gap: 1 }}>
          {/* #pk-header-logo is the intro's FLIP handoff target; clicking replays it */}
          <div
            id="pk-header-logo"
            onClick={onLogoClick}
            title="Replay intro"
            style={{ cursor: 'pointer', flex: 'none', visibility: hideLogo ? 'hidden' : 'visible' }}
          >
            <LogoMark size={108} />
          </div>
          <span
            style={{
              fontFamily: 'var(--font-display)',
              fontSize: 28,
              fontWeight: 600,
              letterSpacing: '-.01em',
              color: 'var(--text-brightest)',
              lineHeight: 1,
              marginLeft: -4,
              marginBottom: 0,
            }}
          >
            arker AI
          </span>
        </div>
      </div>
      <nav
        className="pk-nav"
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
