import { useEffect, useRef, useState } from 'react'

/* 0→1 cubic-ease-out tween driving the count-up bars, matching the
   prototype's rAF tween (1300ms default). `key` restarts the animation. */
export default function useTween(duration = 1300, key = 0) {
  const [p, setP] = useState(0)
  const raf = useRef(null)
  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      setP(1)
      return
    }
    setP(0)
    const t0 = performance.now()
    const ease = (x) => 1 - Math.pow(1 - x, 3)
    const step = (now) => {
      const t = Math.min(1, (now - t0) / duration)
      setP(ease(t))
      if (t < 1) raf.current = requestAnimationFrame(step)
    }
    raf.current = requestAnimationFrame(step)
    return () => cancelAnimationFrame(raf.current)
  }, [duration, key])
  return p
}
