import { useLayoutEffect, useRef } from 'react'
import { useData } from '../data/DataContext.jsx'

/*
  The knockout bracket — the most important screen in the app.

  Three semantic tiers (per spec, do not simplify), driven by real data:
  1. RESULT      — a played Round-of-16 match. Solid teal border, teal tint,
                   real score. Winner bright, loser dimmed. Tag "RESULT", "FT".
  2. CONFIRMED   — a real R16 fixture not yet played. Solid neutral border.
                   Parker's predicted winner bright, underdog dim. Tag
                   "CONFIRMED", favored code + model win% (teal).
  3. PROJECTED   — QF/SF/Final: the matchup itself is Parker's forecast, built
                   by simulating the R16 winners forward. Dashed amber border +
                   amber tint. Tag "PROJECTED". The Final reads "PREDICTED
                   CHAMPION" and gets a gold glow.

  Fit: natural size 980×810, scaled by min(1, width/980) via ResizeObserver —
  never upscales, never scrolls horizontally.
*/

// card object from predictions.json: {home:{code,color}, away:{code,color},
// done, sh, sa, winner, favHome, prob, tier}
function tierProps(m) {
  const predSide = m.done ? m.winner : m.favHome ? 'home' : 'away'
  const hOn = predSide === 'home'
  const aOn = predSide === 'away'
  const isResult = m.tier === 'result'
  const isProjected = m.tier === 'projected'
  const favCode = m.favHome ? m.home.code : m.away.code
  return {
    hCode: m.home.code, hCol: m.home.color, aCode: m.away.code, aCol: m.away.color,
    sh: m.done && m.sh != null ? String(m.sh) : '–',
    sa: m.done && m.sa != null ? String(m.sa) : '–',
    hTextCol: hOn ? '#e8f8f5' : '#3d4f60', aTextCol: aOn ? '#e8f8f5' : '#3d4f60',
    hScoreCol: hOn ? '#ffffff' : '#3d4f60', aScoreCol: aOn ? '#ffffff' : '#3d4f60',
    bg: isResult
      ? 'linear-gradient(135deg,rgba(0,224,198,.09),rgba(0,224,198,.03))'
      : isProjected
        ? 'linear-gradient(135deg,rgba(245,196,81,.06),rgba(255,255,255,.012))'
        : 'linear-gradient(135deg,rgba(255,255,255,.05),rgba(255,255,255,.02))',
    bd: isResult ? 'rgba(0,224,198,.32)' : isProjected ? 'rgba(245,196,81,.4)' : 'rgba(200,210,220,.28)',
    bStyle: isProjected ? 'dashed' : 'solid',
    tagText: isResult ? 'RESULT' : isProjected ? 'PROJECTED' : 'CONFIRMED',
    tagCol: isResult ? '#00e0c6' : isProjected ? '#f5c451' : '#c3cfdc',
    probText: isResult ? 'FT' : favCode + ' ' + m.prob + '%',
    probCol: isResult ? '#3d4f60' : isProjected ? '#f5c451' : '#00e0c6',
  }
}

function MatchCard({ m, x, y, final = false }) {
  const t = tierProps(m)
  const row = (code, col, textCol, score, scoreCol, glowDot) => (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <span style={{ width: 6, height: 6, borderRadius: 2, background: col, flex: 'none', boxShadow: glowDot ? `0 0 5px ${col}` : undefined }} />
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11.5, fontWeight: 600, color: textCol }}>{code}</span>
      </div>
      <span style={{ fontFamily: 'var(--font-mono)', fontSize: 14, fontWeight: 700, color: scoreCol }}>{score}</span>
    </div>
  )
  const card = (
    <div
      style={{
        background: final ? 'linear-gradient(135deg,rgba(245,196,81,.11),rgba(245,196,81,.03))' : t.bg,
        border: final ? '1px dashed rgba(245,196,81,.5)' : `1px ${t.bStyle} ${t.bd}`,
        borderRadius: 10,
        padding: '9px 12px',
        height: 76,
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        boxShadow: final ? '0 0 28px rgba(245,196,81,.08)' : undefined,
      }}
    >
      {row(t.hCode, t.hCol, t.hTextCol, t.sh, t.hScoreCol, true)}
      {row(t.aCode, t.aCol, t.aTextCol, t.sa, t.aScoreCol, false)}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 7.5, letterSpacing: '.05em', color: final ? '#f5c451' : t.tagCol }}>
          {final ? 'PREDICTED CHAMPION' : t.tagText}
        </span>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 8, fontWeight: 700, color: final ? '#f5c451' : t.probCol }}>
          {final ? t.hCode + ' ' + m.prob + '%' : t.probText}
        </span>
      </div>
    </div>
  )
  if (final) {
    return (
      <div style={{ position: 'absolute', left: 780, top: 344, width: 200 }}>
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: 9, letterSpacing: '.14em', color: '#f5c451', textAlign: 'center', marginBottom: 5 }}>
          PROJECTED FINAL
        </div>
        {card}
      </div>
    )
  }
  return <div style={{ position: 'absolute', left: x, top: y, width: 200 }}>{card}</div>
}

const R16Y = [0, 92, 208, 300, 416, 508, 624, 716]
const QFY = [46, 254, 462, 670]
const SFY = [150, 566]

const colLabel = {
  textAlign: 'center',
  fontFamily: 'var(--font-mono)',
  fontSize: 9.5,
  letterSpacing: '.2em',
  color: '#3d4f60',
}

export default function BracketGrid() {
  const wrapRef = useRef(null)
  const innerRef = useRef(null)
  const { data } = useData()

  useLayoutEffect(() => {
    const wrap = wrapRef.current
    const inner = innerRef.current
    if (!wrap || !inner) return
    let last = null
    const fit = () => {
      const w = wrap.offsetWidth
      if (!w) return
      const scale = Math.round(Math.min(1, w / 980) * 1000) / 1000
      if (last === scale) return
      last = scale
      inner.style.transform = `scale(${scale})`
      const h = inner.scrollHeight || 810
      wrap.style.height = Math.ceil(h * scale) + 'px'
    }
    fit()
    const ro = new ResizeObserver(fit)
    ro.observe(wrap)
    return () => ro.disconnect()
  }, [data])

  const bracket = data?.predictions?.bracket
  const r16 = bracket?.r16 || []
  const qf = bracket?.qf || []
  const sf = bracket?.sf || []
  const final = bracket?.final

  return (
    <div ref={wrapRef} style={{ width: '100%', overflow: 'hidden', position: 'relative' }}>
      <div ref={innerRef} style={{ width: 980, transformOrigin: 'top left' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '200px 60px 200px 60px 200px 60px 200px', marginBottom: 12 }}>
          <div style={colLabel}>ROUND OF 16</div>
          <div />
          <div style={colLabel}>QUARTER-FINALS</div>
          <div />
          <div style={colLabel}>SEMI-FINALS</div>
          <div />
          <div style={colLabel}>FINAL</div>
        </div>
        <div style={{ position: 'relative', width: 980, height: 810 }}>
          <svg style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }} viewBox="0 0 980 810" width="980" height="810">
            <g stroke="rgba(0,224,198,.22)" strokeWidth="1.5" fill="none" strokeDasharray="6 5" style={{ animation: 'dash 3.5s linear infinite' }}>
              <line x1="200" y1="38" x2="230" y2="38" /><line x1="200" y1="130" x2="230" y2="130" /><line x1="230" y1="38" x2="230" y2="130" /><line x1="230" y1="84" x2="260" y2="84" />
              <line x1="200" y1="246" x2="230" y2="246" /><line x1="200" y1="338" x2="230" y2="338" /><line x1="230" y1="246" x2="230" y2="338" /><line x1="230" y1="292" x2="260" y2="292" />
              <line x1="200" y1="454" x2="230" y2="454" /><line x1="200" y1="546" x2="230" y2="546" /><line x1="230" y1="454" x2="230" y2="546" /><line x1="230" y1="500" x2="260" y2="500" />
              <line x1="200" y1="662" x2="230" y2="662" /><line x1="200" y1="754" x2="230" y2="754" /><line x1="230" y1="662" x2="230" y2="754" /><line x1="230" y1="708" x2="260" y2="708" />
              <line x1="460" y1="84" x2="490" y2="84" /><line x1="460" y1="292" x2="490" y2="292" /><line x1="490" y1="84" x2="490" y2="292" /><line x1="490" y1="188" x2="520" y2="188" />
              <line x1="460" y1="500" x2="490" y2="500" /><line x1="460" y1="708" x2="490" y2="708" /><line x1="490" y1="500" x2="490" y2="708" /><line x1="490" y1="604" x2="520" y2="604" />
              <line x1="720" y1="188" x2="750" y2="188" /><line x1="720" y1="604" x2="750" y2="604" /><line x1="750" y1="188" x2="750" y2="604" /><line x1="750" y1="396" x2="780" y2="396" />
            </g>
            <g fill="rgba(0,224,198,.65)">
              <circle cx="230" cy="84" r="3.5" /><circle cx="230" cy="292" r="3.5" /><circle cx="230" cy="500" r="3.5" /><circle cx="230" cy="708" r="3.5" />
              <circle cx="490" cy="188" r="3.5" /><circle cx="490" cy="604" r="3.5" />
              <circle cx="750" cy="396" r="4" style={{ filter: 'drop-shadow(0 0 6px rgba(0,224,198,.8))' }} />
            </g>
          </svg>
          {r16.map((m, i) => (
            <MatchCard key={'r16' + i} m={m} x={0} y={R16Y[i]} />
          ))}
          {qf.map((m, i) => (
            <MatchCard key={'qf' + i} m={m} x={260} y={QFY[i]} />
          ))}
          {sf.map((m, i) => (
            <MatchCard key={'sf' + i} m={m} x={520} y={SFY[i]} />
          ))}
          {final && <MatchCard m={final} final />}
        </div>
      </div>
    </div>
  )
}
