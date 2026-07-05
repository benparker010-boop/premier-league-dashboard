import { useState } from 'react'
import Background from './components/Background.jsx'
import Card from './components/Card.jsx'
import Pill from './components/Pill.jsx'
import LogoMark from './components/LogoMark.jsx'

/*
  Phase 1 — token board.
  A temporary sample page proving the global design tokens: fonts, colors,
  background layers, card treatment, pill buttons. Replaced by the real
  6-view app in Phase 2.
*/

const NAV = ['Overview', 'Bracket', 'Groups', 'Fixtures', 'Match Lab', 'Players']

const eyebrow = {
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
  letterSpacing: '.2em',
  color: 'var(--text-secondary-2)',
  textTransform: 'uppercase',
}

export default function App() {
  const [active, setActive] = useState('Bracket')

  return (
    <div style={{ position: 'relative', minHeight: '100vh', overflow: 'hidden', background: 'var(--bg)' }}>
      <Background />

      <div style={{ position: 'relative', zIndex: 2, maxWidth: 1280, margin: '0 auto', padding: '26px 32px 80px' }}>
        {/* logo + wordmark label */}
        <header style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', flexDirection: 'column', lineHeight: 1, gap: 4, flex: 1 }}>
            <LogoMark size={44} />
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 9.5, letterSpacing: '.34em', color: 'var(--text-muted)' }}>
              WORLD CUP INTELLIGENCE
            </span>
          </div>
          {/* nav pill group */}
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
            {NAV.map((n) => (
              <Pill key={n} active={n === active} onClick={() => setActive(n)}>
                {n}
              </Pill>
            ))}
          </nav>
          <div style={{ flex: 1 }} />
        </header>

        {/* hero type scale sample */}
        <main style={{ marginTop: 46, maxWidth: 720 }}>
          <div style={{ ...eyebrow, letterSpacing: '.26em', color: 'var(--text-muted-2)' }}>
            FIFA WORLD CUP 2026 — USA · CANADA · MÉXICO
          </div>
          <h1
            style={{
              fontSize: 58,
              lineHeight: 1.02,
              fontWeight: 700,
              letterSpacing: '-.025em',
              margin: '18px 0 0',
              maxWidth: '15ch',
            }}
          >
            Ask{' '}
            <span
              style={{
                background: 'linear-gradient(110deg,#00e0c6,#7ff8ec,#00e0c6)',
                backgroundSize: '200% auto',
                WebkitBackgroundClip: 'text',
                backgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
                animation: 'shimmer 4s linear infinite',
                filter: 'drop-shadow(0 0 18px rgba(0,224,198,.35))',
              }}
            >
              Parker
            </span>{' '}
            anything about the World Cup.
          </h1>
          <p style={{ fontSize: 16, lineHeight: 1.5, color: 'var(--text-secondary)', maxWidth: '46ch', margin: '18px 0 0' }}>
            Live stats, expected goals and tournament predictions — modelled across all 48 teams and answered the
            instant you ask.
          </p>

          {/* primary CTA + chip samples */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 24, flexWrap: 'wrap' }}>
            <button
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 7,
                padding: '9px 15px',
                border: 'none',
                borderRadius: 10,
                background: 'var(--teal)',
                color: '#04211d',
                fontFamily: 'var(--font-display)',
                fontSize: 13,
                fontWeight: 600,
                cursor: 'pointer',
                boxShadow: '0 0 18px rgba(0,224,198,.3)',
              }}
            >
              Ask<span>↵</span>
            </button>
            <button
              style={{
                padding: '7px 13px',
                border: '1px solid rgba(255,255,255,.1)',
                borderRadius: 100,
                background: 'rgba(255,255,255,.02)',
                color: '#9fb0c2',
                fontFamily: 'var(--font-mono)',
                fontSize: 11.5,
                letterSpacing: '.01em',
                cursor: 'pointer',
              }}
            >
              Who's most likely to win the World Cup?
            </button>
          </div>
        </main>

        {/* card samples */}
        <section style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 18, marginTop: 40, maxWidth: 860 }}>
          <Card style={{ padding: 20 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
              <span style={{ ...eyebrow, color: 'var(--text-secondary-2)' }}>PREDICTED CHAMPION</span>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 9.5, letterSpacing: '.1em', color: '#4f6075' }}>
                MODEL v2.6
              </span>
            </div>
            {[
              { code: 'FRA', name: 'France', pct: 18.4, color: '#5b8cff', w: 100, delay: 0 },
              { code: 'ARG', name: 'Argentina', pct: 16.1, color: '#5ec8e0', w: 87.5, delay: 0.4 },
              { code: 'ENG', name: 'England', pct: 13.7, color: '#e8475e', w: 74.5, delay: 0.8 },
            ].map((c) => (
              <div key={c.code} style={{ marginBottom: 13 }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
                    <span style={{ width: 8, height: 8, borderRadius: 2, background: c.color }} />
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, letterSpacing: '.08em', color: '#cdd8e4' }}>
                      {c.code}
                    </span>
                    <span style={{ fontSize: 12.5, color: '#7c8b9c' }}>{c.name}</span>
                  </div>
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: 13, fontWeight: 500, color: '#eaf2f0' }}>
                    {c.pct}%
                  </span>
                </div>
                <div style={{ height: 8, borderRadius: 4, background: 'rgba(255,255,255,.06)', overflow: 'hidden', position: 'relative' }}>
                  <div
                    style={{
                      height: '100%',
                      borderRadius: 4,
                      width: `${c.w}%`,
                      background: `linear-gradient(90deg,${c.color},${c.color}99)`,
                      boxShadow: `0 0 12px ${c.color}99`,
                      position: 'relative',
                      overflow: 'hidden',
                    }}
                  >
                    <div
                      style={{
                        position: 'absolute',
                        top: 0,
                        bottom: 0,
                        width: '40%',
                        background: 'linear-gradient(90deg,transparent,rgba(255,255,255,.3),transparent)',
                        animation: `barshine 2.8s ease-in-out infinite ${c.delay}s`,
                      }}
                    />
                  </div>
                </div>
              </div>
            ))}
          </Card>

          <Card gold style={{ padding: '18px 20px' }}>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, letterSpacing: '.16em', color: '#caa24f', marginBottom: 14 }}>
              GOLDEN BOOT LEADER
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
              <div
                style={{
                  width: 52,
                  height: 52,
                  borderRadius: '50%',
                  background: 'linear-gradient(135deg,rgba(245,196,81,.22),rgba(245,196,81,.07))',
                  border: '2px solid rgba(245,196,81,.5)',
                  display: 'grid',
                  placeItems: 'center',
                  flex: 'none',
                }}
              >
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 13, fontWeight: 700, color: 'var(--gold)' }}>FRA</span>
              </div>
              <div>
                <div style={{ fontSize: 19, fontWeight: 700, color: 'var(--text-brightest)' }}>K. Mbappé</div>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10.5, color: 'var(--text-secondary-2)', marginTop: 4 }}>
                  6 goals · 5.4 xG · 3 ast
                </div>
              </div>
            </div>
          </Card>
        </section>
      </div>
    </div>
  )
}
