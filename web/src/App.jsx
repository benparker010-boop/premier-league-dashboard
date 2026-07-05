import { useRef, useState } from 'react'
import Background from './components/Background.jsx'
import Header from './components/Header.jsx'
import Ticker from './components/Ticker.jsx'
import BootIntro from './components/BootIntro.jsx'
import DockedParker from './components/DockedParker.jsx'
import Overview from './views/Overview.jsx'
import BracketView from './views/BracketView.jsx'
import Groups from './views/Groups.jsx'
import Fixtures from './views/Fixtures.jsx'
import MatchLab from './views/MatchLab.jsx'
import Players from './views/Players.jsx'
import { MATCHES, TEAMS } from './data/wcdata.js'

/* Phase 3 stand-in answer — replaced by the real LLM endpoint in Phase 5. */
const FALLBACK =
  "Parker's live engine comes online in a later phase, but the model has France leading the title race at 18.4%, with Argentina (16.1%) and England (13.7%) just behind."

/* Build the Match Lab context string that silently enriches the AI prompt when
   a match is open. Wired now; consumed by the real LLM route in Phase 5. */
function matchContext(matchId) {
  const m = MATCHES.find((x) => x.id === matchId)
  if (!m) return ''
  const h = TEAMS[m.home] || {}
  const a = TEAMS[m.away] || {}
  const s = m.stats
  const scorers = m.timeline.filter((e) => e.type === 'g').map((e) => `${e.player} ${e.min}'`).join(', ')
  return (
    `\n\nThe user is currently viewing this match in Match Lab — ground answers about 'this match/game' in it: ` +
    `${h.name} ${m.score[0]}-${m.score[1]} ${a.name} (${m.group}, ${m.date}). ` +
    `Possession ${s.possession[0]}%-${s.possession[1]}%, xG ${s.xg[0]}-${s.xg[1]}, shots ${s.shots[0]}-${s.shots[1]} ` +
    `(on target ${s.sot[0]}-${s.sot[1]}), big chances ${s.big[0]}-${s.big[1]}, corners ${s.corners[0]}-${s.corners[1]}, ` +
    `pass accuracy ${s.passAcc[0]}%-${s.passAcc[1]}%. Scorers: ${scorers}.`
  )
}

export default function App() {
  // landing view is Bracket per latest direction (Overview stays a nav item)
  const [view, setView] = useState('bracket')
  const [match, setMatch] = useState('esp-jpn')
  const [intro, setIntro] = useState(() => {
    try {
      return sessionStorage.getItem('parker_seen') ? 'done' : 'booting'
    } catch (e) {
      return 'booting'
    }
  })

  // Ask Parker chat state (shared by the Overview hero and the docked bar)
  const [query, setQuery] = useState('')
  const [messages, setMessages] = useState([])
  const [pending, setPending] = useState(false)
  const typer = useRef(null)
  // keep the latest view/match available to ask() without stale closures
  const viewRef = useRef(view)
  viewRef.current = view
  const matchRef = useRef(match)
  matchRef.current = match

  const typeOut = (full) => {
    const id = 'a' + Date.now()
    setMessages((s) => [...s, { role: 'assistant', content: '', id }])
    let i = 0
    clearInterval(typer.current)
    typer.current = setInterval(() => {
      i += 2
      setMessages((s) => s.map((m) => (m.id === id ? { ...m, content: full.slice(0, i) } : m)))
      if (i >= full.length) clearInterval(typer.current)
    }, 16)
  }

  const ask = (text) => {
    const q = (text || '').trim()
    if (!q || pending) return
    // context-aware enrichment (used by the real LLM in Phase 5)
    const context = viewRef.current === 'matchlab' ? matchContext(matchRef.current) : ''
    void context
    setMessages((s) => [...s, { role: 'user', content: q, id: 'u' + Date.now() }])
    setQuery('')
    setPending(true)
    setTimeout(() => {
      setPending(false)
      typeOut(FALLBACK)
    }, 900)
  }

  const chat = { query, setQuery, messages, pending, ask }

  const openMatchLab = (id) => {
    setMatch(id)
    setView('matchlab')
  }

  const contextLabel = view === 'matchlab' ? 'this match' : 'the tournament'

  return (
    <div style={{ position: 'relative', minHeight: '100vh', overflow: 'hidden', background: 'var(--bg)' }}>
      <Background />
      <div style={{ position: 'relative', zIndex: 2, maxWidth: 1280, margin: '0 auto', padding: '26px 32px 0' }}>
        <Header view={view} setView={setView} />
        {view === 'overview' && <Overview chat={chat} setView={setView} />}
        {view === 'bracket' && <BracketView />}
        {view === 'groups' && <Groups />}
        {view === 'fixtures' && <Fixtures openMatchLab={openMatchLab} goBracket={() => setView('bracket')} />}
        {view === 'matchlab' && <MatchLab match={match} setMatch={setMatch} />}
        {view === 'players' && <Players />}
      </div>
      <Ticker />
      {view !== 'overview' && <DockedParker chat={chat} contextLabel={contextLabel} />}
      {intro !== 'done' && <BootIntro onDone={() => setIntro('done')} />}
    </div>
  )
}
