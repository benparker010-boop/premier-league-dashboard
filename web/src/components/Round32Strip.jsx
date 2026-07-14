import { useData } from '../data/DataContext.jsx'
import Flag from './Flag.jsx'

const mono = (extra) => ({ fontFamily: 'var(--font-mono)', ...extra })

/*
  Compact Round-of-32 results grid — the 16 matches that produce the Round of
  16 field. BracketGrid's precise connector-line diagram starts at the R16,
  so this reuses its "result" tier visual language (teal border/tint, bright
  winner, dimmed loser) as a standalone strip rather than a 5th bracket
  column, since by the time the R16 exists these are already final scores.
*/
export default function Round32Strip() {
  const { data } = useData()
  const r32 = (data?.fixtures || []).filter((f) => f.round === 'ROUND OF 32')
  if (!r32.length) return null

  return (
    <div style={{ marginBottom: 30 }}>
      <div style={mono({ fontSize: 9.5, letterSpacing: '.2em', color: '#3d4f60', marginBottom: 10 })}>ROUND OF 32</div>
      <div className="pk-groups" style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 10 }}>
        {r32.map((f, i) => {
          const done = f.status === 'done'
          const hWon = done && f.sh > f.sa
          const aWon = done && f.sa > f.sh
          return (
            <div
              key={i}
              style={{
                background: done ? 'linear-gradient(135deg,rgba(0,224,198,.07),rgba(0,224,198,.02))' : 'linear-gradient(135deg,rgba(255,255,255,.04),rgba(255,255,255,.01))',
                border: `1px solid ${done ? 'rgba(0,224,198,.25)' : 'rgba(255,255,255,.09)'}`,
                borderRadius: 10,
                padding: '8px 11px',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <Flag code={f.hCode} color={f.hCol} height={10} />
                  <span style={mono({ fontSize: 11, fontWeight: 600, color: hWon || !done ? 'var(--text-body)' : 'var(--text-dim-2)' })}>{f.hCode}</span>
                </div>
                <span style={mono({ fontSize: 12.5, fontWeight: 700, color: hWon ? '#fff' : 'var(--text-dim-2)' })}>{done ? f.sh : '–'}</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 3 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <Flag code={f.aCode} color={f.aCol} height={10} />
                  <span style={mono({ fontSize: 11, fontWeight: 600, color: aWon || !done ? 'var(--text-body)' : 'var(--text-dim-2)' })}>{f.aCode}</span>
                </div>
                <span style={mono({ fontSize: 12.5, fontWeight: 700, color: aWon ? '#fff' : 'var(--text-dim-2)' })}>{done ? f.sa : '–'}</span>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
