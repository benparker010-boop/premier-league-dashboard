import BracketGrid from '../components/BracketGrid.jsx'
import BracketLegend from '../components/BracketLegend.jsx'

export default function BracketView() {
  return (
    <div style={{ animation: 'vfade .4s ease both', marginTop: 32, paddingBottom: 150 }}>
      <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', marginBottom: 20 }}>
        <div>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, letterSpacing: '.24em', color: 'var(--text-muted-2)' }}>BRACKET</div>
          <div style={{ fontSize: 26, fontWeight: 700, letterSpacing: '-.01em', marginTop: 8 }}>
            Knockout stage · confirmed fixtures &amp; Parker's projected path to the final
          </div>
        </div>
        <BracketLegend full />
      </div>
      <BracketGrid />
    </div>
  )
}
