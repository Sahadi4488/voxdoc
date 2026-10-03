import { useTheme } from '../hooks/useTheme'
import { focusRing } from '../lib/styles'

/** System / Light / Dark, as a native select: keyboard and screen-reader support built in. */
export default function ThemePicker() {
  const [theme, setTheme] = useTheme()
  return (
    <label className="flex items-baseline gap-2 text-sm text-graphite">
      Theme
      <select
        value={theme}
        onChange={(e) => setTheme(e.target.value)}
        className={`cursor-pointer rounded-md border border-rule bg-paper px-2 py-1 text-ink ${focusRing}`}
      >
        <option value="system">System</option>
        <option value="light">Light</option>
        <option value="dark">Dark</option>
      </select>
    </label>
  )
}
