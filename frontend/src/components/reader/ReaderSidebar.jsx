import { memo, useRef, useState } from 'react'
import { useDismiss } from '../../hooks/useDismiss'
import Icon from '../ui/Icon'
import { useReader } from './ReaderContext'

const SIZES = { s: 'Small', m: 'Medium', l: 'Large' }
const THEMES = { system: 'System', light: 'Light', dark: 'Dark' }

function Item({ ref, icon, label, collapsed, ...rest }) {
  return (
    <button
      ref={ref}
      type="button"
      className="vd-side-item"
      title={collapsed ? label : undefined}
      aria-label={collapsed ? label : undefined}
      {...rest}
    >
      <Icon name={icon} />
      <span className="vd-sidebar-label">{label}</span>
    </button>
  )
}

function Segmented({ label, options, value, onChange, renderOption }) {
  return (
    <div className="vd-setting-row">
      <span id={`vd-set-${label}`}>{label}</span>
      <div className="vd-segmented" role="group" aria-labelledby={`vd-set-${label}`}>
        {Object.entries(options).map(([key, name]) => (
          <button type="button" key={key} aria-pressed={value === key} onClick={() => onChange(key)} aria-label={name}>
            {renderOption ? renderOption(key, name) : name}
          </button>
        ))}
      </div>
    </div>
  )
}

/**
 * Narrow and quiet: Document / Summary / Ask, the contents, and settings.
 * Memoised: ReaderPage re-renders on every spoken word, this only when its props change.
 */
function ReaderSidebar({ view, onViewChange, askOpen, onToggleAsk, askItemRef, askPanelId, toc, activeTocIdx, onTocSelect, onHome, onNewDocument, theme }) {
  const { collapsed, toggleCollapsed, closeDrawer, inDrawer, font, setFont, size, setSize } = useReader()
  const [settingsOpen, setSettingsOpen] = useState(false)
  const settingsRef = useRef(null)
  const settingsBtnRef = useRef(null)
  useDismiss(settingsRef, settingsOpen, (viaEscape) => {
    setSettingsOpen(false)
    if (viaEscape) settingsBtnRef.current?.focus()
  })
  const showLabels = !collapsed || inDrawer

  // In the drawer, an action closes it first
  const go = (fn) => () => {
    closeDrawer()
    fn()
  }

  return (
    <aside className="vd-sidebar" id="vd-sidebar" aria-label="Reader navigation">
      <div className="vd-sidebar-top">
        <button type="button" className="vd-logo" onClick={go(onHome)} aria-label="VoxDoc home">
          <span className="vd-logo-mark" aria-hidden="true" />
          <span className="vd-logo-text">VoxDoc</span>
        </button>
        <button
          type="button"
          className="vd-icon-btn vd-collapse-btn"
          onClick={toggleCollapsed}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          aria-expanded={!collapsed}
        >
          <Icon name="sidebar" size="sm" />
        </button>
      </div>

      <nav className="vd-sidebar-group" aria-label="Views">
        <Item
          collapsed={!showLabels}
          icon="doc"
          label="Document"
          aria-current={view === 'document' ? 'page' : undefined}
          onClick={go(() => onViewChange('document'))}
        />
        <Item
          collapsed={!showLabels}
          icon="summary"
          label="Summary"
          aria-current={view === 'summary' ? 'page' : undefined}
          onClick={go(() => onViewChange('summary'))}
        />
        <Item
          ref={askItemRef}
          collapsed={!showLabels}
          icon="ask"
          label="Ask document"
          aria-expanded={askOpen}
          aria-controls={askPanelId}
          onClick={go(onToggleAsk)}
        />
      </nav>

      {toc.length > 0 && (
        <>
          <div className="vd-sidebar-divider" />
          <p className="vd-sidebar-heading" id="vd-toc-heading">
            Contents
          </p>
          <ul className="vd-sidebar-toc" aria-labelledby="vd-toc-heading">
            {toc.map((t) => (
              <li key={t.idx}>
                <button
                  type="button"
                  className="vd-toc-item"
                  aria-current={t.idx === activeTocIdx ? 'true' : undefined}
                  onClick={go(() => onTocSelect(t.idx))}
                  title={t.label}
                >
                  {t.label}
                </button>
              </li>
            ))}
          </ul>
        </>
      )}

      <div className="vd-sidebar-bottom" ref={settingsRef}>
        <div className="vd-sidebar-divider" />
        <Item collapsed={!showLabels} icon="plus" label="New document" onClick={go(onNewDocument)} />
        <Item
          collapsed={!showLabels}
          icon={theme.resolved === 'dark' ? 'sun' : 'moon'}
          label={theme.resolved === 'dark' ? 'Light mode' : 'Dark mode'}
          onClick={theme.toggle}
        />
        <Item
          ref={settingsBtnRef}
          collapsed={!showLabels}
          icon="settings"
          label="Settings"
          aria-expanded={settingsOpen}
          aria-controls="vd-settings"
          onClick={() => setSettingsOpen((o) => !o)}
        />

        {settingsOpen && (
          <div
            id="vd-settings"
            className="vd-popover vd-popover--up vd-popover--start"
            role="dialog"
            aria-label="Reading settings"
            style={{ width: 280 }}
          >
            <p className="vd-popover-title">Reading</p>
            <Segmented
              label="Typeface"
              options={{ sans: 'Sans', serif: 'Serif' }}
              value={font}
              onChange={setFont}
              renderOption={(key, name) => (
                <span style={key === 'serif' ? { fontFamily: 'var(--vd-font-reading-serif)' } : undefined}>{name}</span>
              )}
            />
            <Segmented
              label="Text size"
              options={SIZES}
              value={size}
              onChange={setSize}
              renderOption={(key) => <span style={{ fontSize: { s: 12, m: 14, l: 16 }[key] }}>A</span>}
            />
            <Segmented label="Theme" options={THEMES} value={theme.theme} onChange={theme.setTheme} />
          </div>
        )}
      </div>
    </aside>
  )
}

export default memo(ReaderSidebar)
