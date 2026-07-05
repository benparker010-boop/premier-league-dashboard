import { useRef, useState } from 'react'
import Background from './components/Background.jsx'
import Header from './components/Header.jsx'
import Ticker from './components/Ticker.jsx'
import Overview from './views/Overview.jsx'
import BracketView from './views/BracketView.jsx'
import Groups from './views/Groups.jsx'
import Fixtures from './views/Fixtures.jsx'
import MatchLab from './views/MatchLab.jsx'
import Players from './views/Players.jsx'

/* Phase 2 stand-in answer — replaced by the real LLM endpoint in Phase 5. */
const FALLBACK =
  "Parker's live engine comes online in a later phase, but the model has France leading the title race at 18.4%, with Argentina (16.1%) and England (13.7%) just behind."

export default function App() {
  // landing view is Bracket per latest direction (Overview stays a nav item)
  const [view, setView] = useState('bracket')
  const [match, setMatch] = useState('esp-jpn')

  // Ask Parker chat state (shared with the docked bar in Phase 3)
  const [query, setQuery] = useState('')
  const [messages, setMessages] = useState([])
  const [pending, setPending] = useState(false)
  const typer = useRef(null)

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
    setMessages((s) => [...s, { role: 'user', content: q, id: 'u' + Date.now() }])
    setQuery('')
    setPending(true)
    // Phase 2: simulate the analysing state, then type the stand-in answer
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
    </div>
  )
}
