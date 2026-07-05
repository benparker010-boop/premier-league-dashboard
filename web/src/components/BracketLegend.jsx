/* 3-item legend for the knockout bracket. `full` uses the dedicated Bracket
   view's longer labels; the compact form is used on the Overview embed. */
export default function BracketLegend({ full = false }) {
  const item = (swatch, label) => (
    <span style={{ display: 'flex', alignItems: 'center', gap: full ? 6 : 5 }}>
      {swatch}
      {label}
    </span>
  )
  const size = full ? 8 : 7
  const sq = (bg) => <span style={{ width: size, height: size, borderRadius: 2, background: bg }} />
  return (
    <div style={{ display: 'flex', gap: full ? 16 : 14, fontFamily: 'var(--font-mono)', fontSize: full ? 9.5 : 9, color: 'var(--text-muted)' }}>
      {item(sq('rgba(0,224,198,.5)'), 'RESULT')}
      {item(sq('rgba(200,210,220,.4)'), full ? 'CONFIRMED · PARKER PICK' : 'CONFIRMED')}
      {item(
        <span style={{ width: size, height: size, borderRadius: 2, border: '1px dashed rgba(245,196,81,.7)' }} />,
        full ? 'PROJECTED PATH' : 'PROJECTED',
      )}
    </div>
  )
}
