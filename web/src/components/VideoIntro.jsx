import { useEffect, useRef, useState } from 'react'
import LogoMark, { CROP_FRAC, OFFSET_X_FRAC, OFFSET_Y_FRAC } from './LogoMark.jsx'
import CinematicIntro, { INTRO_SEEN_KEY } from './CinematicIntro.jsx'

/*
  Video boot intro — the Higgsfield-generated brand film (a footballer in the
  PARKER AI kit strikes a glowing ball that forms the constellation P logo).
  Used on desktop/landscape; App.jsx falls back to the canvas CinematicIntro
  on portrait/narrow viewports, and this component itself falls back if the
  video can't load or autoplay.

  The film was generated with the real logo art composited into its final
  frame (the 640px logo image drawn at (510, 90, 900, 900) inside 1920x1080 —
  see EF below), so we know exactly where the logo sits when the video ends.
  During the last ~0.6s the real <LogoMark> (with its live idle animation)
  crossfades in over the video's logo, then FLIP-glides onto the header
  logo's measured rect (#pk-header-logo) as the overlay fades and the site
  is revealed — identical handoff contract to the canvas intro.

  Behaviour contract (same as CinematicIntro): plays once ever (localStorage,
  marked on mount), header-logo click replays, any click/tap/keypress or the
  SKIP button jumps straight to the handoff, prefers-reduced-motion never
  reaches this component (gated in App.jsx), and a 15s hard cap means a
  stalled network can never trap the visitor.
*/

const VIDEO_SRC = '/parker-intro.mp4'
/* end-frame composition: where the full logo art sits in the video frame */
const EF = { x: 510, y: 90, size: 900, w: 1920, h: 1080 }

function logoLayout() {
  const vw = window.innerWidth
  const vh = window.innerHeight
  // must mirror the <video>'s object-fit: cover mapping
  const scale = Math.max(vw / EF.w, vh / EF.h)
  const ox = (vw - EF.w * scale) / 2
  const oy = (vh - EF.h * scale) / 2
  return {
    left: ox + (EF.x + OFFSET_X_FRAC * EF.size) * scale,
    top: oy + (EF.y + OFFSET_Y_FRAC * EF.size) * scale,
    s: CROP_FRAC * EF.size * scale,
  }
}

export default function VideoIntro({ onDone }) {
  const wrapRef = useRef(null)
  const fadeRef = useRef(null)
  const videoRef = useRef(null)
  const logoRef = useRef(null)
  const onDoneRef = useRef(onDone)
  onDoneRef.current = onDone
  const [layout, setLayout] = useState(logoLayout)
  const [fallback, setFallback] = useState(false)

  useEffect(() => {
    if (fallback) return undefined
    const wrap = wrapRef.current
    const video = videoRef.current
    const logoEl = logoRef.current
    const fadeEl = fadeRef.current
    if (!wrap || !video || !logoEl || !fadeEl) return undefined

    // "once ever" is marked as soon as the intro starts playing
    try {
      localStorage.setItem(INTRO_SEEN_KEY, '1')
    } catch (e) {
      /* ignore */
    }

    let handoff = false
    let doneTimer = null
    let capTimer = null
    const log = (m) => {
      if (import.meta.env.DEV) {
        window.__introLog = window.__introLog || []
        window.__introLog.push(`${(performance.now() / 1000).toFixed(2)}s ${m}`)
      }
    }
    log('effect mount')

    const onResize = () => setLayout(logoLayout())
    window.addEventListener('resize', onResize)

    const startHandoff = () => {
      if (handoff) return
      handoff = true
      log('startHandoff (video t=' + video.currentTime.toFixed(2) + ', ended=' + video.ended + ')')
      video.pause()
      logoEl.style.transition = 'opacity .25s ease'
      logoEl.style.opacity = '1'
      // synchronous style flush instead of requestAnimationFrame — rAF can
      // stop entirely in background tabs, which would strand the intro
      logoEl.getBoundingClientRect()
      const target = document.getElementById('pk-header-logo')
      if (target) {
        const tr = target.getBoundingClientRect()
        const lr = logoEl.getBoundingClientRect()
        if (tr.width > 0 && lr.width > 0) {
          logoEl.style.transition = 'opacity .25s ease, transform .8s cubic-bezier(.72,.02,.26,1)'
          logoEl.style.transform = `translate(${tr.left - lr.left}px, ${tr.top - lr.top}px) scale(${tr.width / lr.width})`
        }
      }
      fadeEl.style.transition = 'opacity .6s ease .15s'
      fadeEl.style.opacity = '0'
      doneTimer = setTimeout(() => onDoneRef.current(), 900)
    }

    const skip = (e) => {
      log('skip via ' + (e ? e.type : '?'))
      startHandoff()
    }
    window.addEventListener('keydown', skip)
    wrap.addEventListener('pointerdown', skip)

    const onTime = () => {
      if (handoff) return
      const d = video.duration
      if (!d || !isFinite(d)) return
      // crossfade the real alive logo over the video's finished logo so the
      // idle animation (twinkle, pulses, rotating ball) takes over seamlessly
      const f = Math.min(1, Math.max(0, (video.currentTime - (d - 0.7)) / 0.55))
      logoEl.style.opacity = String(f)
    }
    const onEnded = () => {
      log('ended event')
      startHandoff()
    }
    const onError = () => {
      if (import.meta.env.DEV) window.__introVideoErr = 'element error: ' + (video.error ? `${video.error.code} ${video.error.message}` : 'unknown')
      setFallback(true)
    }
    video.addEventListener('timeupdate', onTime)
    video.addEventListener('ended', onEnded)
    video.addEventListener('error', onError)
    // Autoplay handling: a real NotAllowedError (autoplay policy) falls back
    // to the canvas intro; an AbortError from Chrome pausing video-only
    // media in background tabs is retried — immediately once, and whenever
    // the tab becomes visible. The 15s cap below is the final safety net.
    let retried = false
    const tryPlay = () => {
      if (handoff) return
      const p = video.play()
      if (p && p.catch) {
        p.catch((e) => {
          if (import.meta.env.DEV) window.__introVideoErr = 'play rejected: ' + e.name + ' ' + e.message
          if (e && e.name === 'NotAllowedError') setFallback(true)
          else if (!retried) {
            retried = true
            setTimeout(tryPlay, 400)
          }
        })
      }
    }
    const onVisibility = () => {
      if (!document.hidden && video.paused && !handoff) tryPlay()
    }
    document.addEventListener('visibilitychange', onVisibility)
    tryPlay()
    // hard cap: never trap the visitor behind a stalled download or a
    // browser that refuses to run the video
    capTimer = setTimeout(startHandoff, 15000)

    return () => {
      window.removeEventListener('resize', onResize)
      window.removeEventListener('keydown', skip)
      wrap.removeEventListener('pointerdown', skip)
      document.removeEventListener('visibilitychange', onVisibility)
      video.removeEventListener('timeupdate', onTime)
      video.removeEventListener('ended', onEnded)
      video.removeEventListener('error', onError)
      if (doneTimer) clearTimeout(doneTimer)
      if (capTimer) clearTimeout(capTimer)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fallback])

  if (fallback) return <CinematicIntro onDone={onDone} />

  return (
    <div ref={wrapRef} style={{ position: 'fixed', inset: 0, zIndex: 60, overflow: 'hidden' }}>
      <div ref={fadeRef} style={{ position: 'absolute', inset: 0, background: 'var(--bg)' }}>
        <video
          ref={videoRef}
          src={VIDEO_SRC}
          muted
          playsInline
          preload="auto"
          style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover' }}
        />
      </div>
      {/* the real alive logo, crossfaded over the video's final frame, then
          FLIP-glided onto the header logo */}
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
