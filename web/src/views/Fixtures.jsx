import { useState } from 'react'
import { useData } from '../data/DataContext.jsx'

const mono = (extra) => ({ fontFamily: 'var(--font-mono)', ...extra })

const TABS = [
  ['all', 'All'],
  ['done', 'Results'],
  ['upcoming', 'Schedule'],
]

export default function Fixtures({ openMatchLab, goBracket }) {
  const [filter, setFilter] = useState('all')
  const { data } = useData()
  const fixtures = data?.fixtures || []
  const labIds = new Set((data?.matches || []).map((m) => m.id))
  const all = fixtures.map((f) => ({
    ...f,
    sh: f.status === 'done' && f.sh != null ? String(f.sh) : '–',
    sa: f.status === 'done' && f.sa != null ? String(f.sa) : '–',
    // group-stage matches with lab detail deep-link into Match Lab; others jump to the bracket
    on: labIds.has(f.matchId) ? () => openMatchLab(f.matchId) : goBracket,
    venue: '',
  }))
  const rows = all.filter((f) => filter === 'all' || f.status === filter)

  return (
    <div style={{ animation: 'vfade .4s ease both', marginTop: 32, paddingBottom: 150 }}>
      <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', marginBottom: 18 }}>
        <div>
          <div style={mono({ fontSize: 11, letterSpacing: '.24em', color: 'var(--text-muted-2)' })}>FIXTURES</div>
          <div style={{ fontSize: 26, fontWeight: 700, letterSpacing: '-.01em', marginTop: 8 }}>Full schedule &amp; results history</div>
        </div>
        <div style={{ display: 'flex', gap: 4, padding: 4, background: 'rgba(255,255,255,.03)', border: '1px solid rgba(255,255,255,.07)', borderRadius: 100 }}>
          {TABS.map(([key, label]) => {
            const active = key === filter
            return (
              <button
                key={key}
                onClick={() => setFilter(key)}
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
      <div style={mono({ marginBottom: 10, fontSize: 10, letterSpacing: '.08em', color: 'var(--text-dim)' })}>{rows.length} fixtures</div>
      <div
        style={{
          background: 'linear-gradient(180deg,rgba(255,255,255,.05),rgba(255,255,255,.01))',
          border: '1px solid rgba(255,255,255,.09)',
          borderRadius: 16,
          overflow: 'hidden',
          position: 'relative',
        }}
      >
        <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 1, background: 'linear-gradient(90deg,transparent,rgba(0,224,198,.4),transparent)' }} />
        {rows.map((f, i) => {
          const done = f.status === 'done'
          return (
            <div
              key={i}
              onClick={f.on}
              style={{
                display: 'grid',
                gridTemplateColumns: '120px 1fr 90px 90px',
                alignItems: 'center',
                gap: 14,
                padding: '13px 20px',
                borderBottom: '1px solid rgba(255,255,255,.05)',
                cursor: 'pointer',
              }}
            >
              <div>
                <div style={mono({ fontSize: 9, letterSpacing: '.08em', color: 'var(--text-dim-2)' })}>{f.round}</div>
                <div style={mono({ fontSize: 10.5, color: 'var(--text-secondary-2)', marginTop: 3 })}>{f.date}</div>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 14 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, justifyContent: 'flex-end', width: 110 }}>
                  <span style={mono({ fontSize: 13, fontWeight: 600, color: 'var(--text-body)' })}>{f.hCode}</span>
                  <span style={{ width: 7, height: 7, borderRadius: 2, background: f.hCol, flex: 'none' }} />
                </div>
                <span style={mono({ fontSize: 15, fontWeight: 700, color: done ? 'var(--text-brightest)' : 'var(--text-dim-2)', width: 44, textAlign: 'center' })}>
                  {f.sh}–{f.sa}
                </span>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, width: 110 }}>
                  <span style={{ width: 7, height: 7, borderRadius: 2, background: f.aCol, flex: 'none' }} />
                  <span style={mono({ fontSize: 13, fontWeight: 600, color: 'var(--text-body)' })}>{f.aCode}</span>
                </div>
              </div>
              <div style={mono({ fontSize: 9.5, color: 'var(--text-dim-2)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' })}>{f.venue}</div>
              <div
                style={mono({
                  justifySelf: 'end',
                  padding: '4px 10px',
                  borderRadius: 100,
                  background: done ? 'rgba(0,224,198,.1)' : 'rgba(255,255,255,.05)',
                  fontSize: 9,
                  letterSpacing: '.08em',
                  color: done ? 'var(--teal)' : 'var(--text-secondary)',
                })}
              >
                {done ? 'FT' : 'SCHEDULED'}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
