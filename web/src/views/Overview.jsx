import { useEffect, useRef, useState } from 'react'
import LogoMark from '../components/LogoMark.jsx'
import Flag from '../components/Flag.jsx'
import BracketGrid from '../components/BracketGrid.jsx'
import BracketLegend from '../components/BracketLegend.jsx'
import ChatMessages from '../components/ChatMessages.jsx'
import useTween from '../hooks/useTween.js'
import { useData } from '../data/DataContext.jsx'

const SUGGESTIONS = [
  "Who's most likely to win the World Cup?",
  'Predict the final',
  'Best xG in the tournament?',
  'Who wins the Golden Boot?',
  'Argentina vs Spain — who advances?',
]

const mono = (extra) => ({ fontFamily: 'var(--font-mono)', ...extra })

function QueryBar({ query, setQuery, onSubmit, placeholder }) {
  const inputRef = useRef(null)
  useEffect(() => {
    const t = setTimeout(() => inputRef.current && inputRef.current.focus(), 400)
    return () => clearTimeout(t)
  }, [])
  return (
    <div style={{ position: 'relative', marginTop: 28 }}>
      <div
        style={{
          position: 'absolute',
          inset: -1,
          borderRadius: 16,
          background: 'linear-gradient(120deg,rgba(0,224,198,.35),rgba(91,140,255,.18),transparent)',
          opacity: 0.5,
          filter: 'blur(2px)',
        }}
      />
      <div
        style={{
          position: 'relative',
          display: 'flex',
          alignItems: 'center',
          gap: 13,
          padding: '11px 11px 11px 16px',
          background: 'rgba(10,16,26,.86)',
          border: '1px solid rgba(255,255,255,.1)',
          borderRadius: 15,
          backdropFilter: 'blur(10px)',
        }}
      >
        <div style={{ animation: 'coreP 2.4s ease-in-out infinite' }}>
          <LogoMark size={26} glow={false} style={{ filter: 'drop-shadow(0 0 8px rgba(0,224,198,.6))' }} />
        </div>
        <input
          ref={inputRef}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') onSubmit()
          }}
          placeholder={placeholder}
          style={{ flex: 1, background: 'transparent', border: 'none', outline: 'none', color: '#eaf2f0', fontSize: 15.5, letterSpacing: '.01em' }}
        />
        <button
          onClick={onSubmit}
          onMouseOver={(e) => {
            e.currentTarget.style.transform = 'translateY(-1px)'
            e.currentTarget.style.boxShadow = '0 0 26px rgba(0,224,198,.55)'
          }}
          onMouseOut={(e) => {
            e.currentTarget.style.transform = 'none'
            e.currentTarget.style.boxShadow = '0 0 18px rgba(0,224,198,.3)'
          }}
          style={{
            flex: 'none',
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
            transition: 'transform .15s,box-shadow .2s',
            boxShadow: '0 0 18px rgba(0,224,198,.3)',
          }}
        >
          Ask<span>↵</span>
        </button>
      </div>
    </div>
  )
}

function PredictedChampionCard({ champions, modelVersion }) {
  const p = useTween(1300)
  const maxV = Math.max(...champions.map((c) => c.v), 0.001)
  return (
    <div
      style={{
        padding: 20,
        background: 'linear-gradient(180deg,rgba(255,255,255,.05),rgba(255,255,255,.012))',
        border: '1px solid rgba(255,255,255,.1)',
        borderRadius: 16,
        boxShadow: 'inset 0 1px 0 rgba(255,255,255,.08),0 0 0 1px rgba(0,0,0,.3)',
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 1, background: 'linear-gradient(90deg,transparent,rgba(0,224,198,.5),transparent)' }} />
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
        <span style={mono({ fontSize: 11, letterSpacing: '.2em', color: 'var(--text-secondary-2)' })}>PREDICTED CHAMPION</span>
        <span style={mono({ fontSize: 9.5, letterSpacing: '.1em', color: '#4f6075' })}>MODEL {modelVersion || 'v2.6'}</span>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 13 }}>
        {champions.map((c, i) => (
          <div key={c.code}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
                <Flag code={c.code} color={c.color} height={11} />
                <span style={mono({ fontSize: 12, letterSpacing: '.08em', color: '#cdd8e4' })}>{c.code}</span>
                <span style={{ fontSize: 12.5, color: '#7c8b9c' }}>{c.name}</span>
              </div>
              <span style={mono({ fontSize: 13, fontWeight: 500, color: '#eaf2f0' })}>{(c.v * p).toFixed(1)}%</span>
            </div>
            <div style={{ height: 8, borderRadius: 4, background: 'rgba(255,255,255,.06)', overflow: 'hidden', position: 'relative' }}>
              <div
                style={{
                  height: '100%',
                  borderRadius: 4,
                  width: `${((c.v / maxV) * 100 * p).toFixed(1)}%`,
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
                    animation: `barshine 2.8s ease-in-out infinite ${i * 0.4}s`,
                  }}
                />
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function NextMatchCard({ nextMatch, pred, goBracket }) {
  const nm = nextMatch
  if (!nm) return null
  return (
    <div
      style={{
        padding: '16px 18px',
        background: 'linear-gradient(135deg,rgba(0,224,198,.09),rgba(0,224,198,.02))',
        border: '1px solid rgba(0,224,198,.3)',
        borderRadius: 16,
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 1, background: 'linear-gradient(90deg,transparent,rgba(0,224,198,.6),transparent)' }} />
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <span style={mono({ fontSize: 10.5, letterSpacing: '.16em', color: 'var(--teal)' })}>NEXT MATCH</span>
        <span style={mono({ fontSize: 9, letterSpacing: '.08em', color: 'var(--text-muted)' })}>{nm.round}</span>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
        <Flag code={nm.home.code} color={nm.home.color} height={12} glow />
        <span style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-brightest)' }}>{nm.home.name}</span>
      </div>
      <div style={mono({ fontSize: 9.5, color: 'var(--text-dim)', margin: '4px 0 4px 17px' })}>vs</div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
        <Flag code={nm.away.code} color={nm.away.color} height={12} glow />
        <span style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-brightest)' }}>{nm.away.name}</span>
      </div>
      <div style={mono({ marginTop: 12, fontSize: 10, color: 'var(--text-secondary-2)' })}>
        {nm.date} · {nm.time}
      </div>
      <div style={mono({ marginTop: 2, fontSize: 10, color: 'var(--text-dim-2)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' })}>
        {nm.venue}
      </div>
      <div style={{ marginTop: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={mono({ fontSize: 9, letterSpacing: '.06em', color: 'var(--text-muted)', flex: 'none' })}>PICK</span>
        <div style={{ flex: 1, height: 5, borderRadius: 3, background: 'rgba(255,255,255,.07)', overflow: 'hidden' }}>
          <div style={{ height: '100%', width: `${nm.prob}%`, background: `linear-gradient(90deg,${nm.favCode === nm.home.code ? nm.home.color : nm.away.color},#00e0c6)`, borderRadius: 3 }} />
        </div>
        <span style={mono({ fontSize: 11, fontWeight: 700, color: 'var(--teal)', flex: 'none' })}>
          {nm.favCode} {nm.prob}%
        </span>
      </div>
      {pred && (
        <div style={{ marginTop: 14, paddingTop: 12, borderTop: '1px solid rgba(255,255,255,.08)' }}>
          <div style={{ display: 'flex', height: 6, borderRadius: 3, overflow: 'hidden', gap: 1 }}>
            <div style={{ width: `${pred.result.home}%`, background: nm.home.color }} title={`${nm.home.name} ${pred.result.home}%`} />
            <div style={{ width: `${pred.result.draw}%`, background: 'rgba(255,255,255,.22)' }} title={`Draw ${pred.result.draw}%`} />
            <div style={{ width: `${pred.result.away}%`, background: nm.away.color }} title={`${nm.away.name} ${pred.result.away}%`} />
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 5 }}>
            <span style={mono({ fontSize: 9, color: 'var(--text-dim-2)' })}>{nm.home.code} {pred.result.home}%</span>
            <span style={mono({ fontSize: 9, color: 'var(--text-dim-2)' })}>DRAW {pred.result.draw}%</span>
            <span style={mono({ fontSize: 9, color: 'var(--text-dim-2)' })}>{nm.away.code} {pred.result.away}%</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 10 }}>
            <span style={mono({ fontSize: 9.5, color: 'var(--text-muted)' })}>
              xG <span style={{ color: 'var(--text-secondary)' }}>{pred.xg[0].toFixed(1)}–{pred.xg[1].toFixed(1)}</span>
            </span>
            {pred.topScores?.[0] && (
              <span style={mono({ fontSize: 9.5, color: 'var(--text-muted)' })}>
                LIKELY <span style={{ color: 'var(--text-secondary)' }}>{pred.topScores[0].score[0]}–{pred.topScores[0].score[1]}</span>
              </span>
            )}
            <span style={mono({ fontSize: 9.5, color: 'var(--text-muted)' })}>
              O2.5 <span style={{ color: 'var(--text-secondary)' }}>{pred.totals?.o25}%</span>
            </span>
          </div>
        </div>
      )}
      <button
        onClick={goBracket}
        style={mono({ marginTop: 12, background: 'transparent', border: 'none', padding: 0, color: 'var(--teal)', fontSize: 10, cursor: 'pointer' })}
      >
        FULL BRACKET →
      </button>
    </div>
  )
}

function LastResultCard({ lastMatch, goFixtures }) {
  const lm = lastMatch
  if (!lm) return null
  const row = (team, score) => (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
        <Flag code={team.code} color={team.color} height={11} />
        <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-body)' }}>{team.name}</span>
      </div>
      <span style={mono({ fontSize: 15, fontWeight: 700, color: '#fff' })}>{score}</span>
    </div>
  )
  return (
    <div
      style={{
        padding: '16px 18px',
        background: 'linear-gradient(180deg,rgba(255,255,255,.04),rgba(255,255,255,.01))',
        border: '1px solid rgba(255,255,255,.09)',
        borderRadius: 16,
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 1, background: 'linear-gradient(90deg,transparent,rgba(255,255,255,.18),transparent)' }} />
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <span style={mono({ fontSize: 10.5, letterSpacing: '.16em', color: 'var(--text-secondary-2)' })}>LAST RESULT</span>
        <span style={mono({ fontSize: 9, letterSpacing: '.08em', color: 'var(--text-muted)' })}>{lm.round} · FT</span>
      </div>
      {row(lm.home, lm.sh)}
      <div style={{ marginTop: 6 }}>{row(lm.away, lm.sa)}</div>
      <div style={mono({ marginTop: 12, fontSize: 10, color: 'var(--text-muted)' })}>
        {lm.date} · {lm.venue}
      </div>
      <div style={{ marginTop: 6, fontSize: 11.5, color: 'var(--text-secondary)', lineHeight: 1.4 }}>{lm.scorers}</div>
      <button
        onClick={goFixtures}
        style={mono({ marginTop: 12, background: 'transparent', border: 'none', padding: 0, color: '#9fb0c2', fontSize: 10, cursor: 'pointer' })}
      >
        ALL FIXTURES →
      </button>
    </div>
  )
}

export default function Overview({ chat, setView }) {
  const { query, setQuery, messages, pending, ask } = chat
  const { data } = useData()
  const [ph, setPh] = useState(0)
  useEffect(() => {
    const t = setInterval(() => setPh((x) => (x + 1) % SUGGESTIONS.length), 3000)
    return () => clearInterval(t)
  }, [])
  const pred = data?.predictions
  const nextMatchPred = pred?.nextMatch
    ? (data?.matchpreds || []).find(
        (p) => p.home.code === pred.nextMatch.home.code && p.away.code === pred.nextMatch.away.code,
      )
    : null

  return (
    <div>
      <main className="pk-hero" style={{ display: 'grid', gridTemplateColumns: '1.32fr .92fr', gap: 34, alignItems: 'start', marginTop: 46 }}>
        {/* left: AI panel */}
        <section>
          <div style={mono({ fontSize: 11, letterSpacing: '.26em', color: 'var(--text-muted-2)' })}>
            FIFA WORLD CUP 2026 — USA · CANADA · MÉXICO
          </div>
          <h1 style={{ fontSize: 58, lineHeight: 1.02, fontWeight: 700, letterSpacing: '-.025em', margin: '18px 0 0', maxWidth: '15ch' }}>
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

          <QueryBar query={query} setQuery={setQuery} onSubmit={() => ask(query)} placeholder={'Ask Parker:  ' + SUGGESTIONS[ph]} />

          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 9, marginTop: 14 }}>
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                onClick={() => ask(s)}
                onMouseOver={(e) => {
                  e.currentTarget.style.borderColor = 'rgba(0,224,198,.5)'
                  e.currentTarget.style.color = '#cdeee8'
                  e.currentTarget.style.background = 'rgba(0,224,198,.07)'
                }}
                onMouseOut={(e) => {
                  e.currentTarget.style.borderColor = 'rgba(255,255,255,.1)'
                  e.currentTarget.style.color = '#9fb0c2'
                  e.currentTarget.style.background = 'rgba(255,255,255,.02)'
                }}
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
                  transition: 'border-color .18s,color .18s,background .18s',
                }}
              >
                {s}
              </button>
            ))}
          </div>

          {(messages.length > 0 || pending) && (
            <ChatMessages messages={messages} pending={pending} style={{ marginTop: 22, maxHeight: 240 }} />
          )}
        </section>

        {/* right: predictions sidebar */}
        <aside style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
          {pred && <PredictedChampionCard champions={pred.champions} modelVersion={pred.modelVersion} />}
          <NextMatchCard nextMatch={pred?.nextMatch} pred={nextMatchPred} goBracket={() => setView('bracket')} />
          <LastResultCard lastMatch={pred?.lastMatch} goFixtures={() => setView('fixtures')} />
        </aside>
      </main>

      {/* embedded bracket summary */}
      <section style={{ marginTop: 30 }}>
        <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', marginBottom: 16 }}>
          <div>
            <span style={mono({ fontSize: 11, letterSpacing: '.24em', color: 'var(--text-muted-2)' })}>BRACKET</span>
            <div style={{ fontSize: 20, fontWeight: 700, letterSpacing: '-.01em', marginTop: 6 }}>
              Knockout stage · Parker's projected path to the final
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
            <BracketLegend />
            <button
              onClick={() => setView('bracket')}
              style={mono({ background: 'transparent', border: 'none', padding: 0, color: 'var(--teal)', fontSize: 10.5, cursor: 'pointer', whiteSpace: 'nowrap' })}
            >
              FULL VIEW →
            </button>
          </div>
        </div>
        <BracketGrid />
      </section>
    </div>
  )
}
