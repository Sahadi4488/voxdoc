import { useEffect, useId, useRef, useState } from 'react'
import { useDismiss } from '../../hooks/useDismiss'
import { formatSpeed, MAX_SPEED, MIN_SPEED, roundSpeed, SPEED_STEP } from '../../lib/prefs'

const PRESET_SPEEDS = [0.8, 0.9, 1, 1.1, 1.25, 1.5, 1.75, 2]
const COMMIT_MS = 400 // the slider commits 400 ms after the last change, not on every step

/** The "1.0×" chip: common speeds one tap away, and a fine slider for anything between. */
export default function SpeedPicker({ speed, onSpeedChange }) {
  const [open, setOpen] = useState(false)
  const wrapRef = useRef(null)
  const triggerRef = useRef(null)
  const popoverId = useId()
  const sliderId = useId()

  // The label follows the slider at once; the value commits after a pause
  const [draft, setDraft] = useState(speed)
  const [shownSpeed, setShownSpeed] = useState(speed)
  if (speed !== shownSpeed) {
    // e.g. picking a voice loaded its default speed: follow it
    setShownSpeed(speed)
    setDraft(speed)
  }
  useEffect(() => {
    if (draft === speed) return // nothing to commit (also on mount)
    const t = setTimeout(() => onSpeedChange(draft), COMMIT_MS)
    return () => clearTimeout(t) // each new step cancels the pending commit
  }, [draft, speed, onSpeedChange])

  useDismiss(wrapRef, open, (viaEscape) => {
    setOpen(false)
    if (viaEscape) triggerRef.current?.focus()
  })

  const pct = ((draft - MIN_SPEED) / (MAX_SPEED - MIN_SPEED)) * 100
  return (
    <div className="vd-popover-anchor" ref={wrapRef}>
      <button
        ref={triggerRef}
        type="button"
        className="vd-chip-btn"
        aria-expanded={open}
        aria-controls={popoverId}
        aria-label={`Speed ${formatSpeed(draft)}`}
        onClick={() => setOpen((o) => !o)}
      >
        {formatSpeed(draft)}
      </button>

      {open && (
        <div id={popoverId} className="vd-popover vd-popover--up vd-popover--end" role="dialog" aria-label="Playback speed" style={{ width: 280 }}>
          <p className="vd-popover-title">Speed</p>
          <div className="vd-speed-grid">
            {PRESET_SPEEDS.map((s) => (
              <button
                type="button"
                key={s}
                className="vd-option"
                aria-pressed={s === draft}
                onClick={() => {
                  setDraft(s)
                  onSpeedChange(s) // a tap is deliberate: no need to wait
                }}
              >
                {formatSpeed(s)}
              </button>
            ))}
          </div>
          <div className="vd-speed-fine">
            <label htmlFor={sliderId}>
              Fine-tune <output htmlFor={sliderId}>{formatSpeed(draft)}</output>
            </label>
            <input
              id={sliderId}
              className="vd-range"
              type="range"
              min={MIN_SPEED}
              max={MAX_SPEED}
              step={SPEED_STEP}
              value={draft}
              style={{ '--vd-pct': `${pct}%` }}
              onChange={(e) => setDraft(roundSpeed(Number(e.target.value)))} // a string, with float noise
            />
          </div>
        </div>
      )}
    </div>
  )
}
