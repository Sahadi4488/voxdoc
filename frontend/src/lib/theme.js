// System / Light / Dark. The `dark` class on <html> switches the colour tokens
// (index.css). index.html applies the saved choice before the first paint with
// the same rule as applyTheme, so a dark page never flashes white while React loads.

const KEY = 'voxdoc:theme'
export const THEMES = ['system', 'light', 'dark']

export const systemDark = () => window.matchMedia('(prefers-color-scheme: dark)')

export function loadTheme() {
  try {
    const saved = localStorage.getItem(KEY)
    return THEMES.includes(saved) ? saved : 'system'
  } catch {
    return 'system' // storage blocked (private mode, sandboxed preview)
  }
}

export function saveTheme(theme) {
  try {
    localStorage.setItem(KEY, theme)
  } catch {
    // not saved: the choice still applies until the page is closed
  }
}

export function applyTheme(theme) {
  const dark = theme === 'dark' || (theme === 'system' && systemDark().matches)
  document.documentElement.classList.toggle('dark', dark)
}
