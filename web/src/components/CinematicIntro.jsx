import { useEffect, useRef, useState } from 'react'
import LogoMark, { ND, ED, BX, BY, BR, CROP_FRAC, OFFSET_X_FRAC, OFFSET_Y_FRAC } from './LogoMark.jsx'

/*
  Cinematic boot intro (~3.9s + handoff, canvas + rAF, zero dependencies).

  A silhouetted footballer (articulated 19-joint skeleton skinned with
  tapered-capsule limbs — shirt, shorts, socks, boots, teal rim light)
  materialises from sparks, breathes through a short idle, takes a two-step
  run-up and strikes the ball: slow wind-up into the reference backswing,
  explosive accelerating swing arced down through the grass, contact squash +
  dust burst, high follow-through. The ball (the logo's own geodesic art)
  arcs with spin, motion-blur ghosts and a light trail into the exact spot
  the football occupies inside the P (LogoMark BX/BY/BR + crop constants);
  the P's real constellation mesh (ND/ED) draws itself around it radiating
  outward and crossfades into the live <LogoMark>, which lands with a spring
  settle + ripple. Wordmark fades in, then the alive logo FLIP-glides onto
  the header logo's measured rect (#pk-header-logo) as the site is revealed.

  Behaviour: plays once ever (localStorage — deliberate, so Ben can demo via
  the header-logo replay), a SKIP button plus any click/tap/keypress jump
  straight to the handoff, and prefers-reduced-motion skips the whole thing
  (gated in App.jsx). Dev-only: ?introt=<sec> freezes the timeline.
*/

export const INTRO_SEEN_KEY = 'parker_intro_seen'

const MATERIALIZE = 0.45
const TL = {
  idleEnd: 1.0,
  strideAt: 1.3,
  stepAt: 1.55,
  plantAt: 1.82,
  contactAt: 2.08,
  followAt: 2.34,
  recoverAt: 2.62, // kicking foot steps back down, body settles upright
  fadeOutAt: 2.6, // player fades while the eye follows the ball
  meshAt: 2.7,
  flightEnd: 2.95,
  logoFadeAt: 3.0,
  textAt: 3.2,
  handoffAt: 3.85,
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
const P_RECOVER = [[0.03,0.05],[0.025,0.125],[0.02,0.2],[0.01,0.29],[0.0,0.43],[0.05,0.21],[0.07,0.32],[0.09,0.42],[-0.03,0.21],[-0.06,0.32],[-0.08,0.42],[0.03,0.46],[0.09,0.68],[0.12,0.91],[0.19,0.94],[-0.04,0.46],[-0.06,0.69],[-0.09,0.92],[-0.02,0.95]]

/* PARKER club kit: dark base, teal trim, site palette. Index 0 = near-side
   limbs, 1 = far side (shaded for depth). */
const KIT = {
  skin: ['#243645', '#182530'],
  shirt: ['#0f4f48', '#0a3733'],
  shorts: ['#13253a', '#0d1a29'],
  socks: ['#0f4f48', '#0a3733'],
  boots: ['#0b1119', '#080d13'],
  trim: ['#2fe8cf', '#1da591'],
  hair: '#0c1520',
}

const clamp01 = (x) => (x < 0 ? 0 : x > 1 ? 1 : x)
const easeInOut = (x) => (x < 0.5 ? 2 * x * x : 1 - Math.pow(-2 * x + 2, 2) / 2)
const easeOutCubic = (x) => 1 - Math.pow(1 - x, 3)
const easeOutBack = (x) => 1 + 2.70158 * Math.pow(x - 1, 3) + 1.70158 * Math.pow(x - 1, 2)
/* biomechanics of the swing: slow loading, then the shank whips through —
   velocity peaks right at contact */
const kickWarp = (p) => Math.pow(p, 2.4)

function computeLayout() {
  const w = window.innerWidth
  const h = window.innerHeight
  const s = Math.max(120, Math.min(230, w * 0.5, h * 0.34))
  const left = w / 2 - s / 2
  const top = h * 0.42 - s / 2
  const fullW = s / CROP_FRAC
  const fh = Math.min(h * 0.4, 340, w * 0.34)
  const groundY = h * 0.66
  // pin the kick spot well left of the logo so the shot always travels a
  // real diagonal (never straight up under the badge)
  const ballGX = Math.max(w * 0.24, fh * 0.68)
  const axK = ballGX - fh * 0.32
  return {
    w, h, s, left, top, fullW, fh, groundY, axK,
    // run-up start, clamped so the idle figure stays fully on-screen
    ax0: Math.max(axK - fh * 0.45, fh * 0.16),
    ballGX,
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
  const settleRef = useRef(null)
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
    const settleEl = settleRef.current
    const textEl = textRef.current
    const bgEl = bgRef.current
    if (!cvs || !wrap || !logoEl || !settleEl || !textEl || !bgEl) return undefined
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

    // materialise sparks: converge onto random joints as the player fades in
    const sparks = Array.from({ length: 26 }, () => ({
      j: Math.floor(Math.random() * 19),
      jx: (Math.random() - 0.5) * 0.12,
      jy: (Math.random() - 0.5) * 0.12,
      ang: Math.random() * Math.PI * 2,
      dist: 0.15 + Math.random() * 0.35,
      delay: Math.random() * 0.18,
    }))
    // contact dust burst: deterministic ballistic particles
    const dust = Array.from({ length: 12 }, () => ({
      ang: -0.15 - Math.random() * 1.1, // up-forward spray
      spd: 0.25 + Math.random() * 0.55,
      size: 0.6 + Math.random() * 1.2,
    }))

    // mesh nodes pop in radiating outward from the ball's resting spot
    const popT = new Array(ND.length)
    ND.map((d, i) => ({ i, d: Math.hypot(d[0] - BX, d[1] - BY) }))
      .sort((a, b) => a.d - b.d)
      .forEach((r, k) => {
        popT[r.i] = TL.meshAt + (k / ND.length) * 0.5 + Math.random() * 0.06
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
      settleEl.style.transform = ''
      logoEl.style.transition = 'opacity .2s ease'
      logoEl.style.opacity = '1'
      // synchronous style flush instead of requestAnimationFrame — rAF can
      // stop entirely in background tabs, which would strand the intro
      logoEl.getBoundingClientRect()
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
    }

    const skip = () => startHandoff()
    window.addEventListener('keydown', skip)
    wrap.addEventListener('pointerdown', skip)

    const mixPose = (A, B, u) => A.map((p, i) => [p[0] + (B[i][0] - p[0]) * u, p[1] + (B[i][1] - p[1]) * u])
    const poseAt = (t) => {
      let pose
      if (t <= TL.idleEnd) pose = P_IDLE.map((p) => [p[0], p[1]])
      else if (t <= TL.strideAt) pose = mixPose(P_IDLE, P_STRIDE, easeInOut((t - TL.idleEnd) / (TL.strideAt - TL.idleEnd)))
      else if (t <= TL.stepAt) pose = mixPose(P_STRIDE, P_STEP, easeInOut((t - TL.strideAt) / (TL.stepAt - TL.strideAt)))
      else if (t <= TL.plantAt) pose = mixPose(P_STEP, P_PLANT, easeInOut((t - TL.stepAt) / (TL.plantAt - TL.stepAt))) // slow wind-up
      else if (t <= TL.contactAt) {
        // the foot whips DOWN through the grass and into the ball, not in a
        // straight line from the backswing — arc the kicking leg's chain
        const u = kickWarp((t - TL.plantAt) / (TL.contactAt - TL.plantAt))
        pose = mixPose(P_PLANT, P_CONTACT, u)
        const arc = Math.sin(Math.PI * u)
        pose[12][1] += 0.12 * arc
        pose[13][0] += 0.02 * arc
        pose[13][1] += 0.33 * arc
        pose[14][0] += 0.03 * arc
        pose[14][1] += 0.36 * arc
      } else if (t <= TL.followAt) {
        // follow-through sweeps forward in an arc around the hip
        const u = easeOutCubic((t - TL.contactAt) / (TL.followAt - TL.contactAt))
        pose = mixPose(P_CONTACT, P_FOLLOW, u)
        const arc = Math.sin(Math.PI * u)
        pose[12][0] += 0.03 * arc
        pose[13][0] += 0.08 * arc
        pose[13][1] += 0.02 * arc
        pose[14][0] += 0.1 * arc
        pose[14][1] += 0.02 * arc
      } else if (t <= TL.recoverAt) pose = mixPose(P_FOLLOW, P_RECOVER, easeInOut((t - TL.followAt) / (TL.recoverAt - TL.followAt)))
      else pose = P_RECOVER.map((p) => [p[0], p[1]])

      // weight: vertical bounce through the run-up strides…
      if (t > TL.idleEnd && t < TL.plantAt) {
        const rp = (t - TL.idleEnd) / (TL.plantAt - TL.idleEnd)
        const dy = -0.014 * Math.abs(Math.sin(Math.PI * 2 * rp)) * Math.sin(Math.PI * rp)
        for (let j = 0; j < 19; j++) {
          if (j === 13 || j === 14 || j === 17 || j === 18) continue // feet stay grounded
          pose[j][1] += dy
        }
      }
      // …and a loading dip into the plant that releases through contact
      if (t > TL.plantAt && t < TL.contactAt + 0.1) {
        const dq = Math.sin(Math.PI * clamp01((t - TL.plantAt) / 0.32))
        for (const j of [0, 1, 2, 3, 4, 11, 15]) pose[j][1] += 0.016 * dq
      }

      // idle life: breathing + weight shift, blended out as the run begins
      const amp = t < TL.idleEnd ? 1 : clamp01(1 - (t - TL.idleEnd) / 0.3)
      if (amp > 0) {
        const br = Math.sin(t * 3.3) * amp
        const sw = Math.sin(t * 2.1 + 1.2) * amp
        pose[0][1] -= 0.008 * br; pose[1][1] -= 0.008 * br
        pose[2][1] -= 0.006 * br; pose[3][1] -= 0.005 * br
        pose[5][1] -= 0.005 * br; pose[8][1] -= 0.005 * br
        pose[4][0] += 0.008 * sw; pose[11][0] += 0.008 * sw; pose[15][0] += 0.008 * sw
        pose[0][0] -= 0.004 * sw; pose[1][0] -= 0.004 * sw
        pose[6][0] += 0.004 * br; pose[9][0] -= 0.004 * br
      }
      return pose
    }

    const figurePoints = (t, L) => {
      const pose = poseAt(t)
      let ax
      if (t < TL.idleEnd) ax = L.ax0
      else if (t < TL.plantAt) ax = L.ax0 + (L.axK - L.ax0) * easeInOut((t - TL.idleEnd) / (TL.plantAt - TL.idleEnd))
      else ax = L.axK
      const topY = L.groundY - L.fh
      const pts = pose.map((p) => [ax + p[0] * L.fh, topY + p[1] * L.fh])
      // head tracks the ball — down at it through the strike, up as it flies
      if (t > TL.stepAt) {
        const w = Math.min(clamp01((t - TL.stepAt) / 0.2), 0.65)
        const hd = pts[1]
        const B = ballState(t, L)
        const r = Math.hypot(pts[0][0] - hd[0], pts[0][1] - hd[1]) || 1
        const tilt = Math.max(-0.55, Math.min(0.85, Math.atan2(B.y - hd[1], B.x - hd[0]) * 0.7))
        const want = -Math.PI / 2 + tilt
        const cur = Math.atan2(pts[0][1] - hd[1], pts[0][0] - hd[0])
        const a = cur + (want - cur) * w
        pts[0] = [hd[0] + Math.cos(a) * r, hd[1] + Math.sin(a) * r]
      }
      return pts
    }

    /* ---- silhouette skinning ------------------------------------------- */
    const capsule = (x1, y1, x2, y2, w1, w2, color) => {
      const ang = Math.atan2(y2 - y1, x2 - x1)
      g.fillStyle = color
      g.beginPath()
      g.arc(x1, y1, w1, ang + Math.PI / 2, ang - Math.PI / 2)
      g.arc(x2, y2, w2, ang - Math.PI / 2, ang + Math.PI / 2)
      g.closePath()
      g.fill()
    }
    const lerpPt = (a, b, u) => [a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u]

    const drawPlayer = (t, L) => {
      if (t > TL.fadeOutAt + 0.55) return
      const pts = figurePoints(t, L)
      const fh = L.fh
      let alpha = easeOutCubic(clamp01(t / MATERIALIZE))
      if (t > TL.fadeOutAt) alpha *= clamp01(1 - (t - TL.fadeOutAt) / 0.5)
      if (alpha <= 0.01) return

      const [headTop, head, neck, chest, waist, shF, elF, haF, shB, elB, haB, hipF, knF, anF, toF, hipB, knB, anB, toB] = pts

      g.save()
      g.globalAlpha = alpha
      const limb = (a, b, w1, w2, color) => capsule(a[0], a[1], b[0], b[1], w1 * fh, w2 * fh, color)
      /* -- anatomy helpers: shading + muscled bezier limbs ---------------- */
      const rgbOf = (hx) => [parseInt(hx.slice(1, 3), 16), parseInt(hx.slice(3, 5), 16), parseInt(hx.slice(5, 7), 16)]
      const shade = (hx, f) => {
        const [r, gr, b] = rgbOf(hx)
        const m = f < 0 ? 0 : 255
        const k = Math.abs(f)
        return `rgb(${Math.round(r + (m - r) * k)},${Math.round(gr + (m - gr) * k)},${Math.round(b + (m - b) * k)})`
      }
      // cross-axis gradient: one consistent key light from the upper-left
      const crossGrad = (a, b, w, color) => {
        const dx = b[0] - a[0]
        const dy = b[1] - a[1]
        const len = Math.hypot(dx, dy) || 1
        let nx = -dy / len
        let ny = dx / len
        if (nx * -0.45 + ny * -0.9 < 0) { nx = -nx; ny = -ny }
        const mx = (a[0] + b[0]) / 2
        const my = (a[1] + b[1]) / 2
        const gr = g.createLinearGradient(mx + nx * w, my + ny * w, mx - nx * w, my - ny * w)
        gr.addColorStop(0, shade(color, 0.13))
        gr.addColorStop(1, shade(color, -0.24))
        return gr
      }
      // muscled limb segment: bezier outline with a mid-bulge, not a tube
      const muscle = (a, b, w1, bulge, tB, w2, color) => {
        const dx = b[0] - a[0]
        const dy = b[1] - a[1]
        const len = Math.hypot(dx, dy) || 1
        const nx = -dy / len
        const ny = dx / len
        const ang = Math.atan2(dy, dx)
        const W1 = w1 * fh
        const W2 = w2 * fh
        const WB = 2 * bulge * fh - (W1 + W2) / 2 // control point so the curve peaks at `bulge`
        const qx = a[0] + dx * tB
        const qy = a[1] + dy * tB
        g.fillStyle = crossGrad(a, b, Math.max(W1, bulge * fh), color)
        g.beginPath()
        g.arc(a[0], a[1], W1, ang + Math.PI / 2, ang - Math.PI / 2)
        g.quadraticCurveTo(qx - nx * WB, qy - ny * WB, b[0] - nx * W2, b[1] - ny * W2)
        g.arc(b[0], b[1], W2, ang - Math.PI / 2, ang + Math.PI / 2)
        g.quadraticCurveTo(qx + nx * WB, qy + ny * WB, a[0] + nx * W1, a[1] + ny * W1)
        g.closePath()
        g.fill()
      }
      const arm = (sh, el, ha, side) => {
        muscle(sh, el, 0.024, 0.029, 0.38, 0.016, KIT.skin[side]) // deltoid + bicep
        muscle(el, ha, 0.016, 0.02, 0.28, 0.009, KIT.skin[side]) // forearm taper
        muscle(sh, lerpPt(sh, el, 0.52), 0.029, 0.032, 0.42, 0.023, KIT.shirt[side]) // sleeve over
        limb(lerpPt(sh, el, 0.44), lerpPt(sh, el, 0.6), 0.013, 0.011, KIT.trim[side]) // cuff band
        g.fillStyle = KIT.skin[side]
        g.beginPath(); g.arc(ha[0], ha[1], 0.013 * fh, 0, 7); g.fill()
      }
      const leg = (hip, kn, an, to, side) => {
        muscle(hip, kn, 0.048, 0.055, 0.35, 0.025, KIT.skin[side]) // thigh (quad/ham mass)
        g.fillStyle = KIT.skin[side]
        g.beginPath(); g.arc(kn[0], kn[1], 0.025 * fh, 0, 7); g.fill() // knee
        muscle(kn, an, 0.023, 0.035, 0.3, 0.011, KIT.skin[side]) // calf bulge → slim ankle
        muscle(hip, lerpPt(hip, kn, 0.52), 0.05, 0.053, 0.5, 0.037, KIT.shorts[side]) // shorts
        muscle(lerpPt(kn, an, 0.42), an, 0.025, 0.026, 0.3, 0.014, KIT.socks[side]) // sock
        limb(lerpPt(kn, an, 0.44), lerpPt(kn, an, 0.485), 0.026, 0.025, KIT.trim[side]) // sock stripe 1
        limb(lerpPt(kn, an, 0.53), lerpPt(kn, an, 0.575), 0.025, 0.024, KIT.trim[side]) // sock stripe 2
        limb(an, to, 0.018, 0.022, KIT.boots[side]) // boot
        g.fillStyle = KIT.boots[side]
        g.beginPath(); g.arc(an[0], an[1], 0.02 * fh, 0, 7); g.fill() // heel
        limb(lerpPt(an, to, 0.15), lerpPt(an, to, 0.7), 0.006, 0.005, KIT.trim[side]) // boot flash
      }
      const torso = () => {
        // tapered trunk: shoulders → chest → waist, then the shorts seat
        const pAt = (p, q, w) => {
          const ang = Math.atan2(q[1] - p[1], q[0] - p[0])
          return [Math.cos(ang + Math.PI / 2) * w * fh, Math.sin(ang + Math.PI / 2) * w * fh]
        }
        const n1 = pAt(neck, chest, 0.062)
        const n2 = pAt(neck, waist, 0.058)
        const n3 = pAt(chest, waist, 0.05)
        // +n is the player's back (he faces +x): scapula → lumbar hollow
        // down the back, fuller chest curve on the front
        g.fillStyle = crossGrad(neck, waist, 0.065 * fh, KIT.shirt[0])
        g.beginPath()
        g.moveTo(neck[0] + n1[0], neck[1] + n1[1])
        g.quadraticCurveTo(chest[0] + n2[0] * 0.92, chest[1] + n2[1] * 0.92, waist[0] + n3[0] * 0.84, waist[1] + n3[1] * 0.84)
        g.lineTo(waist[0] - n3[0], waist[1] - n3[1])
        g.quadraticCurveTo(chest[0] - n2[0] * 1.18, chest[1] - n2[1] * 1.18, neck[0] - n1[0], neck[1] - n1[1])
        g.closePath()
        g.fill()
        // shoulder caps
        g.beginPath(); g.arc(shF[0], shF[1], 0.031 * fh, 0, 7); g.fill()
        g.beginPath(); g.arc(shB[0], shB[1], 0.031 * fh, 0, 7); g.fill()
        // teal collar band under the neck
        capsule(neck[0] + n1[0] * 0.55, neck[1] + n1[1] * 0.55, neck[0] - n1[0] * 0.55, neck[1] - n1[1] * 0.55, 0.013 * fh, 0.013 * fh, KIT.trim[0])
        // front seam down the shirt
        g.strokeStyle = 'rgba(47,232,207,0.55)'
        g.lineWidth = Math.max(1, 0.006 * fh)
        g.beginPath()
        g.moveTo(chest[0] + n2[0] * 0.82, chest[1] + n2[1] * 0.82)
        g.lineTo(waist[0] + n3[0] * 0.82, waist[1] + n3[1] * 0.82)
        g.stroke()
        // shorts seat bridging the hips
        g.fillStyle = KIT.shorts[0]
        capsule(hipB[0], hipB[1], hipF[0], hipF[1], 0.044 * fh, 0.044 * fh, KIT.shorts[0])
        capsule(waist[0], waist[1], (hipF[0] + hipB[0]) / 2, (hipF[1] + hipB[1]) / 2, 0.05 * fh, 0.046 * fh, KIT.shorts[0])
        // shorts trim hem
        g.strokeStyle = 'rgba(47,232,207,0.45)'
        g.beginPath()
        g.moveTo(hipF[0] + 0.02 * fh, hipF[1] + 0.035 * fh)
        g.lineTo(hipF[0] - 0.02 * fh, hipF[1] + 0.04 * fh)
        g.stroke()
      }
      // "PARKER AI" printed high on the back, just under the collar (matches
      // the reference kit photo's name-band placement) — tracks the torso's
      // position and lean, auto-fits to the shirt width, skipped when too
      // small to read as kit print
      const wordmark = () => {
        const mid = lerpPt(neck, chest, 0.62)
        const angT = Math.atan2(waist[1] - chest[1], waist[0] - chest[0]) - Math.PI / 2
        const maxW = 0.1 * fh // must stay inside the chest span (~0.116fh) with margin
        let fpx = 0.032 * fh
        g.save()
        g.font = `700 ${fpx}px "JetBrains Mono", monospace`
        const tw = g.measureText('PARKER AI').width
        if (tw > maxW) {
          fpx *= maxW / tw
          g.font = `700 ${fpx}px "JetBrains Mono", monospace`
        }
        if (fpx >= 5) {
          g.translate(mid[0], mid[1])
          g.rotate(angT)
          g.textAlign = 'center'
          g.textBaseline = 'middle'
          g.fillStyle = 'rgba(160,255,240,0.95)'
          g.fillText('PARKER AI', 0, 0)
        }
        g.restore()
      }
      // small glowing constellation-ball badge below the wordmark — echoes
      // the geodesic ball that flies at the end and the logo's own mesh,
      // matching the reference kit photo's back-of-shirt graphic
      const BADGE_PTS = [[0, -1], [0.68, -0.72], [0.95, -0.05], [0.66, 0.7], [0, 0.98], [-0.7, 0.66], [-0.94, -0.08], [-0.62, -0.74]]
      const BADGE_EDGES = [[0, 1], [1, 2], [2, 3], [3, 4], [4, 5], [5, 6], [6, 7], [7, 0], [0, 3], [1, 4], [2, 5], [3, 6], [0, 5]]
      const shirtBadge = () => {
        const mid = lerpPt(chest, waist, 0.58)
        const angT = Math.atan2(waist[1] - chest[1], waist[0] - chest[0]) - Math.PI / 2
        const rad = 0.052 * fh
        if (rad < 3) return
        const pt = (i) => [BADGE_PTS[i][0] * rad, BADGE_PTS[i][1] * rad]
        g.save()
        g.translate(mid[0], mid[1])
        g.rotate(angT)
        g.globalCompositeOperation = 'lighter'
        g.strokeStyle = 'rgba(120,240,225,0.5)'
        g.lineWidth = Math.max(0.5, rad * 0.045)
        for (const [a, b] of BADGE_EDGES) {
          const [ax, ay] = pt(a)
          const [bx, by] = pt(b)
          g.beginPath(); g.moveTo(ax, ay); g.lineTo(bx, by); g.stroke()
        }
        for (let i = 0; i < BADGE_PTS.length; i++) {
          const [x, y] = pt(i)
          const rg = g.createRadialGradient(x, y, 0, x, y, rad * 0.22)
          rg.addColorStop(0, 'rgba(200,255,245,0.85)')
          rg.addColorStop(1, 'rgba(0,224,198,0)')
          g.fillStyle = rg
          g.beginPath(); g.arc(x, y, rad * 0.22, 0, 7); g.fill()
        }
        const cg = g.createRadialGradient(0, 0, 0, 0, 0, rad * 0.55)
        cg.addColorStop(0, 'rgba(230,255,250,0.95)')
        cg.addColorStop(0.4, 'rgba(0,224,198,0.5)')
        cg.addColorStop(1, 'rgba(0,224,198,0)')
        g.fillStyle = cg
        g.beginPath(); g.arc(0, 0, rad * 0.55, 0, 7); g.fill()
        g.globalCompositeOperation = 'source-over'
        g.restore()
      }
      const headDraw = () => {
        limb(neck, head, 0.02, 0.016, KIT.skin[0]) // neck
        const r = 0.042 * fh
        // skull biased toward the jaw so it stays seated on the neck even
        // when the crown swings with the head-tracking tilt
        const cx = head[0] + (headTop[0] - head[0]) * 0.3
        const cy = head[1] + (headTop[1] - head[1]) * 0.3
        const aC = Math.atan2(headTop[1] - head[1], headTop[0] - head[0])
        // face direction: the +x side of the crown axis (he faces the ball)
        const s = Math.cos(aC + Math.PI / 2) >= 0 ? 1 : -1
        // jaw/chin wedge hung forward-down off the cranium
        const jd = aC + Math.PI - s * 1.05
        const chin = [cx + Math.cos(jd) * r * 1.15, cy + Math.sin(jd) * r * 1.15]
        capsule(cx, cy, chin[0], chin[1], r * 0.78, r * 0.32, KIT.skin[0])
        g.fillStyle = crossGrad(head, headTop, r, KIT.skin[0])
        g.beginPath(); g.arc(cx, cy, r, 0, 7); g.fill() // cranium
        // hair crescent over the top-back of the skull, rotating with tilt
        g.strokeStyle = KIT.hair
        g.lineWidth = r * 0.5
        g.beginPath()
        g.arc(cx, cy, r * 0.82, aC - s * 1.9, aC + s * 0.55, s < 0)
        g.stroke()
      }

      // teal rim light on the whole figure — kept subtle so shapes stay crisp
      g.shadowColor = 'rgba(0,224,198,0.26)'
      g.shadowBlur = 6 * (fh / 350)
      // far side first (shaded), then trunk, near side on top
      arm(shB, elB, haB, 1)
      leg(hipB, knB, anB, toB, 1)
      torso()
      wordmark()
      shirtBadge()
      headDraw()
      leg(hipF, knF, anF, toF, 0)
      arm(shF, elF, haF, 0)
      g.shadowBlur = 0
      g.restore()

      // materialise sparks converging onto the body
      if (t < MATERIALIZE + 0.35) {
        g.globalCompositeOperation = 'lighter'
        for (const sp of sparks) {
          const p = clamp01((t - sp.delay) / 0.5)
          if (p <= 0 || p >= 1) continue
          const target = pts[sp.j]
          const tx = target[0] + sp.jx * fh
          const ty = target[1] + sp.jy * fh
          const d0 = sp.dist * Math.min(L.w, L.h)
          const e = easeOutCubic(p)
          const x = tx + Math.cos(sp.ang) * d0 * (1 - e)
          const y = ty + Math.sin(sp.ang) * d0 * (1 - e)
          g.fillStyle = `rgba(0,224,198,${(Math.sin(Math.PI * p) * 0.7).toFixed(3)})`
          g.beginPath(); g.arc(x, y, 1.4, 0, 7); g.fill()
        }
        g.globalCompositeOperation = 'source-over'
      }
    }

    const drawGround = (t, L) => {
      const a0 = t < TL.fadeOutAt ? 1 : clamp01(1 - (t - TL.fadeOutAt) / 0.6)
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

    /* ball centre/radius as a pure function of time — lets the trail and
       motion-blur ghosts sample the true path (works under ?introt too) */
    const ballState = (t, L) => {
      const r0 = Math.max(9, L.fh * 0.052)
      if (t < TL.contactAt) return { x: L.ballGX, y: L.groundY - r0, r: r0, e: 0 }
      const p = clamp01((t - TL.contactAt) / (TL.flightEnd - TL.contactAt))
      const e = 1 - Math.pow(1 - p, 3.2)
      const x0 = L.ballGX
      const y0 = L.groundY - r0
      const cx = x0 + (L.ballFX - x0) * 0.5
      const cy = Math.min(y0, L.ballFY) - Math.max(80, L.h * 0.1)
      const v = 1 - e
      return {
        x: v * v * x0 + 2 * v * e * cx + e * e * L.ballFX,
        y: v * v * y0 + 2 * v * e * cy + e * e * L.ballFY,
        r: r0 + (L.ballFR - r0) * e,
        e,
      }
    }

    const drawBall = (t, dt, L) => {
      if (t < 0.55) return
      const appear = clamp01((t - 0.55) / 0.35)
      const B = ballState(t, L)
      if (B.e > 0 && B.e < 1) ballRot += dt * (15 * (1 - B.e) + 0.12)
      // canvas ball hands over to the DOM logo's own rotating ball
      const A = appear * (1 - clamp01((t - (TL.logoFadeAt + 0.12)) / 0.35))

      g.globalCompositeOperation = 'lighter'
      // light trail: sampled from the true path just behind the ball
      if (B.e > 0.01 && B.e < 0.97 && A > 0.02) {
        for (let k = 1; k <= 9; k++) {
          const Bp = ballState(t - k * 0.022, L)
          const Bq = ballState(t - (k - 1) * 0.022, L)
          const f = 1 - k / 10
          g.strokeStyle = `rgba(0,224,198,${(f * 0.45 * A).toFixed(3)})`
          g.lineWidth = Math.max(0.6, B.r * 0.55 * f)
          g.lineCap = 'round'
          g.beginPath(); g.moveTo(Bp.x, Bp.y); g.lineTo(Bq.x, Bq.y); g.stroke()
        }
      }
      if (A > 0.01) {
        const gr = g.createRadialGradient(B.x, B.y, 0, B.x, B.y, B.r * 2.1)
        gr.addColorStop(0, `rgba(0,224,198,${(0.4 * A).toFixed(3)})`)
        gr.addColorStop(1, 'rgba(0,224,198,0)')
        g.fillStyle = gr
        g.beginPath(); g.arc(B.x, B.y, B.r * 2.1, 0, 7); g.fill()
      }
      // impact: quick ring + dust burst off the turf
      if (t >= TL.contactAt && t < TL.contactAt + 0.2) {
        const q = (t - TL.contactAt) / 0.2
        g.strokeStyle = `rgba(180,255,240,${((1 - q) * 0.6).toFixed(3)})`
        g.lineWidth = 2 * (1 - q) + 0.5
        g.beginPath(); g.arc(L.ballGX, L.groundY - B.r, B.r * (1 + q * 2.2), 0, 7); g.stroke()
      }
      if (t >= TL.contactAt && t < TL.contactAt + 0.5) {
        const dT = t - TL.contactAt
        for (const d of dust) {
          const a = (1 - dT / 0.5) * 0.55
          if (a <= 0.02) continue
          const x = L.ballGX + Math.cos(d.ang) * d.spd * dT * L.fh
          const y = L.groundY - 4 + Math.sin(d.ang) * d.spd * dT * L.fh + 0.9 * L.fh * dT * dT
          g.fillStyle = `rgba(140,230,215,${a.toFixed(3)})`
          g.beginPath(); g.arc(x, y, d.size, 0, 7); g.fill()
        }
      }
      // landing ripple as the ball settles into the P
      if (t >= TL.flightEnd && t < TL.flightEnd + 0.45) {
        const q = (t - TL.flightEnd) / 0.45
        g.strokeStyle = `rgba(0,224,198,${((1 - q) * 0.45).toFixed(3)})`
        g.lineWidth = 1.4 * (1 - q) + 0.3
        g.beginPath(); g.arc(L.ballFX, L.ballFY, L.ballFR * (1 + q * 1.2), 0, 7); g.stroke()
      }
      g.globalCompositeOperation = 'source-over'

      if (A > 0.01) {
        // motion-blur ghosts trailing the ball mid-flight
        if (B.e > 0.03 && B.e < 0.9 && ballImg.complete && ballImg.naturalWidth) {
          for (let k = 3; k >= 1; k--) {
            const Bp = ballState(t - k * 0.03, L)
            if (Bp.e <= 0.001) continue // never ghost the pre-kick ball
            g.save()
            g.globalAlpha = A * (0.2 - k * 0.05)
            g.translate(Bp.x, Bp.y)
            g.rotate(ballRot - k * 0.1)
            g.drawImage(ballImg, -Bp.r, -Bp.r, Bp.r * 2, Bp.r * 2)
            g.restore()
          }
        }
        g.save()
        g.globalAlpha = A
        g.translate(B.x, B.y)
        // contact squash along the launch direction
        if (t >= TL.contactAt && t < TL.contactAt + 0.12) {
          const q = Math.sin((Math.PI * (t - TL.contactAt)) / 0.12)
          g.rotate(-0.6)
          g.scale(1 + q * 0.12, 1 - q * 0.2)
          g.rotate(0.6)
        }
        g.rotate(ballRot)
        if (ballImg.complete && ballImg.naturalWidth) {
          g.drawImage(ballImg, -B.r, -B.r, B.r * 2, B.r * 2)
        } else {
          g.strokeStyle = 'rgba(0,224,198,.9)'
          g.lineWidth = 1.2
          g.beginPath(); g.arc(0, 0, B.r, 0, 7); g.stroke()
          g.beginPath(); g.ellipse(0, 0, B.r, B.r * 0.45, 0, 0, 7); g.stroke()
          g.beginPath(); g.ellipse(0, 0, B.r * 0.45, B.r, 0, 0, 7); g.stroke()
        }
        g.restore()
      }
    }

    const drawMesh = (t, L) => {
      if (t < TL.meshAt) return
      const meshA = 1 - clamp01((t - (TL.logoFadeAt + 0.35)) / 0.35)
      if (meshA <= 0) return
      const fw = L.fullW
      const px = (i) => L.left + (ND[i][0] - OFFSET_X_FRAC) * fw
      const py = (i) => L.top + (ND[i][1] - OFFSET_Y_FRAC) * fw
      g.globalCompositeOperation = 'lighter'
      for (const [a, b] of ED) {
        const st = Math.max(popT[a], popT[b]) + 0.04
        const q = easeOutCubic(clamp01((t - st) / 0.25))
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
        const p = clamp01((t - popT[i]) / 0.2)
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
      drawPlayer(t, L)
      drawBall(t, dt, L)
      drawMesh(t, L)
      logoEl.style.opacity = String(clamp01((t - TL.logoFadeAt) / 0.35))
      // spring settle as the logo takes over from the landed ball
      const sd = t - (TL.logoFadeAt + 0.2)
      if (sd > 0 && sd < 1.2) {
        const sc = 1 + 0.05 * Math.exp(-4.5 * sd) * Math.sin(11 * sd)
        settleEl.style.transform = `scale(${sc.toFixed(4)})`
      }
      const tf = easeOutCubic(clamp01((t - TL.textAt) / 0.4))
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
        <div ref={settleRef} style={{ width: '100%', height: '100%', transformOrigin: '50% 50%' }}>
          <LogoMark size={layout.s} glow={false} />
        </div>
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
      {/* visible skip affordance — any click/tap/keypress skips too */}
      <div
        style={{
          position: 'absolute',
          right: 22,
          bottom: 18,
          fontFamily: 'var(--font-mono)',
          fontSize: 11,
          letterSpacing: '.22em',
          color: 'rgba(255,255,255,.35)',
          cursor: 'pointer',
          userSelect: 'none',
        }}
      >
        SKIP ›
      </div>
    </div>
  )
}
