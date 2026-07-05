import { useData } from '../data/DataContext.jsx'

const mono = (extra) => ({ fontFamily: 'var(--font-mono)', ...extra })

export default function Groups() {
  const { data } = useData()
  const GROUPS_DATA = data?.groups || []
  return (
    <div style={{ animation: 'vfade .4s ease both', marginTop: 32, paddingBottom: 150 }}>
      <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', marginBottom: 24 }}>
        <div>
          <div style={mono({ fontSize: 11, letterSpacing: '.24em', color: 'var(--text-muted-2)' })}>GROUPS</div>
          <div style={{ fontSize: 26, fontWeight: 700, letterSpacing: '-.01em', marginTop: 8 }}>All 12 group standings</div>
        </div>
        <div style={{ display: 'flex', gap: 16, fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-muted)' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ width: 8, height: 8, borderRadius: 2, background: 'rgba(0,224,198,.45)' }} />QUALIFIED
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ width: 8, height: 8, borderRadius: 2, background: 'rgba(255,255,255,.12)' }} />ELIMINATED
          </span>
        </div>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 14 }}>
        {GROUPS_DATA.map((grp) => (
          <div
            key={grp.name}
            style={{
              background: 'linear-gradient(180deg,rgba(255,255,255,.05),rgba(255,255,255,.01))',
              border: '1px solid rgba(255,255,255,.09)',
              borderRadius: 14,
              overflow: 'hidden',
              position: 'relative',
            }}
          >
            <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 1, background: 'linear-gradient(90deg,transparent,rgba(0,224,198,.45),transparent)' }} />
            <div style={{ padding: '12px 14px 8px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={mono({ fontSize: 13, fontWeight: 700, letterSpacing: '.1em', color: 'var(--text-brightest)' })}>GROUP {grp.name}</span>
              <span style={mono({ fontSize: 8.5, color: 'var(--text-dim)', letterSpacing: '.06em', whiteSpace: 'pre' })}>P  W  D  L  GD  Pts</span>
            </div>
            {grp.teams.map((t, i) => {
              const qual = t.qual !== 'x'
              return (
                <div
                  key={t.code}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 7,
                    padding: '6px 14px',
                    background: t.qual === 'q1' ? 'rgba(0,224,198,.06)' : t.qual === 'q2' ? 'rgba(0,224,198,.03)' : 'transparent',
                    borderTop: '1px solid rgba(255,255,255,.04)',
                  }}
                >
                  <span style={mono({ fontSize: 10, color: 'var(--text-dim)', width: 10, textAlign: 'center', flex: 'none' })}>{i + 1}</span>
                  <span style={{ width: 7, height: 7, borderRadius: 2, background: t.color, flex: 'none' }} />
                  <span style={mono({ fontSize: 10.5, fontWeight: 600, color: qual ? 'var(--text-body)' : 'var(--text-dim-2)', flex: 1, minWidth: 0 })}>{t.code}</span>
                  <div style={{ display: 'flex', fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-dim-2)' }}>
                    <span style={{ width: 16, textAlign: 'center' }}>{t.p}</span>
                    <span style={{ width: 16, textAlign: 'center' }}>{t.w}</span>
                    <span style={{ width: 16, textAlign: 'center' }}>{t.d}</span>
                    <span style={{ width: 16, textAlign: 'center' }}>{t.l}</span>
                    <span style={{ width: 26, textAlign: 'center', color: '#6f8093' }}>{(t.gd >= 0 ? '+' : '') + t.gd}</span>
                    <span style={{ width: 22, textAlign: 'right', fontWeight: qual ? 700 : 400, color: qual ? 'var(--text-brightest)' : 'var(--text-dim-2)' }}>{t.pts}</span>
                  </div>
                </div>
              )
            })}
          </div>
        ))}
      </div>
    </div>
  )
}
