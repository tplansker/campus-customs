// "Campus Customs Online, est. 1996": retro web decorations (Problem 10).
// Everything animated is switched off for prefers-reduced-motion (see retro.css + Sparkles).
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import Bulldog from './Bulldog'

const MARQUEE_ITEMS = [
  '★ WELCOME TO CAMPUS CUSTOMS ON THE WORLD WIDE WEB ★',
  'BOOLA BOOLA!',
  '★ NEW!!! CHAT WITH HANDSOME DAN, THE BULLDOG WHO KNOWS EVERY SIZE IN STOCK ★',
  '100% HARVARD-FREE ZONE 🚫',
  '★ HOODIES ★ CREWNECKS ★ TEES ★ QUARTER-ZIPS ★',
  'FREE BULLDOG PRIDE WITH EVERY PURCHASE',
  '★ BEAT HARVARD! ★',
]

export function Marquee() {
  const text = MARQUEE_ITEMS.join('   ·   ')
  return (
    <div className="marquee" role="note" aria-label="Campus Customs news">
      <div className="marquee-track" aria-hidden="true">
        <span>{text}</span>
        <span>{text}</span>
      </div>
      <span className="sr-only">{MARQUEE_ITEMS.join('. ')}</span>
    </div>
  )
}

// Real visitor count from the backend (one hit per browser session).
export function HitCounter() {
  const [count, setCount] = useState<number | null>(null)

  useEffect(() => {
    let counted = false
    try {
      counted = sessionStorage.getItem('cc_counted') === '1'
    } catch {
      /* storage blocked: just count again */
    }
    fetch('/api/visits', { method: counted ? 'GET' : 'POST' })
      .then((r) => r.json())
      .then((d: { visits: number }) => {
        setCount(d.visits)
        try {
          sessionStorage.setItem('cc_counted', '1')
        } catch {
          /* ignore */
        }
      })
      .catch(() => setCount(null))
  }, [])

  const digits = String(count ?? 0).padStart(7, '0')
  return (
    <p className="hit-counter">
      You are visitor #
      <span className="odometer" aria-label={count === null ? 'loading' : String(count)}>
        {digits.split('').map((d, i) => (
          <span key={i}>{d}</span>
        ))}
      </span>
      since 1996*
    </p>
  )
}

// Yellow comic-book starburst for prices and shouts.
export function StarBurst({ children, size = 'md' }: { children: ReactNode; size?: 'sm' | 'md' | 'lg' }) {
  return (
    <span className={`starburst starburst-${size}`}>
      <span>{children}</span>
    </span>
  )
}

// Little Yale-blue and gold stars that trail the mouse, like every good 1996 homepage.
export function Sparkles() {
  const last = useRef(0)
  useEffect(() => {
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    const touch = window.matchMedia('(pointer: coarse)').matches
    if (reduce || touch) return
    const glyphs = ['✦', '★', '✧', '·']
    function onMove(e: MouseEvent) {
      const now = performance.now()
      if (now - last.current < 45) return
      last.current = now
      const s = document.createElement('span')
      s.className = 'sparkle'
      s.textContent = glyphs[Math.floor(Math.random() * glyphs.length)]
      s.style.left = `${e.clientX}px`
      s.style.top = `${e.clientY}px`
      s.style.setProperty('--dx', `${(Math.random() - 0.5) * 30}px`)
      document.body.appendChild(s)
      window.setTimeout(() => s.remove(), 800)
    }
    window.addEventListener('mousemove', onMove)
    return () => window.removeEventListener('mousemove', onMove)
  }, [])
  return null
}

// Easter egg: "Harvard Mode" turns the site crimson... until Handsome Dan objects.
function HarvardMode() {
  const [phase, setPhase] = useState<'off' | 'crimson' | 'woof'>('off')

  useEffect(() => {
    document.body.classList.toggle('harvard-mode', phase === 'crimson')
    if (phase === 'crimson') {
      const t = window.setTimeout(() => setPhase('woof'), 1400)
      return () => window.clearTimeout(t)
    }
    if (phase === 'woof') {
      const t = window.setTimeout(() => setPhase('off'), 2600)
      return () => window.clearTimeout(t)
    }
  }, [phase])

  return (
    <>
      <button
        type="button"
        className="retro-btn harvard-btn"
        onClick={() => setPhase('crimson')}
        disabled={phase !== 'off'}
      >
        Switch to Harvard Mode?
      </button>
      {phase === 'woof' && (
        <div className="woof-overlay" role="alert">
          <div className="woof-card">
            <Bulldog size={110} />
            <StarBurst size="lg">WOOF!</StarBurst>
            <p>
              <strong>Harvard Mode blocked by Handsome Dan.</strong>
              <br />
              This is a crimson-free zone. Boola Boola!
            </p>
          </div>
        </div>
      )}
    </>
  )
}

export function RetroFooter() {
  return (
    <footer className="site-footer retro-footer">
      <div className="footer-row">
        <HitCounter />
      </div>

      <div className="webring" aria-label="Ivy League Webring (just for fun)">
        <span className="webring-arrow">« prev</span>
        <span className="webring-title">⚡ The Ivy League WebRing ⚡</span>
        <span className="webring-arrow">next »</span>
        <span className="webring-blocked" title="Nice try.">
          <s>Harvard</s> (blocked by webmaster)
        </span>
      </div>

      <div className="footer-badges" aria-hidden="true">
        <span className="badge88">
          Best viewed in
          <br />
          <b>Netscape 3.0</b>
        </span>
        <span className="badge88 badge88-alt">
          800 × 600
          <br />
          <b>256 COLORS</b>
        </span>
        <span className="badge88 badge88-crimson">
          🚫 NO
          <br />
          <b>CRIMSON</b>
        </span>
        <span className="badge88">
          Made with
          <br />
          <b>Notepad ♥</b>
        </span>
      </div>

      <div className="footer-row">
        <HarvardMode />
      </div>

      <p className="footer-legal">
        <strong className="footer-cheer">Boola Boola!</strong> · © Campus Customs · New Haven, CT ·{' '}
        <Link to="/about">About us</Link> · <Link to="/products">Shop</Link>
        <br />
        <small>*Hit counter is real; our 1996 launch date is a fond fiction.</small>
      </p>
    </footer>
  )
}
