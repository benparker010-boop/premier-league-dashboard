import { useEffect, useRef, useState } from 'react'
import LogoMark from './LogoMark.jsx'

/*
  Session-gated boot intro (first visit per browser tab only).
  Full-screen black overlay: live particle/constellation field, orbital rings +
  a centered transparent "P" glyph, the two eyebrow lines, and a scan line.
  On the user's first mousemove/click the logo brightens, a radial flash wipes
  the screen, and the whole scene scales up + fades (~0.9s), revealing the app.
  A 6-second fallback auto-triggers the same transition. Backed by
  sessionStorage `parker_seen` so it plays once per tab.
*/

function reduceMotion() {
  return typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

export default function BootIntro({ onDone }) {
  const wrapRef = useRef(null)
  const sceneRef = useRef(null)
  const logoRef = useRef(null)
  const flashRef = useRef(null)
  const particlesRef = useRef(null)
  const [leaving, setLeaving] = useState(false)

  // particle constellation field
  useEffect(() => {
    const cvs = particlesRef.current
    if (!cvs) return
    const motion = !reduceMotion()
    const resize = () => {
      cvs.width = cvs.offsetWidth
      cvs.height = cvs.offsetHeight
    }
    resize()
    window.addEventListener('resize', resize)
    const ctx = cvs.getContext('2d')
    const N = 90
    const pts = Array.from({ length: N }, () => ({
      x: Math.random(),
      y: Math.random(),
      vx: (Math.random() - 0.5) * 0.0003,
      vy: (Math.random() - 0.5) * 0.0003,
      r: Math.random() * 1.8 + 0.6,
      c: Math.random() < 0.12 ? 'rgba(180,120,255,' : 'rgba(0,224,198,',
    }))
    let raf = null
    let stopped = false
    const tick = () => {
      if (stopped) return
      const W = cvs.width
      const H = cvs.height
      ctx.clearRect(0, 0, W, H)
      if (motion) pts.forEach((p) => { p.x = (p.x + p.vx + 1) % 1; p.y = (p.y + p.vy + 1) % 1 })
      for (let i = 0; i < N; i++) {
        for (let j = i + 1; j < N; j++) {
          const dx = (pts[i].x - pts[j].x) * W
          const dy = (pts[i].y - pts[j].y) * H
          const d = Math.sqrt(dx * dx + dy * dy)
          if (d < 120) {
            ctx.beginPath()
            ctx.moveTo(pts[i].x * W, pts[i].y * H)
            ctx.lineTo(pts[j].x * W, pts[j].y * H)
            ctx.strokeStyle = `rgba(0,224,198,${(0.18 * (1 - d / 120)).toFixed(3)})`
            ctx.lineWidth = 0.7
            ctx.stroke()
          }
        }
      }
      pts.forEach((p) => {
        ctx.beginPath()
        ctx.arc(p.x * W, p.y * H, p.r, 0, Math.PI * 2)
        ctx.fillStyle = p.c + '.7)'
        ctx.shadowBlur = 8
        ctx.shadowColor = p.c + '1)'
        ctx.fill()
        ctx.shadowBlur = 0
      })
      if (motion) raf = requestAnimationFrame(tick)
    }
    tick()
    return () => {
      stopped = true
      window.removeEventListener('resize', resize)
      if (raf) cancelAnimationFrame(raf)
    }
  }, [])

  // 6-second fallback so nobody gets stuck
  useEffect(() => {
    const t = setTimeout(() => go(), 6000)
    return () => clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const go = () => {
    if (leaving) return
    setLeaving(true)
    const wrap = wrapRef.current
    const scene = sceneRef.current
    const logo = logoRef.current
    const flash = flashRef.current
    if (wrap) wrap.style.pointerEvents = 'none'
    if (logo) {
      logo.style.transform = 'scale(1.1)'
      logo.style.filter = 'drop-shadow(0 0 60px rgba(0,224,198,.95)) drop-shadow(0 0 120px rgba(0,224,198,.5))'
    }
    setTimeout(() => {
      if (flash) flash.style.animation = 'flashpop .55s ease forwards'
      if (scene) {
        scene.style.transform = 'scale(1.15)'
        scene.style.opacity = '0'
      }
    }, 180)
    setTimeout(() => {
      try {
        sessionStorage.setItem('parker_seen', '1')
      } catch (e) {
        /* ignore */
      }
      onDone()
    }, 900)
  }

  return (
    <div
      ref={wrapRef}
      onMouseMove={go}
      onClick={go}
      style={{ position: 'fixed', inset: 0, zIndex: 60, pointerEvents: 'auto', overflow: 'hidden', background: '#000' }}
    >
      <div
        ref={sceneRef}
        style={{
          position: 'absolute',
          inset: 0,
          transition: 'transform .7s cubic-bezier(.7,0,.3,1),opacity .7s ease',
          transform: 'scale(1)',
          opacity: 1,
        }}
      >
        <div style={{ position: 'absolute', inset: 0, background: 'radial-gradient(ellipse 80% 60% at 50% 42%,rgba(0,20,18,0) 0%,transparent 72%)' }} />
        <canvas ref={particlesRef} style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none' }} />
        <div
          style={{
            position: 'absolute',
            left: 0,
            right: 0,
            top: 0,
            height: 3,
            background: 'linear-gradient(90deg,transparent,rgba(0,224,198,.9),rgba(180,120,255,.7),transparent)',
            boxShadow: '0 0 22px 6px rgba(0,224,198,.5)',
            animation: 'scandown 3.6s linear infinite',
          }}
        />

        <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 0 }}>
          <div style={{ position: 'relative', display: 'grid', placeItems: 'center' }}>
            {/* radial glow */}
            <div
              style={{
                position: 'absolute',
                width: 480,
                height: 480,
                borderRadius: '50%',
                background: 'radial-gradient(circle,rgba(0,224,198,.15) 0%,rgba(120,80,220,.09) 50%,transparent 72%)',
                animation: 'coreP 3.5s ease-in-out infinite',
              }}
            />
            {/* orbital rings */}
            <div style={{ position: 'absolute', width: 300, height: 300, border: '1px solid rgba(0,224,198,.25)', borderTopColor: 'transparent', borderRadius: '50%', animation: 'ringspin 8s linear infinite' }} />
            <div style={{ position: 'absolute', width: 380, height: 380, border: '1px solid rgba(0,224,198,.16)', borderRightColor: 'transparent', borderRadius: '50%', animation: 'ringspin2 12s linear infinite' }} />
            <div style={{ position: 'absolute', width: 460, height: 460, border: '1px solid rgba(180,120,255,.12)', borderBottomColor: 'transparent', borderRadius: '50%', animation: 'ringspin 18s linear infinite' }} />
            {/* logo — P glyph only, floating */}
            <div ref={logoRef} style={{ animation: 'robotbob 5s ease-in-out infinite', transition: 'transform .3s ease,filter .3s ease', filter: 'drop-shadow(0 0 36px rgba(0,224,198,.7)) drop-shadow(0 0 80px rgba(0,224,198,.3))' }}>
              <LogoMark size={230} glow={false} />
            </div>
          </div>
          <div style={{ marginTop: 28, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 10 }}>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12, letterSpacing: '.38em', color: 'var(--teal)', animation: 'hzpulse 3s ease-in-out infinite' }}>
              WORLD CUP 2026 &nbsp;·&nbsp; AI ANALYTICS
            </div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, letterSpacing: '.22em', color: 'rgba(255,255,255,.28)', animation: 'hzpulse 4.2s ease-in-out infinite .8s' }}>
              MOVE CURSOR OR CLICK TO ENTER
            </div>
          </div>
        </div>

        <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none', boxShadow: 'inset 0 0 180px 40px rgba(0,0,0,.65)' }} />
      </div>

      <div ref={flashRef} style={{ position: 'absolute', inset: 0, pointerEvents: 'none', opacity: 0, background: 'radial-gradient(circle at 50% 44%,rgba(220,255,250,.98),rgba(0,224,198,.6) 28%,transparent 65%)' }} />
    </div>
  )
}
