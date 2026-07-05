import { useState } from 'react'
import useTween from '../hooks/useTween.js'
import { useData } from '../data/DataContext.jsx'

const mono = (extra) => ({ fontFamily: 'var(--font-mono)', ...extra })

const STAT_ROWS = [
  ['possession', 'Possession', '%'],
  ['xg', 'Expected goals (xG)', ''],
  ['shots', 'Total shots', ''],
  ['sot', 'Shots on target', ''],
  ['big', 'Big chances', ''],
  ['corners', 'Corners', ''],
  ['passes', 'Passes', ''],
  ['passAcc', 'Pass accuracy', '%'],
  ['fouls', 'Fouls', ''],
  ['yellow', 'Yellow cards', ''],
]

const EVENT_TYPE = { g: ['GOAL', '#00e0c6'], y: ['YELLOW', '#f5c451'], r: ['RED', '#e8475e'] }
const num = (v) => (v == null ? 0 : v)
const disp = (v, unit) => (v == null ? '—' : `${v}${unit}`)

function StatsTab({ m, h, a, animKey }) {
  const mp = useTween(850, animKey)
  const rows = STAT_ROWS.filter(([key]) => {
    const v = m.stats[key] || [null, null]
    return v[0] != null || v[1] != null
  })
  return (
    <div style={{ padding: '24px 28px', display: 'flex', flexDirection: 'column', gap: 15 }}>
      {rows.map(([key, label, unit]) => {
        const [hvRaw, avRaw] = m.stats[key] || [null, null]
        const hv = num(hvRaw)
        const av = num(avRaw)
        const tot = hv + av || 1
        return (
          <div key={key} style={{ display: 'grid', gridTemplateColumns: '1fr 190px 1fr', alignItems: 'center', gap: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 12 }}>
              <span style={mono({ fontSize: 13, color: 'var(--text-body)', minWidth: 46, textAlign: 'right' })}>{disp(hvRaw, unit)}</span>
              <div style={{ flex: 1, height: 7, borderRadius: 4, background: 'rgba(255,255,255,.05)', display: 'flex', justifyContent: 'flex-end', overflow: 'hidden' }}>
                <div style={{ height: '100%', borderRadius: 4, width: `${((hv / tot) * 100 * mp).toFixed(1)}%`, background: h.color }} />
              </div>
            </div>
            <span style={{ textAlign: 'center', fontSize: 12.5, color: 'var(--text-secondary)' }}>{label}</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <div style={{ flex: 1, height: 7, borderRadius: 4, background: 'rgba(255,255,255,.05)', overflow: 'hidden' }}>
                <div style={{ height: '100%', borderRadius: 4, width: `${((av / tot) * 100 * mp).toFixed(1)}%`, background: a.color }} />
              </div>
              <span style={mono({ fontSize: 13, color: 'var(--text-body)', minWidth: 46 })}>{disp(avRaw, unit)}</span>
            </div>
          </div>
        )
      })}
    </div>
  )
}

function TimelineTab({ m }) {
  const events = m.timeline.filter((e) => e.player)
  if (!events.length) {
    return <div style={mono({ padding: '40px 28px', textAlign: 'center', fontSize: 12, color: 'var(--text-muted-2)' })}>No timeline events available for this match.</div>
  }
  return (
    <div style={{ padding: '24px 28px', position: 'relative' }}>
      <div style={{ position: 'absolute', left: '50%', top: 24, bottom: 24, width: 1, background: 'rgba(255,255,255,.09)' }} />
      {events.map((e, i) => {
        const [typeName, markerColor] = EVENT_TYPE[e.type] || ['', '#5d6e80']
        const sub = e.type === 'g' ? (e.assist ? 'assist · ' + e.assist : 'goal') : typeName.charAt(0) + typeName.slice(1).toLowerCase()
        const bubble = (isHome) => (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 9,
              flexDirection: isHome ? 'row-reverse' : 'row',
              padding: '8px 12px',
              border: '1px solid rgba(255,255,255,.08)',
              borderRadius: 10,
              background: 'rgba(255,255,255,.02)',
            }}
          >
            <span style={{ width: 8, height: 8, borderRadius: 2, background: markerColor, flex: 'none' }} />
            <div style={{ textAlign: isHome ? 'right' : 'left' }}>
              <div style={{ fontSize: 13.5, color: '#e8edf2' }}>{e.player}</div>
              <div style={mono({ fontSize: 9.5, color: '#6f8093' })}>{sub}</div>
            </div>
          </div>
        )
        return (
          <div key={i} style={{ display: 'grid', gridTemplateColumns: '1fr 56px 1fr', alignItems: 'center', marginBottom: 14 }}>
            <div style={{ display: 'flex', justifyContent: 'flex-end' }}>{e.team === 'home' && bubble(true)}</div>
            <div style={{ display: 'flex', justifyContent: 'center' }}>
              <span style={mono({ fontSize: 11, color: '#9fb0c2', background: '#0a1018', border: '1px solid rgba(255,255,255,.1)', borderRadius: 100, padding: '3px 8px' })}>
                {e.min}'
              </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-start' }}>{e.team === 'away' && bubble(false)}</div>
          </div>
        )
      })}
    </div>
  )
}

function ShotMapTab({ m, h, a, shotTeam, setShotTeam }) {
  const tcol = shotTeam === 'home' ? h.color : a.color
  const list = (m.shots || []).filter((s) => s.team === shotTeam)
  const OUT = {
    g: [tcol, tcol, 1],
    s: ['#00e0c6', '#00e0c6', 0.95],
    o: ['transparent', '#8593a3', 0.9],
    b: ['#e0a93b', '#e0a93b', 0.9],
  }
  const totalXg = list.reduce((q, s) => q + (s.xg || 0), 0).toFixed(1)
  return (
    <div style={{ padding: '22px 28px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
        <div style={{ display: 'flex', gap: 7 }}>
          {[['home', h.name], ['away', a.name]].map(([key, label]) => {
            const active = shotTeam === key
            return (
              <button
                key={key}
                onClick={() => setShotTeam(key)}
                style={{
                  position: 'relative',
                  padding: '6px 14px',
                  border: '1px solid rgba(255,255,255,.12)',
                  borderRadius: 8,
                  background: 'transparent',
                  color: '#c3cfdc',
                  fontFamily: 'var(--font-mono)',
                  fontSize: 11,
                  cursor: 'pointer',
                }}
              >
                {active && (
                  <span style={{ position: 'absolute', inset: 0, borderRadius: 8, border: '1px solid #00e0c6', background: 'rgba(0,224,198,.16)', pointerEvents: 'none' }} />
                )}
                <span style={{ position: 'relative' }}>{label}</span>
              </button>
            )
          })}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-secondary)' }}>
          <span>{list.length} SHOTS</span>
          <span style={{ color: '#2d3a48' }}>·</span>
          <span>{totalXg} xG</span>
        </div>
      </div>
      <svg viewBox="0 0 360 230" style={{ width: '100%', background: 'rgba(0,224,198,.015)', border: '1px solid rgba(255,255,255,.07)', borderRadius: 12 }}>
        <rect x="8" y="8" width="344" height="214" fill="none" stroke="rgba(255,255,255,.12)" strokeWidth="1" />
        <line x1="180" y1="8" x2="180" y2="222" stroke="rgba(255,255,255,.1)" strokeWidth="1" />
        <circle cx="180" cy="115" r="26" fill="none" stroke="rgba(255,255,255,.1)" strokeWidth="1" />
        <rect x="300" y="62" width="52" height="106" fill="none" stroke="rgba(255,255,255,.1)" strokeWidth="1" />
        <rect x="330" y="90" width="22" height="50" fill="none" stroke="rgba(255,255,255,.1)" strokeWidth="1" />
        {list.map((s, i) => {
          const [fill, stroke, op] = OUT[s.outcome] || OUT.o
          // API x,y are 0..100 pitch %; normalise so the selected team attacks
          // the right-hand goal. Map onto the right 60% of the pitch box.
          const px = 8 + (0.42 + (num(s.x) / 100) * 0.56) * 344
          const py = 8 + (num(s.y) / 100) * 214
          return (
            <circle key={i} cx={px.toFixed(1)} cy={py.toFixed(1)} r={(4 + (s.xg || 0) * 20).toFixed(1)} fill={fill} stroke={stroke} strokeWidth="1.5" opacity={op} />
          )
        })}
      </svg>
      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginTop: 14, fontFamily: 'var(--font-mono)', fontSize: 10.5, color: 'var(--text-secondary)' }}>
        <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}><span style={{ width: 10, height: 10, borderRadius: '50%', background: tcol }} />GOAL</span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}><span style={{ width: 10, height: 10, borderRadius: '50%', background: '#00e0c6' }} />ON TARGET</span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}><span style={{ width: 10, height: 10, borderRadius: '50%', border: '1.5px solid #8593a3' }} />OFF</span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}><span style={{ width: 10, height: 10, borderRadius: '50%', background: '#e0a93b' }} />BLOCKED</span>
        <span style={{ color: '#56657a' }}>· size = xG</span>
      </div>
    </div>
  )
}

// Generic position-based pitch layout (works for any real formation).
const ROW_DEPTH = { gk: 0.04, def: 0.2, mid: 0.42, fwd: 0.62 }

function layout(xi, isHome) {
  const groups = { gk: [], def: [], mid: [], fwd: [] }
  xi.forEach((p) => (groups[p.pos] || groups.mid).push(p))
  const out = []
  Object.entries(groups).forEach(([g, players]) => {
    const depth = ROW_DEPTH[g] ?? 0.42
    players.forEach((p, i) => {
      const frac = players.length === 1 ? 0.5 : 0.14 + (i / (players.length - 1)) * 0.72
      const x = 12 + frac * 276
      const y = isHome ? 408 - depth * 190 : 12 + depth * 190
      out.push({ ...p, x, y })
    })
  })
  return out
}

function LineupsTab({ m, h, a }) {
  const lh = m.lineups?.home
  const la = m.lineups?.away
  if (!lh || !la || !lh.xi?.length) {
    return <div style={mono({ padding: '40px 28px', textAlign: 'center', fontSize: 12, color: 'var(--text-muted-2)' })}>Lineups not available for this match.</div>
  }
  const homePlayers = layout(lh.xi, true)
  const awayPlayers = layout(la.xi, false)
  const teamBlock = (line, color, name) => (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 9, marginBottom: 10 }}>
        <span style={{ width: 9, height: 9, borderRadius: 2, background: color }} />
        <span style={{ fontSize: 14, fontWeight: 600 }}>{name}</span>
        <span style={mono({ fontSize: 10.5, color: '#6f8093', letterSpacing: '.1em' })}>{line.formation}</span>
      </div>
      <div style={mono({ fontSize: 10, color: '#6f8093', letterSpacing: '.08em', marginBottom: 7 })}>SUBSTITUTES</div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 7 }}>
        {(line.subs || []).map((n) => (
          <span key={n} style={{ fontSize: 12, color: '#9fb0c2', padding: '4px 9px', border: '1px solid rgba(255,255,255,.08)', borderRadius: 7 }}>
            {n}
          </span>
        ))}
      </div>
    </div>
  )
  const dots = (players, color) =>
    players.map((p, i) => (
      <g key={color + i}>
        <circle cx={p.x} cy={p.y} r="9" fill="#0a1018" stroke={color} strokeWidth="2" />
        <text x={p.x} y={p.y} dy="13" fill="#9fb0c2" fontFamily="'JetBrains Mono',monospace" fontSize="7.5" textAnchor="middle">
          {(p.name || '').split(' ').slice(-1)[0]}
        </text>
      </g>
    ))
  return (
    <div style={{ padding: '22px 28px', display: 'grid', gridTemplateColumns: '300px 1fr', gap: 26, alignItems: 'start' }}>
      <svg viewBox="0 0 300 420" style={{ width: 300, background: 'rgba(0,224,198,.015)', border: '1px solid rgba(255,255,255,.07)', borderRadius: 12 }}>
        <rect x="6" y="6" width="288" height="408" fill="none" stroke="rgba(255,255,255,.1)" strokeWidth="1" />
        <line x1="6" y1="210" x2="294" y2="210" stroke="rgba(255,255,255,.08)" strokeWidth="1" />
        <circle cx="150" cy="210" r="30" fill="none" stroke="rgba(255,255,255,.08)" strokeWidth="1" />
        <rect x="80" y="6" width="140" height="52" fill="none" stroke="rgba(255,255,255,.08)" strokeWidth="1" />
        <rect x="80" y="362" width="140" height="52" fill="none" stroke="rgba(255,255,255,.08)" strokeWidth="1" />
        {dots(awayPlayers, a.color)}
        {dots(homePlayers, h.color)}
      </svg>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>
        {teamBlock(lh, h.color, h.name)}
        {teamBlock(la, a.color, a.name)}
      </div>
    </div>
  )
}

const SUBTABS = [
  ['stats', 'STATS'],
  ['timeline', 'TIMELINE'],
  ['shots', 'SHOT MAP'],
  ['lineups', 'LINEUPS'],
]

export default function MatchLab({ match, setMatch }) {
  const [subtab, setSubtab] = useState('stats')
  const [shotTeam, setShotTeam] = useState('home')
  const [animKey, setAnimKey] = useState(0)
  const { data } = useData()
  const MATCHES = data?.matches || []
  const m = MATCHES.find((x) => x.id === match) || MATCHES[0]

  if (!m) {
    return <div style={{ marginTop: 32, paddingBottom: 150 }} />
  }
  const h = m.home
  const a = m.away

  const selectMatch = (id) => {
    setMatch(id)
    setSubtab('stats')
    setShotTeam('home')
    setAnimKey((k) => k + 1)
  }

  return (
    <div style={{ animation: 'vfade .4s ease both', marginTop: 32, paddingBottom: 150 }}>
      <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', marginBottom: 22 }}>
        <div>
          <div style={mono({ fontSize: 11, letterSpacing: '.24em', color: 'var(--text-muted-2)' })}>MATCH LAB</div>
          <div style={{ fontSize: 26, fontWeight: 700, letterSpacing: '-.01em', marginTop: 8 }}>Head-to-head match intelligence</div>
        </div>
        <span style={mono({ fontSize: 10.5, letterSpacing: '.12em', color: 'var(--text-muted)' })}>{MATCHES.length} MATCHES</span>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '240px 1fr', gap: 22, alignItems: 'start' }}>
        {/* left rail */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 9, maxHeight: 720, overflowY: 'auto' }}>
          {MATCHES.map((g) => {
            const selected = g.id === m.id
            return (
              <button
                key={g.id}
                onClick={() => selectMatch(g.id)}
                style={{
                  position: 'relative',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 8,
                  padding: '11px 13px',
                  borderRadius: 12,
                  cursor: 'pointer',
                  textAlign: 'left',
                  border: '1px solid rgba(255,255,255,.07)',
                  background: 'rgba(255,255,255,.02)',
                }}
              >
                {selected && (
                  <span style={{ position: 'absolute', inset: 0, borderRadius: 12, border: '1px solid rgba(0,224,198,.5)', background: 'rgba(0,224,198,.08)', pointerEvents: 'none' }} />
                )}
                <div style={{ position: 'relative', zIndex: 1, display: 'flex', flexDirection: 'column', gap: 8, width: '100%' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
                    <span style={mono({ fontSize: 9, letterSpacing: '.1em', color: '#6f8093' })}>{g.round}</span>
                    <span style={mono({ fontSize: 9, color: '#56657a' })}>{g.date}</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
                      <span style={{ width: 7, height: 7, borderRadius: 2, background: g.home.color }} />
                      <span style={mono({ fontSize: 13, color: 'var(--text-body)' })}>{g.home.code}</span>
                    </div>
                    <span style={mono({ fontSize: 13, fontWeight: 700, color: '#fff' })}>
                      {g.score[0]}–{g.score[1]}
                    </span>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
                      <span style={mono({ fontSize: 13, color: 'var(--text-body)' })}>{g.away.code}</span>
                      <span style={{ width: 7, height: 7, borderRadius: 2, background: g.away.color }} />
                    </div>
                  </div>
                </div>
              </button>
            )
          })}
        </div>

        {/* right panel */}
        <div style={{ background: 'linear-gradient(180deg,rgba(255,255,255,.04),rgba(255,255,255,.01))', border: '1px solid rgba(255,255,255,.09)', borderRadius: 18, overflow: 'hidden' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr auto 1fr', alignItems: 'center', gap: 20, padding: '24px 28px 18px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, justifyContent: 'flex-start' }}>
              <span style={{ width: 12, height: 12, borderRadius: 3, background: h.color, boxShadow: `0 0 12px ${h.color}` }} />
              <div>
                <div style={{ fontSize: 18, fontWeight: 600 }}>{h.name}</div>
                <div style={mono({ fontSize: 10, color: '#6f8093', letterSpacing: '.1em' })}>HOME</div>
              </div>
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 40, fontWeight: 700, lineHeight: 1 }}>
                {m.score[0]}
                <span style={{ color: '#56657a', margin: '0 10px' }}>:</span>
                {m.score[1]}
              </div>
              <div style={mono({ fontSize: 9.5, color: '#6f8093', letterSpacing: '.1em', marginTop: 7 })}>FT · {m.round}</div>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, justifyContent: 'flex-end' }}>
              <div style={{ textAlign: 'right' }}>
                <div style={{ fontSize: 18, fontWeight: 600 }}>{a.name}</div>
                <div style={mono({ fontSize: 10, color: '#6f8093', letterSpacing: '.1em' })}>AWAY</div>
              </div>
              <span style={{ width: 12, height: 12, borderRadius: 3, background: a.color, boxShadow: `0 0 12px ${a.color}` }} />
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 16, flexWrap: 'wrap', padding: '0 28px 18px', fontFamily: 'var(--font-mono)', fontSize: 10.5, color: '#6f8093', letterSpacing: '.03em' }}>
            <span>{m.date}</span>
            <span style={{ color: '#2d3a48' }}>·</span>
            <span>{m.venue}{m.city ? `, ${m.city}` : ''}</span>
            <span style={{ color: '#2d3a48' }}>·</span>
            <span>REF {m.ref}</span>
          </div>

          <div style={{ display: 'flex', gap: 4, padding: '0 22px', borderBottom: '1px solid rgba(255,255,255,.07)' }}>
            {SUBTABS.map(([key, label]) => {
              const active = subtab === key
              return (
                <button
                  key={key}
                  onClick={() => {
                    setSubtab(key)
                    if (key === 'stats') setAnimKey((k) => k + 1)
                  }}
                  style={{
                    position: 'relative',
                    padding: '11px 16px',
                    border: 'none',
                    background: 'transparent',
                    color: active ? '#eaf2f0' : '#9fb0c2',
                    fontFamily: 'var(--font-mono)',
                    fontSize: 11.5,
                    letterSpacing: '.08em',
                    cursor: 'pointer',
                  }}
                >
                  <span style={{ position: 'relative' }}>{label}</span>
                  {active && <span style={{ position: 'absolute', left: 8, right: 8, bottom: -1, height: 2, background: 'var(--teal)' }} />}
                </button>
              )
            })}
          </div>

          {subtab === 'stats' && <StatsTab m={m} h={h} a={a} animKey={animKey} />}
          {subtab === 'timeline' && <TimelineTab m={m} />}
          {subtab === 'shots' && <ShotMapTab m={m} h={h} a={a} shotTeam={shotTeam} setShotTeam={setShotTeam} />}
          {subtab === 'lineups' && <LineupsTab m={m} h={h} a={a} />}
        </div>
      </div>
    </div>
  )
}
