import { useCallback, useEffect, useState } from 'react'
import { applyTheme, loadTheme, saveTheme, systemDark } from '../lib/theme'

/**
 * { theme, setTheme, resolved, toggle }
 * theme: 'system' | 'light' | 'dark', saved and applied to <html>.
 * resolved: what the page shows right now, 'light' or 'dark'.
 * toggle(): switch to the opposite of what is showing.
 */
export function useTheme() {
  const [theme, setTheme] = useState(loadTheme)
  const [systemIsDark, setSystemIsDark] = useState(() => systemDark().matches)

  // "System" keeps following the OS setting while the page is open
  useEffect(() => {
    const media = systemDark()
    const onChange = () => setSystemIsDark(media.matches)
    media.addEventListener('change', onChange)
    return () => media.removeEventListener('change', onChange)
  }, [])

  useEffect(() => {
    applyTheme(theme)
    saveTheme(theme)
  }, [theme, systemIsDark])

  const resolved = theme === 'system' ? (systemIsDark ? 'dark' : 'light') : theme
  const toggle = useCallback(() => setTheme(resolved === 'dark' ? 'light' : 'dark'), [resolved])
  return { theme, setTheme, resolved, toggle }
}
