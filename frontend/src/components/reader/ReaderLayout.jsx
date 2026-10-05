import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import Icon from '../ui/Icon'
import { ReaderContext } from './ReaderContext'

const PREFS_KEY = 'voxdoc:reader'
const DRAWER_MAX = '(max-width: 900px)' // the sidebar becomes a drawer below this (voxdoc.css)

function loadPrefs() {
  try {
    const p = JSON.parse(localStorage.getItem(PREFS_KEY) ?? '{}') ?? {}
    return {
      font: p.font === 'serif' ? 'serif' : 'sans',
      size: ['s', 'm', 'l'].includes(p.size) ? p.size : 'm',
      collapsed: p.collapsed === true,
    }
  } catch {
    return { font: 'sans', size: 'm', collapsed: false } // corrupt, or storage blocked
  }
}

/**
 * The reader's shell: sidebar on the left (a drawer on small screens), the page in
 * the middle, the floating player, and the Ask panel on the right.
 * focus: true while audio plays, so the sidebar steps back (Focus Mode).
 */
export default function ReaderLayout({ title, sidebar, player, panel, panelOpen, focus, askOpen, onToggleAsk, mobileAskRef, children }) {
  const [prefs, setPrefs] = useState(loadPrefs)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const menuBtnRef = useRef(null)

  useEffect(() => {
    try {
      localStorage.setItem(PREFS_KEY, JSON.stringify(prefs))
    } catch {
      // not saved: the choice still applies until the page is closed
    }
  }, [prefs])

  const closeDrawer = useCallback((returnFocus = false) => {
    setDrawerOpen(false)
    if (returnFocus) menuBtnRef.current?.focus()
  }, [])

  // Open drawer: focus its first item; Escape closes it and returns to the menu button
  useEffect(() => {
    if (!drawerOpen) return
    document.querySelector('.vd-sidebar button')?.focus()
    const onKey = (e) => {
      if (e.key === 'Escape') closeDrawer(true)
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [drawerOpen, closeDrawer])

  // Growing past the drawer breakpoint closes the drawer, so it can't reappear later
  useEffect(() => {
    const media = window.matchMedia(DRAWER_MAX)
    const onChange = () => !media.matches && setDrawerOpen(false)
    media.addEventListener('change', onChange)
    return () => media.removeEventListener('change', onChange)
  }, [])

  const ctx = useMemo(
    () => ({
      collapsed: prefs.collapsed,
      toggleCollapsed: () => setPrefs((p) => ({ ...p, collapsed: !p.collapsed })),
      font: prefs.font,
      setFont: (font) => setPrefs((p) => ({ ...p, font })),
      size: prefs.size,
      setSize: (size) => setPrefs((p) => ({ ...p, size })),
      inDrawer: drawerOpen,
      closeDrawer,
    }),
    [prefs, drawerOpen, closeDrawer],
  )

  return (
    <ReaderContext.Provider value={ctx}>
      <div
        className="vd-reader"
        data-collapsed={prefs.collapsed}
        data-drawer={drawerOpen}
        data-focus={focus && !drawerOpen}
        data-panel={panelOpen}
        data-font={prefs.font}
        data-size={prefs.size}
      >
        <div className="vd-mobile-bar">
          <button
            ref={menuBtnRef}
            type="button"
            className="vd-icon-btn"
            onClick={() => setDrawerOpen(true)}
            aria-label="Open navigation"
            aria-expanded={drawerOpen}
            aria-controls="vd-sidebar"
          >
            <Icon name="menu" />
          </button>
          <span className="vd-mobile-title">{title}</span>
          <button
            ref={mobileAskRef}
            type="button"
            className="vd-icon-btn"
            onClick={onToggleAsk}
            aria-label="Ask this document"
            aria-expanded={askOpen}
          >
            <Icon name="ask" />
          </button>
        </div>

        <div className="vd-drawer-scrim" onClick={() => closeDrawer(true)} aria-hidden="true" />
        {sidebar}

        <main className="vd-main" id="vd-reader-main">
          {children}
        </main>

        {player}
        {panel}
      </div>
    </ReaderContext.Provider>
  )
}
