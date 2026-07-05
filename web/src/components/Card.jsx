/*
  Card treatment per spec:
  - gradient background, 1px white border at 9% alpha, 14–16px radius
  - a 1px top "hairline" accent (teal by default, gold for special cards)
*/
export default function Card({ gold = false, style, children, ...rest }) {
  return (
    <div
      style={{
        position: 'relative',
        overflow: 'hidden',
        background: gold
          ? 'linear-gradient(135deg,rgba(245,196,81,.1),rgba(245,196,81,.03))'
          : 'var(--card-bg)',
        border: gold ? '1px solid rgba(245,196,81,.28)' : 'var(--card-border)',
        borderRadius: 'var(--card-radius)',
        ...style,
      }}
      {...rest}
    >
      <div
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          height: 1,
          background: gold ? 'var(--hairline-gold)' : 'var(--hairline-teal)',
        }}
      />
      {children}
    </div>
  )
}
