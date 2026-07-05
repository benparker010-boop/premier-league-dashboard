import { useEffect, useRef } from 'react'

/*
  Fixed full-viewport background stack, in z-order per the spec:
    1. canvas particle field (~70 teal dots, linked < 118px) — respects reduced motion
    2. radial accent glows
    3. faint grid texture (1px lines every 54px)
    4. very faint (≈6%) football pitch line-drawing, teal stroke
*/

function prefersReducedMotion() {
  return (
    typeof window !== 'undefined' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches
  )
}

export default function Background({ particleCount = 70 }) {
  const canvasRef = useRef(null)

  useEffect(() => {
    const cv = canvasRef.current
    if (!cv) return
    const motion = !prefersReducedMotion()
    const ctx = cv.getContext('2d')
    let w, h, dpr
    let raf = null
    const resize = () => {
      dpr = Math.min(2, window.devicePixelRatio || 1)
      w = cv.clientWidth
      h = cv.clientHeight
      cv.width = w * dpr
      cv.height = h * dpr
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    }
    window.addEventListener('resize', resize)
    resize()
    const pts = Array.from({ length: particleCount }, () => ({
      x: Math.random() * w,
      y: Math.random() * h,
      vx: (Math.random() - 0.5) * 0.22,
      vy: (Math.random() - 0.5) * 0.22,
    }))
    const draw = () => {
      ctx.clearRect(0, 0, w, h)
      for (const p of pts) {
        if (motion) {
          p.x += p.vx
          p.y += p.vy
          if (p.x < 0 || p.x > w) p.vx *= -1
          if (p.y < 0 || p.y > h) p.vy *= -1
        }
      }
      for (let i = 0; i < pts.length; i++) {
        for (let j = i + 1; j < pts.length; j++) {
          const a = pts[i]
          const b = pts[j]
          const dx = a.x - b.x
          const dy = a.y - b.y
          const d = Math.hypot(dx, dy)
          if (d < 118) {
            ctx.strokeStyle = 'rgba(0,224,198,' + 0.1 * (1 - d / 118) + ')'
            ctx.lineWidth = 1
            ctx.beginPath()
            ctx.moveTo(a.x, a.y)
            ctx.lineTo(b.x, b.y)
            ctx.stroke()
          }
        }
      }
      for (const p of pts) {
        ctx.fillStyle = 'rgba(120,200,220,.5)'
        ctx.beginPath()
        ctx.arc(p.x, p.y, 1.3, 0, 7)
        ctx.fill()
      }
      if (motion) raf = requestAnimationFrame(draw)
    }
    draw()
    return () => {
      window.removeEventListener('resize', resize)
      if (raf) cancelAnimationFrame(raf)
    }
  }, [particleCount])

  return (
    <>
      <canvas
        ref={canvasRef}
        style={{ position: 'fixed', inset: 0, width: '100%', height: '100%', zIndex: 0, opacity: 0.7 }}
      />
      <div
        style={{
          position: 'fixed',
          inset: 0,
          zIndex: 0,
          pointerEvents: 'none',
          background:
            'radial-gradient(1100px 700px at 22% 8%,rgba(0,224,198,.10),transparent 60%),radial-gradient(900px 600px at 88% 90%,rgba(91,140,255,.08),transparent 55%)',
        }}
      />
      <div
        style={{
          position: 'fixed',
          inset: 0,
          zIndex: 0,
          pointerEvents: 'none',
          opacity: 0.4,
          backgroundImage:
            'linear-gradient(rgba(255,255,255,.025) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.025) 1px,transparent 1px)',
          backgroundSize: '54px 54px',
          WebkitMaskImage: 'radial-gradient(circle at 50% 30%,#000,transparent 75%)',
          maskImage: 'radial-gradient(circle at 50% 30%,#000,transparent 75%)',
        }}
      />
      <div
        style={{
          position: 'fixed',
          inset: 0,
          zIndex: 0,
          pointerEvents: 'none',
          display: 'grid',
          placeItems: 'center',
          opacity: 0.06,
          overflow: 'hidden',
        }}
      >
        <svg width="860" height="860" viewBox="0 0 860 860" fill="none" stroke="#00e0c6" strokeWidth="1.3">
          <line x1="60" y1="430" x2="800" y2="430" />
          <circle cx="430" cy="430" r="130" />
          <circle cx="430" cy="430" r="5" fill="#00e0c6" stroke="none" />
          <rect x="270" y="60" width="320" height="130" />
          <rect x="345" y="60" width="170" height="60" />
          <path d="M345 190 A 95 95 0 0 0 515 190" />
          <rect x="270" y="670" width="320" height="130" />
          <rect x="345" y="740" width="170" height="60" />
          <path d="M345 670 A 95 95 0 0 1 515 670" />
        </svg>
      </div>
    </>
  )
}
