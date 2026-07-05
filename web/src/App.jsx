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
import { useData } from './data/DataContext.jsx'

/* Phase 3 stand-in answer — replaced by the real LLM endpoint in Phase 5. */
const FALLBACK =
  "Parker's live engine comes online in a later phase — but the model currently has France as the clear title favourite, with Spain, Morocco and Argentina its next-most-likely champions."

/* Build the Match Lab context string that silently enriches the AI prompt when
   a match is open. Consumed by the real LLM route in Phase 5. */
function matchContext(m) {
  if (!m) return ''
  const s = m.stats || {}
  const p = (k) => (s[k] || [null, null])
  const scorers = (m.timeline || []).filter((e) => e.type === 'g').map((e) => `${e.player} ${e.min}'`).join(', ')
  return (
    `\n\nThe user is currently viewing this match in Match Lab — ground answers about 'this match/game' in it: ` +
    `${m.home.name} ${m.score[0]}-${m.score[1]} ${m.away.name} (${m.round}, ${m.date}). ` +
    `Possession ${p('possession')[0]}%-${p('possession')[1]}%, xG ${p('xg')[0]}-${p('xg')[1]}, ` +
    `shots ${p('shots')[0]}-${p('shots')[1]} (on target ${p('sot')[0]}-${p('sot')[1]}). Scorers: ${scorers}.`
  )
}

export default function App() {
  const { data } = useData()
  // landing view is Bracket per latest direction (Overview stays a nav item)
  const [view, setView] = useState('bracket')
  const [match, setMatch] = useState(null)
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
    const curMatch = (data?.matches || []).find((x) => x.id === matchRef.current) || (data?.matches || [])[0]
    const context = viewRef.current === 'matchlab' ? matchContext(curMatch) : ''
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
