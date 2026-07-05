import { flagUrl } from '../data/flags.js'

/*
  Replaces the old hashed-colour team swatch with the real national flag
  (via flagcdn.com, keyed off web/src/data/flags.js). `color` is kept as an
  optional prop purely for the glow shadow and as a graceful fallback swatch
  if a code has no flag mapping — so nothing breaks if the team list changes.
*/
export default function Flag({ code, color, height = 10, radius = 2, glow = false, style }) {
  const url = flagUrl(code)
  const shadow = glow && color ? `0 0 6px ${color}` : undefined
  if (!url) {
    return (
      <span
        style={{ width: height, height, borderRadius: radius, background: color || '#3d4f60', flex: 'none', boxShadow: shadow, ...style }}
      />
    )
  }
  return (
    <img
      src={url}
      alt={code}
      style={{ height, width: 'auto', borderRadius: radius, flex: 'none', display: 'block', boxShadow: shadow, ...style }}
    />
  )
}
