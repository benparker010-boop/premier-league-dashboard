import ChatMessages from './ChatMessages.jsx'

/*
  Persistent Ask Parker bar docked to the bottom of the viewport on every view
  except Overview (which has its own hero input). Above it, an expanded chat
  transcript when there are messages. Context-aware placeholder: names "this
  match" in Match Lab, "the tournament" elsewhere.
*/
export default function DockedParker({ chat, contextLabel = 'the tournament' }) {
  const { query, setQuery, messages, pending, ask } = chat
  return (
    <div style={{ position: 'fixed', left: 0, right: 0, bottom: 0, zIndex: 6, display: 'flex', justifyContent: 'center', pointerEvents: 'none', padding: '0 32px 18px' }}>
      <div style={{ width: '100%', maxWidth: 1280, pointerEvents: 'auto' }}>
        {(messages.length > 0 || pending) && (
          <ChatMessages
            messages={messages}
            pending={pending}
            style={{ maxHeight: 230, marginBottom: 10, background: 'rgba(8,13,22,.92)', border: '1px solid rgba(255,255,255,.1)', backdropFilter: 'blur(12px)' }}
          />
        )}
        <div style={{ position: 'relative' }}>
          <div style={{ position: 'absolute', inset: -1, borderRadius: 15, background: 'linear-gradient(120deg,rgba(0,224,198,.3),rgba(91,140,255,.16),transparent)', opacity: 0.5, filter: 'blur(2px)' }} />
          <div style={{ position: 'relative', display: 'flex', alignItems: 'center', gap: 12, padding: '9px 9px 9px 15px', background: 'rgba(10,16,26,.95)', border: '1px solid rgba(255,255,255,.12)', borderRadius: 14, backdropFilter: 'blur(12px)' }}>
            <div style={{ position: 'relative', width: 24, height: 24, display: 'grid', placeItems: 'center', flex: 'none' }}>
              <div style={{ position: 'absolute', inset: 0, border: '1px solid rgba(0,224,198,.4)', borderRightColor: 'transparent', borderRadius: '50%', animation: 'ringspin 4s linear infinite' }} />
              <div style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--teal)', boxShadow: '0 0 11px #00e0c6', animation: 'coreP 2.4s ease-in-out infinite' }} />
            </div>
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') ask(query)
              }}
              placeholder={`Ask Parker about ${contextLabel}…`}
              style={{ flex: 1, background: 'transparent', border: 'none', outline: 'none', color: '#eaf2f0', fontSize: 15 }}
            />
            <button
              onClick={() => ask(query)}
              onMouseOver={(e) => {
                e.currentTarget.style.boxShadow = '0 0 26px rgba(0,224,198,.55)'
              }}
              onMouseOut={(e) => {
                e.currentTarget.style.boxShadow = '0 0 18px rgba(0,224,198,.3)'
              }}
              style={{ flex: 'none', display: 'flex', alignItems: 'center', gap: 6, padding: '8px 15px', border: 'none', borderRadius: 10, background: 'var(--teal)', color: '#04211d', fontFamily: 'var(--font-display)', fontSize: 13, fontWeight: 600, cursor: 'pointer', boxShadow: '0 0 18px rgba(0,224,198,.3)' }}
            >
              Ask<span>↵</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
