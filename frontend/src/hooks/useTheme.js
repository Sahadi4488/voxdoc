import { useEffect, useState } from 'react'
import { applyTheme, loadTheme, saveTheme, systemDark } from '../lib/theme'

/** [theme, setTheme]: 'system' | 'light' | 'dark', saved, and applied to <html>. */
export function useTheme() {
  const [theme, setTheme] = useState(loadTheme)

  useEffect(() => {
    applyTheme(theme)
    saveTheme(theme)
    if (theme !== 'system') return
    // "System" keeps following the OS setting while the page is open
    const media = systemDark()
    const onChange = () => applyTheme('system')
    media.addEventListener('change', onChange)
    return () => media.removeEventListener('change', onChange)
  }, [theme])

  return [theme, setTheme]
}
