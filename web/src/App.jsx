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

/* Shown only if the Ask Parker route is unreachable (e.g. no API key set). */
const FALLBACK =
  "Parker's live engine isn't reachable right now — but the model has France as the clear title favourite, with Spain, Morocco and Argentina its next most-likely champions."

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

  const ask = async (text) => {
    const q = (text || '').trim()
    if (!q || pending) return
    const history = [...messages, { role: 'user', content: q }]
    setMessages((s) => [...s, { role: 'user', content: q, id: 'u' + Date.now() }])
    setQuery('')
    setPending(true)
    // The route builds the grounded prompt server-side from our real prediction
    // data + (in Match Lab) the open match; the API key never touches the client.
    try {
      const r = await fetch('/api/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: history.map((m) => ({ role: m.role, content: m.content })),
          view: viewRef.current,
          matchId: matchRef.current,
        }),
      })
      const data = await r.json()
      setPending(false)
      typeOut(data.text || FALLBACK)
    } catch (e) {
      setPending(false)
      typeOut(FALLBACK)
    }
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
      <div className="pk-shell" style={{ position: 'relative', zIndex: 2, maxWidth: 1280, margin: '0 auto', padding: '26px 32px 0' }}>
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
