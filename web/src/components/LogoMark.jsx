import { useEffect, useRef } from 'react'

/*
  The animated PARKER "P" glyph — constellation mesh with a rotating football,
  travelling light pulses along the mesh edges, node shimmer and random edge
  flickers. Base art is `parker-logo-mesh.png` (640x640, includes the full
  glyph + ball + "PARKER" wordmark, background keyed to transparent); we crop to the
  glyph-only region the same way the old static PNG was cropped (the wordmark
  is never shown in the live UI — see design_handoff spec). The canvas overlay
  is sized/positioned identically to the base <img> so the two clip together
  inside the overflow-hidden box, keeping the node/edge coordinates (which are
  fractions of the *full* 640x640 image) perfectly aligned.

  Crop box (fraction of the full image): x 0.216–0.849, y 0.114–0.747 — a
  tighter crop than the original static PNG so the glyph fills more of the
  box. The background has been keyed out to real alpha transparency (the
  source webp had it baked onto near-black), so only the glyph/ball/mesh show
  — no background square behind the logo.
*/

const CROP_FRAC = 0.6332
const OFFSET_X_FRAC = 0.2162
const OFFSET_Y_FRAC = 0.1139

// Glow/pulse pixel sizes below were tuned for a ~440px render (the original
// standalone preview). Everything is scaled by W/REF_W so the glow doesn't
// overwhelm small renders (e.g. the 44px nav logo) or look too thin on big
// ones (e.g. the 230px boot intro).
const REF_W = 440

const ND = [[0.323,0.154,0.033,146,117,209],[0.5,0.148,0.016,72,213,164],[0.63,0.161,0.01,98,231,236],[0.389,0.197,0.01,59,205,146],[0.584,0.207,0.009,61,208,163],[0.719,0.223,0.01,102,220,186],[0.465,0.239,0.032,151,198,134],[0.672,0.24,0.01,56,207,152],[0.315,0.257,0.015,69,212,161],[0.626,0.279,0.006,117,236,209],[0.514,0.294,0.012,39,225,188],[0.464,0.31,0.006,107,245,219],[0.4,0.316,0.008,105,224,190],[0.752,0.33,0.013,59,208,161],[0.379,0.368,0.03,146,110,211],[0.664,0.356,0.012,62,209,152],[0.7,0.411,0.008,105,229,216],[0.314,0.429,0.012,81,215,168],[0.742,0.461,0.009,71,210,159],[0.625,0.463,0.01,63,206,147],[0.411,0.472,0.01,62,209,149],[0.673,0.509,0.028,160,196,127],[0.526,0.499,0.029,150,206,144],[0.688,0.526,0.02,171,194,117],[0.325,0.537,0.03,111,205,153],[0.581,0.541,0.027,132,151,209],[0.489,0.526,0.007,135,236,209],[0.637,0.563,0.01,94,220,172],[0.417,0.572,0.015,63,211,153],[0.524,0.571,0.005,127,237,214],[0.359,0.635,0.01,87,229,234],[0.417,0.666,0.006,121,238,219],[0.315,0.717,0.011,70,208,153],[0.416,0.719,0.006,115,236,215]]
const ED = [[0,3],[0,6],[1,3],[1,4],[1,6],[2,4],[2,7],[3,6],[3,8],[3,12],[4,6],[4,7],[4,9],[4,16],[5,7],[6,12],[7,9],[7,13],[7,15],[8,12],[8,14],[8,17],[9,16],[12,14],[13,15],[13,16],[14,17],[14,20],[15,16],[15,18],[16,18],[16,19],[16,21],[17,20],[18,21],[19,21],[19,23],[19,25],[19,26],[20,22],[20,24],[20,26],[20,28],[20,31],[21,23],[21,25],[21,27],[21,29],[22,25],[22,26],[22,28],[23,27],[25,26],[25,27],[25,29],[26,27],[26,28],[27,28],[27,29],[28,29],[28,30],[28,31],[28,33],[30,31],[30,32],[30,33],[31,32],[31,33],[32,33]]
const BX = 0.5346, BY = 0.3636, BR = 0.11

function reduceMotion() {
  return typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

function useLogoAnimation(canvasRef, imgRef, ballRef) {
  useEffect(() => {
    if (reduceMotion()) return undefined
    const cv = canvasRef.current
    const img = imgRef.current
    const ball = ballRef.current
    if (!cv || !img) return undefined
    const g = cv.getContext('2d')
    let W = 0, H = 0, T = 0, raf = null, stopped = false

    const nodes = ND.map((d) => {
      const m = 255 / Math.max(d[3], d[4], d[5])
      return {
        x: d[0], y: d[1], r: d[2],
        cr: Math.round(d[3] * m), cg: Math.round(d[4] * m), cb: Math.round(d[5] * m),
        ph: Math.random() * 7, sp: 0.4 + Math.random() * 0.7, heat: 0,
      }
    })
    const adj = {}
    ED.forEach(([a, b]) => { (adj[a] = adj[a] || []).push(b); (adj[b] = adj[b] || []).push(a) })
    function pickNext(cur, prev) {
      const ns = adj[cur] || []
      if (!ns.length) return null
      let c = ns[Math.floor(Math.random() * ns.length)]
      if (ns.length > 1 && c === prev) c = ns[(ns.indexOf(c) + 1) % ns.length]
      return c
    }
    const pulses = []
    function spawn() {
      const ks = Object.keys(adj)
      const s = +ks[Math.floor(Math.random() * ks.length)]
      const n = pickNext(s, -1)
      if (n === null) return
      pulses.push({ a: s, b: n, t: 0, sp: 0.01 + Math.random() * 0.01, hops: 3 + Math.floor(Math.random() * 5), trail: [] })
    }
    for (let i = 0; i < 5; i++) spawn()
    const flicks = []
    let nextFlick = 1.2

    function size() {
      const r = img.getBoundingClientRect()
      if (r.width < 10) return
      W = r.width; H = r.height
      cv.width = W * 2; cv.height = H * 2
      g.setTransform(2, 0, 0, 2, 0, 0)
    }
    if (img.complete) size()
    else img.addEventListener('load', size)
    const onResize = () => size()
    window.addEventListener('resize', onResize)

    function frame() {
      if (stopped) return
      T += 0.016
      if (W < 10) { size(); raf = requestAnimationFrame(frame); return }
      const s = W / REF_W
      g.clearRect(0, 0, W, H)
      if (ball && ball.complete && ball.naturalWidth) {
        g.save()
        g.translate(BX * W, BY * H)
        g.rotate(T * 0.12)
        g.drawImage(ball, -BR * W, -BR * W, BR * 2 * W, BR * 2 * W)
        g.restore()
      }
      g.globalCompositeOperation = 'lighter'
      const oa = Math.sin(T * 0.9)
      if (oa > 0) {
        const ang = T * 0.45
        const ox = BX * W + Math.cos(ang) * BR * W * 0.93
        const oy = BY * H + Math.sin(ang) * BR * W * 0.93
        const orb = 5 * s
        const og = g.createRadialGradient(ox, oy, 0, ox, oy, orb)
        og.addColorStop(0, `rgba(200,255,245,${(oa * 0.7).toFixed(2)})`)
        og.addColorStop(1, 'rgba(0,224,198,0)')
        g.fillStyle = og
        g.beginPath(); g.arc(ox, oy, orb, 0, 7); g.fill()
      }
      if (T > nextFlick) {
        nextFlick = T + 0.9 + Math.random() * 1.6
        flicks.push({ e: ED[Math.floor(Math.random() * ED.length)], life: 1 })
      }
      for (let f = flicks.length - 1; f >= 0; f--) {
        const fl = flicks[f]
        fl.life *= 0.9
        if (fl.life < 0.05) { flicks.splice(f, 1); continue }
        const A = nodes[fl.e[0]]; const B = nodes[fl.e[1]]
        const jit = 0.55 + Math.random() * 0.45
        g.strokeStyle = `rgba(120,255,225,${(fl.life * 0.3 * jit).toFixed(2)})`
        g.lineWidth = 1.1 * s
        g.beginPath(); g.moveTo(A.x * W, A.y * H); g.lineTo(B.x * W, B.y * H); g.stroke()
      }
      for (const n of nodes) {
        const tw = 0.5 + Math.sin(T * n.sp * 2 + n.ph) * 0.5
        n.heat *= 0.93
        const a = tw * 0.14 + n.heat * 0.45
        if (a < 0.02) continue
        const x = n.x * W; const y = n.y * H; const R = n.r * W + (2.4 + tw * 1.6 + n.heat * 4.5) * s
        const rg = g.createRadialGradient(x, y, 0, x, y, R)
        rg.addColorStop(0, `rgba(${n.cr},${n.cg},${n.cb},${Math.min(0.7, a).toFixed(3)})`)
        rg.addColorStop(1, `rgba(${n.cr},${n.cg},${n.cb},0)`)
        g.fillStyle = rg
        g.beginPath(); g.arc(x, y, R, 0, 7); g.fill()
        if (n.heat > 0.35) {
          g.fillStyle = `rgba(255,255,255,${(n.heat * 0.6).toFixed(2)})`
          g.beginPath(); g.arc(x, y, 1 * s, 0, 7); g.fill()
        }
      }
      for (let p = pulses.length - 1; p >= 0; p--) {
        const u = pulses[p]
        u.t += u.sp
        if (u.t >= 1) {
          nodes[u.b].heat = 1
          u.hops -= 1
          const nx = pickNext(u.b, u.a)
          if (u.hops <= 0 || nx === null) { pulses.splice(p, 1); spawn(); continue }
          u.a = u.b; u.b = nx; u.t = 0
        }
        const A = nodes[u.a]; const B = nodes[u.b]
        const px = (A.x + (B.x - A.x) * u.t) * W
        const py = (A.y + (B.y - A.y) * u.t) * H
        u.trail.unshift([px, py])
        if (u.trail.length > 10) u.trail.pop()
        for (let k = u.trail.length - 1; k > 0; k--) {
          const f = 1 - k / u.trail.length
          g.strokeStyle = `rgba(140,255,230,${(f * 0.38).toFixed(2)})`
          g.lineWidth = (1.7 * f + 0.4) * s
          g.beginPath(); g.moveTo(u.trail[k][0], u.trail[k][1]); g.lineTo(u.trail[k - 1][0], u.trail[k - 1][1]); g.stroke()
        }
        const pr = 4 * s
        const rg = g.createRadialGradient(px, py, 0, px, py, pr)
        rg.addColorStop(0, 'rgba(230,255,250,0.85)')
        rg.addColorStop(0.35, 'rgba(90,255,220,0.4)')
        rg.addColorStop(1, 'rgba(90,255,220,0)')
        g.fillStyle = rg
        g.beginPath(); g.arc(px, py, pr, 0, 7); g.fill()
        g.fillStyle = 'rgba(255,255,255,0.95)'
        g.beginPath(); g.arc(px, py, 0.9 * s, 0, 7); g.fill()
      }
      g.globalCompositeOperation = 'source-over'
      raf = requestAnimationFrame(frame)
    }
    raf = requestAnimationFrame(frame)

    return () => {
      stopped = true
      window.removeEventListener('resize', onResize)
      img.removeEventListener('load', size)
      if (raf) cancelAnimationFrame(raf)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
}

export default function LogoMark({ size = 44, glow = true, style }) {
  const full = size / CROP_FRAC
  const left = -full * OFFSET_X_FRAC
  const top = -full * OFFSET_Y_FRAC
  const imgRef = useRef(null)
  const ballRef = useRef(null)
  const canvasRef = useRef(null)
  useLogoAnimation(canvasRef, imgRef, ballRef)

  return (
    <div
      style={{
        width: size,
        height: size,
        overflow: 'hidden',
        position: 'relative',
        flex: 'none',
        filter: glow ? 'drop-shadow(0 0 10px rgba(0,224,198,.6))' : undefined,
        ...style,
      }}
    >
      <img
        ref={imgRef}
        src="/parker-logo-mesh.png"
        alt="PARKER"
        style={{
          position: 'absolute',
          width: full,
          height: full,
          left,
          top,
          objectFit: 'contain',
        }}
      />
      <img ref={ballRef} src="/parker-logo-ball.webp" alt="" style={{ display: 'none' }} />
      <canvas
        ref={canvasRef}
        style={{
          position: 'absolute',
          width: full,
          height: full,
          left,
          top,
          pointerEvents: 'none',
        }}
      />
    </div>
  )
}
