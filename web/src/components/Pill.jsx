/*
  Rounded-full pill button per spec. Active state: teal gradient fill,
  teal border, soft outer glow, text brightens + weight 600.
*/
export default function Pill({ active = false, mono = false, style, children, ...rest }) {
  return (
    <button
      style={{
        position: 'relative',
        padding: '8px 18px',
        border: 'none',
        borderRadius: 100,
        background: 'transparent',
        color: active ? 'var(--text-brightest)' : 'var(--text-secondary)',
        fontFamily: mono ? 'var(--font-mono)' : 'var(--font-display)',
        fontSize: mono ? 11 : 13,
        fontWeight: active ? 600 : mono ? 400 : 500,
        letterSpacing: mono ? '.06em' : undefined,
        cursor: 'pointer',
        transition: 'color .18s',
        ...style,
      }}
      {...rest}
    >
      {active && (
        <span
          style={{
            position: 'absolute',
            inset: 0,
            borderRadius: 100,
            background: 'var(--pill-active-bg)',
            border: 'var(--pill-active-border)',
            boxShadow: 'var(--pill-active-glow)',
          }}
        />
      )}
      <span style={{ position: 'relative' }}>{children}</span>
    </button>
  )
}
