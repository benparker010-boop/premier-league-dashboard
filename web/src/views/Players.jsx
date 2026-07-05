import { useState } from 'react'
import { useData } from '../data/DataContext.jsx'

const mono = (extra) => ({ fontFamily: 'var(--font-mono)', ...extra })

const TABS = [
  ['goals', 'Goals'],
  ['xg', 'xG'],
  ['assists', 'Assists'],
  ['cards', 'Cards'],
]
const KEY = { goals: 'goals', xg: 'xg', assists: 'assists', cards: 'yc' }

export default function Players() {
  const [tab, setTab] = useState('goals')
  const [search, setSearch] = useState('')
  const { data } = useData()
  const PLAYERS_DATA = data?.players?.players || []
  const totals = data?.players?.totals || { goals: 0, xg: 0, assists: 0, tracked: 0 }

  const key = KEY[tab] || 'goals'
  const q = search.trim().toLowerCase()
  const filtered = q
    ? PLAYERS_DATA.filter(
        (pl) => pl.name.toLowerCase().includes(q) || pl.code.toLowerCase().includes(q) || pl.nation.toLowerCase().includes(q),
      )
    : PLAYERS_DATA
  const maxV = filtered.reduce((m, x) => Math.max(m, x[key] || 0), 0) || 1
  const sorted = [...filtered].sort((a, b) => (b[key] || 0) - (a[key] || 0))
  const overallTop = [...PLAYERS_DATA].sort((a, b) => b.goals - a.goals)[0] || { code: '', name: '—', goals: 0, xg: 0, assists: 0 }

  const tourneyGoals = totals.goals
  const tourneyXG = totals.xg.toFixed(1)
  const tourneyAssists = totals.assists

  const rankCol = (i) => (i === 0 ? '#f5c451' : i === 1 ? '#c0c8d4' : i === 2 ? '#c87830' : '#56708a')

  return (
    <div style={{ animation: 'vfade .4s ease both', marginTop: 32, paddingBottom: 150 }}>
      <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', marginBottom: 18 }}>
        <div>
          <div style={mono({ fontSize: 11, letterSpacing: '.24em', color: 'var(--text-muted-2)' })}>PLAYERS</div>
          <div style={{ fontSize: 26, fontWeight: 700, letterSpacing: '-.01em', marginTop: 8 }}>Individual stats &amp; leaderboards</div>
        </div>
        <div style={{ display: 'flex', gap: 4, padding: 4, background: 'rgba(255,255,255,.03)', border: '1px solid rgba(255,255,255,.07)', borderRadius: 100 }}>
          {TABS.map(([k, label]) => {
            const active = tab === k
            return (
              <button
                key={k}
                onClick={() => setTab(k)}
                style={{
                  position: 'relative',
                  padding: '7px 16px',
                  border: 'none',
                  borderRadius: 100,
                  background: 'transparent',
                  fontFamily: 'var(--font-mono)',
                  fontSize: 11,
                  fontWeight: active ? 600 : 400,
                  letterSpacing: '.06em',
                  cursor: 'pointer',
                  color: active ? 'var(--text-brightest)' : '#6f8093',
                }}
              >
                {active && (
                  <span style={{ position: 'absolute', inset: 0, borderRadius: 100, background: 'linear-gradient(135deg,rgba(0,224,198,.2),rgba(0,224,198,.07))', border: '1px solid rgba(0,224,198,.42)' }} />
                )}
                <span style={{ position: 'relative' }}>{label}</span>
              </button>
            )
          })}
        </div>
      </div>

      {/* search */}
      <div style={{ position: 'relative', marginBottom: 18 }}>
        <svg
          style={{ position: 'absolute', left: 15, top: '50%', transform: 'translateY(-50%)', pointerEvents: 'none' }}
          width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#56708a" strokeWidth="2"
        >
          <circle cx="11" cy="11" r="7" />
          <line x1="21" y1="21" x2="16.65" y2="16.65" />
        </svg>
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search any player, team code or nation…"
          style={{
            width: '100%',
            padding: '13px 40px 13px 40px',
            background: 'rgba(255,255,255,.03)',
            border: '1px solid rgba(255,255,255,.1)',
            borderRadius: 12,
            color: '#eaf2f0',
            fontSize: 14,
            outline: 'none',
            fontFamily: 'var(--font-display)',
          }}
        />
        {q.length > 0 && (
          <button
            onClick={() => setSearch('')}
            style={{
              position: 'absolute',
              right: 12,
              top: '50%',
              transform: 'translateY(-50%)',
              width: 22,
              height: 22,
              border: 'none',
              borderRadius: '50%',
              background: 'rgba(255,255,255,.08)',
              color: '#9fb0c2',
              fontSize: 13,
              cursor: 'pointer',
              lineHeight: 1,
            }}
          >
            ×
          </button>
        )}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10, padding: '0 2px' }}>
        <span style={mono({ fontSize: 10, letterSpacing: '.08em', color: 'var(--text-dim)' })}>
          {sorted.length} of {totals.tracked} players
        </span>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1.1fr .9fr', gap: 20 }}>
        {/* leaderboard */}
        <div
          style={{
            background: 'linear-gradient(180deg,rgba(255,255,255,.05),rgba(255,255,255,.01))',
            border: '1px solid rgba(255,255,255,.09)',
            borderRadius: 16,
            overflow: 'hidden',
            position: 'relative',
          }}
        >
          <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 1, background: 'linear-gradient(90deg,transparent,rgba(0,224,198,.42),transparent)' }} />
          <div
            style={mono({
              display: 'grid',
              gridTemplateColumns: '32px 1fr 72px 34px 34px 40px',
              alignItems: 'center',
              padding: '10px 16px',
              borderBottom: '1px solid rgba(255,255,255,.07)',
              fontSize: 9,
              letterSpacing: '.1em',
              color: 'var(--text-dim)',
            })}
          >
            <span>#</span><span>PLAYER</span><span /><span style={{ textAlign: 'center' }}>G</span><span style={{ textAlign: 'center' }}>A</span><span style={{ textAlign: 'right' }}>xG</span>
          </div>
          <div style={{ maxHeight: 500, overflowY: 'auto' }}>
            {sorted.map((pl, i) => (
              <div
                key={pl.name + pl.code}
                style={{ display: 'grid', gridTemplateColumns: '32px 1fr 72px 34px 34px 40px', alignItems: 'center', padding: '9px 16px', borderBottom: '1px solid rgba(255,255,255,.04)' }}
              >
                <span style={mono({ fontSize: 11, fontWeight: 700, color: rankCol(i) })}>{i + 1}</span>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
                  <span style={{ width: 7, height: 7, borderRadius: 2, background: pl.color, flex: 'none', boxShadow: `0 0 6px ${pl.color}` }} />
                  <div style={{ minWidth: 0 }}>
                    <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-body)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{pl.name}</div>
                    <div style={mono({ fontSize: 9, color: 'var(--text-dim)', letterSpacing: '.04em', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' })}>
                      {pl.code} · {pl.nation}
                    </div>
                  </div>
                </div>
                <div style={{ height: 4, background: 'rgba(255,255,255,.07)', borderRadius: 3, overflow: 'hidden' }}>
                  <div
                    style={{
                      height: '100%',
                      width: `${Math.round(((pl[key] || 0) / maxV) * 100)}%`,
                      background: `linear-gradient(90deg,${pl.color},rgba(0,224,198,.5))`,
                      borderRadius: 3,
                    }}
                  />
                </div>
                <span style={mono({ fontSize: 13, fontWeight: 700, color: 'var(--text-body)', textAlign: 'center' })}>{pl.goals}</span>
                <span style={mono({ fontSize: 12, color: 'var(--text-secondary-2)', textAlign: 'center' })}>{pl.assists}</span>
                <span style={mono({ fontSize: 11, color: 'var(--text-muted-2)', textAlign: 'right' })}>{pl.xg.toFixed(1)}</span>
              </div>
            ))}
            {sorted.length === 0 && (
              <div style={mono({ padding: '40px 20px', textAlign: 'center', fontSize: 12, color: 'var(--text-muted-2)' })}>
                No players match "{search}"
              </div>
            )}
          </div>
        </div>

        {/* right column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div
            style={{
              background: 'linear-gradient(135deg,rgba(245,196,81,.1),rgba(245,196,81,.03))',
              border: '1px solid rgba(245,196,81,.28)',
              borderRadius: 14,
              padding: '18px 20px',
              position: 'relative',
              overflow: 'hidden',
            }}
          >
            <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 1, background: 'linear-gradient(90deg,transparent,rgba(245,196,81,.6),transparent)' }} />
            <div style={mono({ fontSize: 10, letterSpacing: '.16em', color: '#caa24f', marginBottom: 14 })}>GOLDEN BOOT LEADER</div>
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
                <span style={mono({ fontSize: 13, fontWeight: 700, color: 'var(--gold)' })}>{overallTop.code}</span>
              </div>
              <div>
                <div style={{ fontSize: 19, fontWeight: 700, color: 'var(--text-brightest)' }}>{overallTop.name}</div>
                <div style={mono({ fontSize: 10.5, color: 'var(--text-secondary-2)', marginTop: 4 })}>
                  {overallTop.goals} goals · {overallTop.xg.toFixed(1)} xG · {overallTop.assists} ast
                </div>
              </div>
            </div>
          </div>

          <div
            style={{
              background: 'linear-gradient(180deg,rgba(255,255,255,.04),rgba(255,255,255,.01))',
              border: '1px solid rgba(255,255,255,.09)',
              borderRadius: 14,
              padding: '18px 20px',
              flex: 1,
            }}
          >
            <div style={mono({ fontSize: 10, letterSpacing: '.14em', color: 'var(--text-muted)', marginBottom: 18 })}>TOURNAMENT TOTALS</div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 18 }}>
              {[
                [tourneyGoals, 'GOALS SCORED', '#f5c451'],
                [tourneyXG, 'TOTAL xG', '#5b8cff'],
                [totals.tracked, 'PLAYERS TRACKED', '#00e0c6'],
                [tourneyAssists, 'ASSISTS', '#ef7d52'],
              ].map(([val, label, accent]) => (
                <div key={label} style={{ borderLeft: `2px solid ${accent}`, paddingLeft: 12 }}>
                  <div style={{ fontSize: 34, fontWeight: 700, color: 'var(--text-brightest)', letterSpacing: '-.02em', lineHeight: 1 }}>{val}</div>
                  <div style={mono({ fontSize: 9, color: 'var(--text-dim)', marginTop: 5, letterSpacing: '.06em' })}>{label}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
