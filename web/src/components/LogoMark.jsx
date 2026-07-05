/*
  The PARKER logo cropped to only the "P" glyph (per the spec's Assets section
  the full wordmark is never shown in the live UI). The source PNG is square:
  the glyph sits in a box roughly x 30%–77%, y 12%–75% of the image, so we
  scale the image up inside an overflow-hidden square and offset it.
*/
export default function LogoMark({ size = 44, glow = true, style }) {
  const img = size / 0.63
  return (
    <div
      style={{
        width: size,
        height: size,
        overflow: 'hidden',
        position: 'relative',
        flex: 'none',
        ...style,
      }}
    >
      <img
        src="/parker-logo-transparent.png"
        alt="PARKER"
        style={{
          position: 'absolute',
          width: img,
          height: img,
          left: -img * 0.221,
          top: -img * 0.12,
          objectFit: 'contain',
          filter: glow ? 'drop-shadow(0 0 10px rgba(0,224,198,.6))' : undefined,
        }}
      />
    </div>
  )
}
