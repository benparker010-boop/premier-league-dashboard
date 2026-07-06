import { useEffect, useRef, useState } from 'react'
import LogoMark, { ND, ED, BX, BY, BR, CROP_FRAC, OFFSET_X_FRAC, OFFSET_Y_FRAC } from './LogoMark.jsx'

/*
  Cinematic boot intro (~6s, canvas + rAF, no dependencies).

  Sequence:
    0.0–1.2s  a constellation-style football player (30 nodes + thin teal
              edges, same visual language as the logo mesh) assembles out of
              converging glowing particles on the left of a dark pitch scene.
    1.2–2.2s  short run-up and kick across 4 keyframe poses (idle → stride →
              plant-and-swing → follow-through) with a slow-motion beat right
              at the moment of contact.
    2.2–4.1s  the ball (the same spinning geodesic wireframe art the logo
              uses, /parker-logo-ball.webp) launches off the boot with a teal
              light trail and arcs toward the logo position while the player
              dissolves back into drifting particles.
    3.7–5.1s  the ball decelerates into the exact spot the football occupies
              inside the P (derived from the LogoMark BX/BY/BR + crop
              constants) and the P's constellation mesh (the real ND/ED data)
              draws itself around it — nodes pop in radiating out from the
              ball, edges draw on — crossfading into the real <LogoMark>
              element so the idle animation (twinkle, pulses, rotating ball)
              takes over seamlessly.
    5.0–5.9s  "PARKER" + "WORLD CUP 2026 · AI ANALYTICS" fade in beneath the
              logo, then the alive logo FLIP-glides into the header logo's
              measured rect (#pk-header-logo) while the overlay fades,
              revealing the site.

  Behaviour: plays once ever (localStorage), any click/keypress skips
  straight to the header handoff, clicking the header logo replays it, and
  prefers-reduced-motion skips it entirely (gated in App.jsx).
*/

export const INTRO_SEEN_KEY = 'parker_intro_seen'

const TL = {
  assembleEnd: 1.2,
  strideAt: 1.5,
  stepAt: 1.65,
  plantAt: 1.8,
  contactAt: 2.2,
  followAt: 2.45,
  dissolveAt: 2.65,
  flightEnd: 4.1,
  meshAt: 3.7,
  logoFadeAt: 4.4,
  textAt: 4.95,
  handoffAt: 5.9,
}

/* ---- figure keyframe poses ------------------------------------------------
   19 joints, coordinates in "figure units": x right (kick direction),
   y 0 = top of head … ~0.96 = ground, both scaled by figure height.
   Joint order: 0 headTop, 1 head, 2 neck, 3 chest, 4 waist,
   5 shoulderF, 6 elbowF, 7 handF (kicking side), 8 shoulderB, 9 elbowB,
   10 handB, 11 hipF, 12 kneeF, 13 ankleF, 14 toeF, 15 hipB, 16 kneeB,
   17 ankleB, 18 toeB.
   Posed from a reference photo of a full-force strike: run-up stride, a
   transition step onto the kicking foot, then the signature backswing —
   kicking leg extended high behind, torso pitched forward over the ball,
   head down watching it, arms flung wide (lead arm up-forward, kicking-side
   arm trailing) — through contact and a high follow-through. */
const P_IDLE = [[0.035,0.055],[0.03,0.13],[0.02,0.2],[0.01,0.29],[0.0,0.43],[0.06,0.21],[0.09,0.33],[0.11,0.43],[-0.03,0.21],[-0.07,0.32],[-0.09,0.42],[0.04,0.46],[0.06,0.69],[0.05,0.92],[0.12,0.95],[-0.04,0.46],[-0.04,0.69],[-0.06,0.92],[0.01,0.95]]
const P_STRIDE = [[0.1,0.05],[0.09,0.12],[0.08,0.19],[0.06,0.28],[0.02,0.42],[0.09,0.2],[-0.01,0.27],[-0.09,0.31],[0.06,0.2],[0.16,0.25],[0.24,0.2],[0.06,0.45],[0.2,0.56],[0.16,0.74],[0.22,0.77],[-0.01,0.45],[-0.12,0.63],[-0.23,0.78],[-0.3,0.81]]
const P_STEP = [[0.14,0.06],[0.12,0.13],[0.1,0.2],[0.07,0.29],[0.02,0.43],[0.11,0.21],[0.0,0.25],[-0.1,0.29],[0.08,0.21],[0.18,0.18],[0.27,0.13],[0.03,0.46],[0.0,0.68],[-0.04,0.91],[0.03,0.945],[-0.02,0.46],[0.1,0.6],[0.14,0.8],[0.2,0.83]]
const P_PLANT = [[0.17,0.115],[0.14,0.155],[0.1,0.215],[0.07,0.3],[0.03,0.44],[0.11,0.22],[0.01,0.27],[-0.1,0.31],[0.07,0.225],[0.1,0.11],[0.16,0.01],[0.02,0.47],[-0.14,0.4],[-0.28,0.3],[-0.34,0.28],[-0.03,0.47],[0.03,0.68],[0.0,0.92],[0.07,0.95]]
const P_CONTACT = [[0.08,0.085],[0.05,0.14],[0.03,0.21],[0.02,0.3],[0.0,0.44],[0.03,0.22],[-0.09,0.26],[-0.19,0.3],[0.0,0.22],[0.06,0.15],[0.14,0.1],[0.03,0.46],[0.14,0.64],[0.25,0.82],[0.31,0.89],[-0.03,0.46],[0.02,0.68],[-0.01,0.92],[0.06,0.95]]
const P_FOLLOW = [[-0.1,0.075],[-0.09,0.145],[-0.08,0.22],[-0.06,0.31],[-0.02,0.44],[-0.04,0.23],[0.06,0.26],[0.15,0.24],[-0.1,0.24],[-0.18,0.31],[-0.24,0.38],[0.02,0.46],[0.18,0.52],[0.32,0.4],[0.38,0.33],[-0.04,0.46],[-0.02,0.69],[-0.06,0.92],[0.01,0.95]]

/* satellite nodes riding the skeleton (index 19+): [a, b, lerp, offX, offY] */
const SATS = [
  [5, 6, 0.5, 0.015, -0.012],
  [6, 7, 0.5, -0.012, 0.012],
  [8, 9, 0.5, -0.015, -0.012],
  [11, 12, 0.5, 0.022, 0],
  [12, 13, 0.5, 0.016, 0.01],
  [15, 16, 0.5, -0.022, 0],
  [16, 17, 0.5, -0.016, 0.01],
  [3, 4, 0.5, 0.05, 0],
  [3, 4, 0.42, -0.05, 0.012],
  // face and back-of-skull points: with headTop + neck they close a small
  // head outline that tilts with the pose (head down at the plant/contact)
  [1, 1, 0, 0.048, 0.002],
  [1, 1, 0, -0.044, -0.008],
]
const FIG_NODES = 19 + SATS.length

/* bones (routed through the satellite nodes) + constellation cross-links */
const FIG_EDGES = [
  [0, 1], [1, 2], [2, 3], [3, 4],
  [2, 5], [5, 19], [19, 6], [6, 20], [20, 7],
  [2, 8], [8, 21], [21, 9], [9, 10],
  [4, 11], [11, 22], [22, 12], [12, 23], [23, 13], [13, 14],
  [4, 15], [15, 24], [24, 16], [16, 25], [25, 17], [17, 18],
  [5, 8], [5, 3], [8, 3], [11, 15], [3, 11], [3, 15],
  [3, 26], [4, 26], [3, 27], [4, 27],
  [0, 28], [28, 2], [0, 29], [29, 2],
]

const clamp01 = (x) => (x < 0 ? 0 : x > 1 ? 1 : x)
const easeInOut = (x) => (x < 0.5 ? 2 * x * x : 1 - Math.pow(-2 * x + 2, 2) / 2)
const easeOutCubic = (x) => 1 - Math.pow(1 - x, 3)
const easeOutBack = (x) => 1 + 2.70158 * Math.pow(x - 1, 3) + 1.70158 * Math.pow(x - 1, 2)
/* swing covers 85% of its arc in the first half, then crawls into contact —
   the slow-motion beat */
const kickWarp = (p) => (p < 0.55 ? (p / 0.55) * 0.85 : 0.85 + ((p - 0.55) / 0.45) * 0.15)

function computeLayout() {
  const w = window.innerWidth
  const h = window.innerHeight
  const s = Math.max(120, Math.min(230, w * 0.5, h * 0.34))
  const left = w / 2 - s / 2
  const top = h * 0.42 - s / 2
  const fullW = s / CROP_FRAC
  const fh = Math.min(h * 0.44, 380, w * 0.42)
  const groundY = h * 0.66
  const axK = Math.max(w * 0.2, fh * 0.9)
  return {
    w, h, s, left, top, fullW, fh, groundY, axK,
    ax0: axK - fh * 0.5,
    ballGX: axK + fh * 0.32,
    // exact spot the football occupies inside the P (LogoMark constants)
    ballFX: left + (BX - OFFSET_X_FRAC) * fullW,
    ballFY: top + (BY - OFFSET_Y_FRAC) * fullW,
    ballFR: BR * fullW,
  }
}

export default function CinematicIntro({ onDone }) {
  const wrapRef = useRef(null)
  const bgRef = useRef(null)
  const canvasRef = useRef(null)
  const logoRef = useRef(null)
  const textRef = useRef(null)
  const onDoneRef = useRef(onDone)
  onDoneRef.current = onDone
  const [layout, setLayout] = useState(computeLayout)
  const layoutRef = useRef(layout)
  layoutRef.current = layout

  useEffect(() => {
    const cvs = canvasRef.current
    const wrap = wrapRef.current
    const logoEl = logoRef.current
    const textEl = textRef.current
    const bgEl = bgRef.current
    if (!cvs || !wrap || !logoEl || !textEl || !bgEl) return undefined
    const g = cvs.getContext('2d')

    // "once ever" is marked as soon as the intro starts playing
    try {
      localStorage.setItem(INTRO_SEEN_KEY, '1')
    } catch (e) {
      /* ignore */
    }

    let stopped = false
    let handoff = false
    let raf = null
    let doneTimer = null
    let lastT = 0
    let ballRot = 0
    const trail = []

    const dpr = Math.min(2, window.devicePixelRatio || 1)
    const sizeCanvas = () => {
      cvs.width = window.innerWidth * dpr
      cvs.height = window.innerHeight * dpr
      g.setTransform(dpr, 0, 0, dpr, 0, 0)
    }
    sizeCanvas()
    const onResize = () => {
      sizeCanvas()
      const L = computeLayout()
      layoutRef.current = L
      setLayout(L)
    }
    window.addEventListener('resize', onResize)

    const ballImg = new Image()
    ballImg.src = '/parker-logo-ball.webp'

    // per-node randoms: assembly origin, twinkle, dissolve drift
    const fx = Array.from({ length: FIG_NODES }, () => ({
      ang: Math.random() * Math.PI * 2,
      dist: 0.18 + Math.random() * 0.45,
      delay: Math.random() * 0.35,
      ph: Math.random() * 7,
      sp: 0.8 + Math.random() * 1.6,
      dAng: Math.random() * Math.PI * 2,
      dSpd: 0.4 + Math.random() * 0.8,
      dDelay: Math.random() * 0.45,
    }))
    const dust = Array.from({ length: 16 }, () => ({
      x: Math.random(), y: Math.random(),
      vx: (Math.random() - 0.5) * 0.02, vy: (Math.random() - 0.5) * 0.02,
      ph: Math.random() * 7, sp: 0.6 + Math.random() * 1.2,
    }))

    // mesh nodes pop in radiating outward from the ball's resting spot
    const popT = new Array(ND.length)
    ND.map((d, i) => ({ i, d: Math.hypot(d[0] - BX, d[1] - BY) }))
      .sort((a, b) => a.d - b.d)
      .forEach((r, k) => {
        popT[r.i] = TL.meshAt + (k / ND.length) * 0.65 + Math.random() * 0.08
      })
    const meshCol = ND.map((d) => {
      const m = 255 / Math.max(d[3], d[4], d[5])
      return [Math.round(d[3] * m), Math.round(d[4] * m), Math.round(d[5] * m)]
    })

    const startHandoff = () => {
      if (handoff) return
      handoff = true
      stopped = true
      if (raf) cancelAnimationFrame(raf)
      cvs.style.transition = 'opacity .3s ease'
      cvs.style.opacity = '0'
      textEl.style.transition = 'opacity .3s ease, transform .3s ease'
      textEl.style.opacity = '0'
      logoEl.style.transition = 'opacity .2s ease'
      logoEl.style.opacity = '1'
      requestAnimationFrame(() => {
        const target = document.getElementById('pk-header-logo')
        if (target) {
          const tr = target.getBoundingClientRect()
          const lr = logoEl.getBoundingClientRect()
          if (tr.width > 0 && lr.width > 0) {
            logoEl.style.transition = 'opacity .2s ease, transform .8s cubic-bezier(.72,.02,.26,1)'
            logoEl.style.transform = `translate(${tr.left - lr.left}px, ${tr.top - lr.top}px) scale(${tr.width / lr.width})`
          }
        }
        bgEl.style.transition = 'opacity .6s ease .18s'
        bgEl.style.opacity = '0'
        doneTimer = setTimeout(() => onDoneRef.current(), 880)
      })
    }

    const skip = () => startHandoff()
    window.addEventListener('keydown', skip)
    wrap.addEventListener('pointerdown', skip)

    const mixPose = (A, B, u) => A.map((p, i) => [p[0] + (B[i][0] - p[0]) * u, p[1] + (B[i][1] - p[1]) * u])
    const poseAt = (t) => {
      if (t <= TL.assembleEnd) return P_IDLE
      if (t <= TL.strideAt) return mixPose(P_IDLE, P_STRIDE, easeInOut((t - TL.assembleEnd) / (TL.strideAt - TL.assembleEnd)))
      if (t <= TL.stepAt) return mixPose(P_STRIDE, P_STEP, easeInOut((t - TL.strideAt) / (TL.stepAt - TL.strideAt)))
      if (t <= TL.plantAt) return mixPose(P_STEP, P_PLANT, easeInOut((t - TL.stepAt) / (TL.plantAt - TL.stepAt)))
      if (t <= TL.contactAt) {
        // the foot whips DOWN through the grass and into the ball, not in a
        // straight line from the backswing — arc the kicking leg's chain
        const u = kickWarp((t - TL.plantAt) / (TL.contactAt - TL.plantAt))
        const pose = mixPose(P_PLANT, P_CONTACT, u)
        const arc = Math.sin(Math.PI * u)
        pose[12][1] += 0.12 * arc
        pose[13][0] += 0.02 * arc
        pose[13][1] += 0.33 * arc
        pose[14][0] += 0.03 * arc
        pose[14][1] += 0.36 * arc
        return pose
      }
      if (t <= TL.followAt) {
        // follow-through sweeps forward in an arc around the hip
        const u = easeOutCubic((t - TL.contactAt) / (TL.followAt - TL.contactAt))
        const pose = mixPose(P_CONTACT, P_FOLLOW, u)
        const arc = Math.sin(Math.PI * u)
        pose[12][0] += 0.03 * arc
        pose[13][0] += 0.08 * arc
        pose[13][1] += 0.02 * arc
        pose[14][0] += 0.1 * arc
        pose[14][1] += 0.02 * arc
        return pose
      }
      return P_FOLLOW
    }

    const figurePoints = (t, L) => {
      const pose = poseAt(t)
      let ax
      if (t < TL.assembleEnd) ax = L.ax0
      else if (t < TL.plantAt) ax = L.ax0 + (L.axK - L.ax0) * easeInOut((t - TL.assembleEnd) / (TL.plantAt - TL.assembleEnd))
      else ax = L.axK
      const topY = L.groundY - L.fh
      const pts = pose.map((p) => [ax + p[0] * L.fh, topY + p[1] * L.fh])
      for (const [a, b, u, ox, oy] of SATS) {
        pts.push([
          pts[a][0] + (pts[b][0] - pts[a][0]) * u + ox * L.fh,
          pts[a][1] + (pts[b][1] - pts[a][1]) * u + oy * L.fh,
        ])
      }
      return pts
    }

    const drawGround = (t, L) => {
      const a0 = t < TL.dissolveAt ? 1 : clamp01(1 - (t - TL.dissolveAt) / 0.9)
      if (a0 <= 0) return
      const x0 = L.ax0 - L.fh * 0.45
      const x1 = L.ballGX + L.fh * 0.55
      const grd = g.createLinearGradient(x0, 0, x1, 0)
      grd.addColorStop(0, 'rgba(0,224,198,0)')
      grd.addColorStop(0.5, `rgba(0,224,198,${(0.16 * a0).toFixed(3)})`)
      grd.addColorStop(1, 'rgba(0,224,198,0)')
      g.strokeStyle = grd
      g.lineWidth = 1
      g.beginPath()
      g.moveTo(x0, L.groundY + 0.5)
      g.lineTo(x1, L.groundY + 0.5)
      g.stroke()
    }

    const drawFigure = (t, L) => {
      if (t > 3.9) return
      const pts = figurePoints(t, L)
      const scale = L.fh / 350
      const alphas = new Array(pts.length)
      for (let i = 0; i < pts.length; i++) {
        const f = fx[i]
        let [x, y] = pts[i]
        let a = 1
        if (t < TL.assembleEnd + 0.05) {
          const p = clamp01((t - f.delay) / 0.7)
          const e = easeOutCubic(p)
          const d0 = f.dist * Math.min(L.w, L.h)
          x += Math.cos(f.ang) * d0 * (1 - e)
          y += Math.sin(f.ang) * d0 * (1 - e)
          a = clamp01(p * 1.8)
        }
        if (t > TL.dissolveAt) {
          const p = clamp01((t - TL.dissolveAt - f.dDelay) / 0.85)
          const e = easeOutCubic(p)
          const dr = e * L.fh * 0.4 * f.dSpd
          x += Math.cos(f.dAng) * dr
          y += Math.sin(f.dAng) * dr - e * L.fh * 0.12
          a *= 1 - p
        }
        pts[i] = [x, y]
        alphas[i] = a
      }
      g.globalCompositeOperation = 'lighter'
      g.lineWidth = Math.max(0.8, 1.1 * scale)
      // edges die faster than nodes so the dissolve reads as drifting
      // particles, not a stretched web
      const edgeGate = t > TL.dissolveAt ? clamp01(1 - (t - TL.dissolveAt) / 0.45) : 1
      for (const [a, b] of FIG_EDGES) {
        const ea = Math.min(alphas[a], alphas[b]) * edgeGate
        if (ea <= 0.02) continue
        g.strokeStyle = `rgba(0,224,198,${(ea * 0.42).toFixed(3)})`
        g.beginPath()
        g.moveTo(pts[a][0], pts[a][1])
        g.lineTo(pts[b][0], pts[b][1])
        g.stroke()
      }
      for (let i = 0; i < pts.length; i++) {
        const a = alphas[i]
        if (a <= 0.02) continue
        const f = fx[i]
        const tw = 0.65 + 0.35 * Math.sin(t * f.sp * 2 + f.ph)
        const base = (i === 1 ? 3.4 : i < 19 ? 2.5 : 1.7) * scale
        const R = base * 3.1
        const [x, y] = pts[i]
        const rg = g.createRadialGradient(x, y, 0, x, y, R)
        rg.addColorStop(0, `rgba(160,255,238,${(a * tw * 0.85).toFixed(3)})`)
        rg.addColorStop(0.35, `rgba(0,224,198,${(a * tw * 0.4).toFixed(3)})`)
        rg.addColorStop(1, 'rgba(0,224,198,0)')
        g.fillStyle = rg
        g.beginPath(); g.arc(x, y, R, 0, 7); g.fill()
        g.fillStyle = `rgba(235,255,250,${(a * (0.5 + tw * 0.5)).toFixed(3)})`
        g.beginPath(); g.arc(x, y, Math.max(1, base * 0.55), 0, 7); g.fill()
      }
      for (const d of dust) {
        d.x = (d.x + d.vx * 0.016 + 1) % 1
        d.y = (d.y + d.vy * 0.016 + 1) % 1
        const gate = t < 1.4 ? clamp01((t - 0.3) / 0.8) : t > TL.dissolveAt ? clamp01(1 - (t - TL.dissolveAt)) : 1
        if (gate <= 0.02) continue
        const tw = 0.5 + 0.5 * Math.sin(t * d.sp + d.ph)
        const x = L.ax0 - L.fh * 0.3 + d.x * L.fh * 1.6
        const y = L.groundY - L.fh * 1.15 + d.y * L.fh * 1.2
        g.fillStyle = `rgba(0,224,198,${(gate * tw * 0.22).toFixed(3)})`
        g.beginPath(); g.arc(x, y, 1.2 * scale + 0.4, 0, 7); g.fill()
      }
      g.globalCompositeOperation = 'source-over'
    }

    const drawBall = (t, dt, L) => {
      if (t < 0.9) return
      const r0 = Math.max(9, L.fh * 0.052)
      const appear = clamp01((t - 0.9) / 0.4)
      let x = L.ballGX
      let y = L.groundY - r0
      let r = r0
      if (t >= TL.contactAt) {
        const p = clamp01((t - TL.contactAt) / (TL.flightEnd - TL.contactAt))
        const e = 1 - Math.pow(1 - p, 3.4)
        const x2 = L.ballFX
        const y2 = L.ballFY
        const cx = x + (x2 - x) * 0.48
        const cy = Math.min(y, y2) - Math.max(150, L.h * 0.24)
        const v = 1 - e
        const bx = v * v * x + 2 * v * e * cx + e * e * x2
        const by = v * v * y + 2 * v * e * cy + e * e * y2
        x = bx
        y = by
        r = r0 + (L.ballFR - r0) * e
        ballRot += dt * (16 * (1 - e) + 0.12)
        if (e < 0.985 && !Number.isFinite(freeze)) trail.push({ x, y, t })
      }
      // canvas ball hands over to the DOM logo's own rotating ball
      const A = appear * (1 - clamp01((t - (TL.logoFadeAt + 0.15)) / 0.45))
      g.globalCompositeOperation = 'lighter'
      for (let i = trail.length - 1; i >= 0; i--) {
        if (t - trail[i].t > 0.55) trail.splice(i, 1)
      }
      g.lineCap = 'round'
      for (let i = 1; i < trail.length; i++) {
        const age = (t - trail[i].t) / 0.55
        const a = (1 - age) * 0.5 * A
        if (a <= 0.01) continue
        g.strokeStyle = `rgba(0,224,198,${a.toFixed(3)})`
        g.lineWidth = Math.max(0.6, (1 - age) * r * 0.5)
        g.beginPath()
        g.moveTo(trail[i - 1].x, trail[i - 1].y)
        g.lineTo(trail[i].x, trail[i].y)
        g.stroke()
      }
      if (A > 0.01) {
        const gr = g.createRadialGradient(x, y, 0, x, y, r * 2.1)
        gr.addColorStop(0, `rgba(0,224,198,${(0.4 * A).toFixed(3)})`)
        gr.addColorStop(1, 'rgba(0,224,198,0)')
        g.fillStyle = gr
        g.beginPath(); g.arc(x, y, r * 2.1, 0, 7); g.fill()
      }
      if (t >= TL.contactAt && t < TL.contactAt + 0.22) {
        const q = (t - TL.contactAt) / 0.22
        g.strokeStyle = `rgba(180,255,240,${((1 - q) * 0.6).toFixed(3)})`
        g.lineWidth = 2 * (1 - q) + 0.5
        g.beginPath(); g.arc(L.ballGX, L.groundY - r0, r0 * (1 + q * 2.6), 0, 7); g.stroke()
      }
      if (t >= TL.flightEnd && t < TL.flightEnd + 0.5) {
        const q = (t - TL.flightEnd) / 0.5
        g.strokeStyle = `rgba(0,224,198,${((1 - q) * 0.45).toFixed(3)})`
        g.lineWidth = 1.4 * (1 - q) + 0.3
        g.beginPath(); g.arc(L.ballFX, L.ballFY, L.ballFR * (1 + q * 1.2), 0, 7); g.stroke()
      }
      g.globalCompositeOperation = 'source-over'
      if (A > 0.01) {
        g.save()
        g.globalAlpha = A
        g.translate(x, y)
        g.rotate(ballRot)
        if (ballImg.complete && ballImg.naturalWidth) {
          g.drawImage(ballImg, -r, -r, r * 2, r * 2)
        } else {
          g.strokeStyle = 'rgba(0,224,198,.9)'
          g.lineWidth = 1.2
          g.beginPath(); g.arc(0, 0, r, 0, 7); g.stroke()
          g.beginPath(); g.ellipse(0, 0, r, r * 0.45, 0, 0, 7); g.stroke()
          g.beginPath(); g.ellipse(0, 0, r * 0.45, r, 0, 0, 7); g.stroke()
        }
        g.restore()
      }
    }

    const drawMesh = (t, L) => {
      if (t < TL.meshAt) return
      const meshA = 1 - clamp01((t - (TL.logoFadeAt + 0.45)) / 0.45)
      if (meshA <= 0) return
      const fw = L.fullW
      const px = (i) => L.left + (ND[i][0] - OFFSET_X_FRAC) * fw
      const py = (i) => L.top + (ND[i][1] - OFFSET_Y_FRAC) * fw
      g.globalCompositeOperation = 'lighter'
      for (const [a, b] of ED) {
        const st = Math.max(popT[a], popT[b]) + 0.05
        const q = easeOutCubic(clamp01((t - st) / 0.3))
        if (q <= 0) continue
        const x0 = px(a)
        const y0 = py(a)
        g.strokeStyle = `rgba(0,224,198,${(0.34 * meshA).toFixed(3)})`
        g.lineWidth = Math.max(0.7, fw * 0.0022)
        g.beginPath()
        g.moveTo(x0, y0)
        g.lineTo(x0 + (px(b) - x0) * q, y0 + (py(b) - y0) * q)
        g.stroke()
      }
      for (let i = 0; i < ND.length; i++) {
        const p = clamp01((t - popT[i]) / 0.24)
        if (p <= 0) continue
        const s = easeOutBack(p)
        const [cr, cg, cb] = meshCol[i]
        const x = px(i)
        const y = py(i)
        const R = Math.max(0.1, (ND[i][2] * fw * 0.62 + fw * 0.012) * s)
        const rg = g.createRadialGradient(x, y, 0, x, y, R * 2.4)
        rg.addColorStop(0, `rgba(${cr},${cg},${cb},${(0.8 * p * meshA).toFixed(3)})`)
        rg.addColorStop(1, `rgba(${cr},${cg},${cb},0)`)
        g.fillStyle = rg
        g.beginPath(); g.arc(x, y, R * 2.4, 0, 7); g.fill()
        g.fillStyle = `rgba(240,255,252,${(0.75 * p * meshA).toFixed(3)})`
        g.beginPath(); g.arc(x, y, Math.max(0.8, R * 0.4), 0, 7); g.fill()
      }
      g.globalCompositeOperation = 'source-over'
    }

    // dev-only: ?introt=2.1 freezes the timeline at that second for tuning
    const freeze = import.meta.env.DEV
      ? parseFloat(new URLSearchParams(window.location.search).get('introt'))
      : NaN
    const t0 = performance.now()
    const frame = (now) => {
      if (stopped) return
      const t = Number.isFinite(freeze) ? freeze : (now - t0) / 1000
      const dt = Math.min(0.05, Math.max(0.001, t - lastT))
      lastT = t
      const L = layoutRef.current
      g.clearRect(0, 0, L.w, L.h)
      drawGround(t, L)
      drawFigure(t, L)
      drawBall(t, dt, L)
      drawMesh(t, L)
      logoEl.style.opacity = String(clamp01((t - TL.logoFadeAt) / 0.5))
      const tf = easeOutCubic(clamp01((t - TL.textAt) / 0.55))
      textEl.style.opacity = String(tf)
      textEl.style.transform = `translateY(${((1 - tf) * 14).toFixed(1)}px)`
      if (t >= TL.handoffAt) {
        startHandoff()
        return
      }
      raf = requestAnimationFrame(frame)
    }
    raf = requestAnimationFrame(frame)

    return () => {
      stopped = true
      if (raf) cancelAnimationFrame(raf)
      if (doneTimer) clearTimeout(doneTimer)
      window.removeEventListener('resize', onResize)
      window.removeEventListener('keydown', skip)
      wrap.removeEventListener('pointerdown', skip)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div ref={wrapRef} style={{ position: 'fixed', inset: 0, zIndex: 60, overflow: 'hidden' }}>
      <div ref={bgRef} style={{ position: 'absolute', inset: 0, background: 'var(--bg)' }}>
        {/* faint pitch lines, same drawing as the site background */}
        <div style={{ position: 'absolute', inset: 0, display: 'grid', placeItems: 'center', opacity: 0.06, overflow: 'hidden', pointerEvents: 'none' }}>
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
      </div>
      <canvas ref={canvasRef} style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }} />
      <div
        ref={logoRef}
        style={{
          position: 'absolute',
          left: layout.left,
          top: layout.top,
          width: layout.s,
          height: layout.s,
          opacity: 0,
          transformOrigin: 'top left',
          willChange: 'transform,opacity',
        }}
      >
        <LogoMark size={layout.s} glow={false} />
      </div>
      <div
        ref={textRef}
        style={{
          position: 'absolute',
          left: 0,
          right: 0,
          top: layout.top + layout.s + 16,
          textAlign: 'center',
          opacity: 0,
          transform: 'translateY(14px)',
          pointerEvents: 'none',
        }}
      >
        <div
          style={{
            fontFamily: 'var(--font-display)',
            fontSize: Math.min(46, layout.w * 0.1),
            fontWeight: 600,
            letterSpacing: '.32em',
            textIndent: '.32em',
            color: 'var(--text-brightest)',
            textShadow: '0 0 26px rgba(0,224,198,.35)',
          }}
        >
          PARKER
        </div>
        <div
          style={{
            marginTop: 10,
            fontFamily: 'var(--font-mono)',
            fontSize: 12,
            letterSpacing: '.38em',
            textIndent: '.38em',
            color: 'var(--teal)',
          }}
        >
          WORLD CUP 2026 · AI ANALYTICS
        </div>
      </div>
    </div>
  )
}
