import { useRef, useState } from 'react'
import { useDismiss } from '../../hooks/useDismiss'
import Icon from '../ui/Icon'

const LINKS = [
  { href: '#features', label: 'Features' },
  { href: '#how-it-works', label: 'How it works' },
  { href: '#voices', label: 'Voices' },
]

/** Small floating pill. Collapses into a menu sheet on phones. */
export default function Navbar({ onOpenReader, theme }) {
  const [menuOpen, setMenuOpen] = useState(false)
  const wrapRef = useRef(null)
  const menuBtnRef = useRef(null)
  useDismiss(wrapRef, menuOpen, (viaEscape) => {
    setMenuOpen(false)
    if (viaEscape) menuBtnRef.current?.focus()
  })
  const dark = theme.resolved === 'dark'

  return (
    <div ref={wrapRef}>
      <nav className="vd-nav" aria-label="Main">
        <a className="vd-logo" href="#top" aria-label="VoxDoc, back to top">
          <span className="vd-logo-mark" aria-hidden="true" />
          <span>VoxDoc</span>
        </a>

        <ul className="vd-nav-links">
          <li>
            <button type="button" className="vd-nav-link" onClick={onOpenReader}>
              Reader
            </button>
          </li>
          {LINKS.map((l) => (
            <li key={l.href}>
              <a className="vd-nav-link" href={l.href}>
                {l.label}
              </a>
            </li>
          ))}
        </ul>

        <div className="vd-nav-actions">
          <button
            type="button"
            className="vd-icon-btn"
            onClick={theme.toggle}
            aria-label={dark ? 'Switch to light mode' : 'Switch to dark mode'}
          >
            <Icon name={dark ? 'sun' : 'moon'} size="sm" />
          </button>
          <button type="button" className="vd-btn vd-btn--dark vd-btn--sm vd-nav-open-btn" onClick={onOpenReader}>
            Open Reader
          </button>
          <button
            ref={menuBtnRef}
            type="button"
            className="vd-icon-btn vd-nav-menu-btn"
            aria-label={menuOpen ? 'Close menu' : 'Open menu'}
            aria-expanded={menuOpen}
            aria-controls="vd-nav-sheet"
            onClick={() => setMenuOpen((o) => !o)}
          >
            <Icon name={menuOpen ? 'close' : 'menu'} />
          </button>
        </div>
      </nav>

      {menuOpen && (
        <div id="vd-nav-sheet" className="vd-nav-sheet">
          {LINKS.map((l) => (
            <a key={l.href} href={l.href} onClick={() => setMenuOpen(false)}>
              {l.label}
            </a>
          ))}
          <button
            type="button"
            onClick={() => {
              setMenuOpen(false)
              onOpenReader()
            }}
          >
            Open Reader
          </button>
        </div>
      )}
    </div>
  )
}
