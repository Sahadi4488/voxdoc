import { useEffect, useState } from 'react'
import Icon from '../ui/Icon'

const SEEK_COMMIT_MS = 300 // dragging the bar plays where it stops, not every sentence passed

/**
 * The floating player. One set of controls for every width: on phones the CSS
 * hides previous/next and shows the title instead (voxdoc.css, .vd-player-row).
 */
export default function PlayerBar({ ref, player, sentenceCount, ready, notice, title, voiceControl, speedControl }) {
  const { status, currentIdx, error, playFrom } = player
  const playing = status === 'playing'
  const loading = status === 'loading'
  const last = Math.max(sentenceCount - 1, 0)

  // "Preparing audio…" only once loading the current sentence has lasted
  // 300 ms, so a prefetched clip doesn't make the text flash for a split second.
  const [slowIdx, setSlowIdx] = useState(null)
  useEffect(() => {
    if (!loading) return
    const t = setTimeout(() => setSlowIdx(currentIdx), 300)
    return () => clearTimeout(t)
  }, [loading, currentIdx])
  const slow = loading && slowIdx === currentIdx

  // Seek by sentence: the bar follows the drag at once, playback after a pause
  const [scrub, setScrub] = useState(null)
  useEffect(() => {
    if (scrub === null) return
    const t = setTimeout(() => {
      setScrub(null)
      playFrom(scrub)
    }, SEEK_COMMIT_MS)
    return () => clearTimeout(t)
  }, [scrub, playFrom])
  const position = scrub ?? currentIdx
  const pct = last > 0 ? (position / last) * 100 : 0

  let statusLine = null
  if (status === 'error') {
    statusLine = (
      <>
        {error}{' '}
        <button type="button" className="vd-link-btn" onClick={() => playFrom(currentIdx)}>
          Try again
        </button>
      </>
    )
  } else if (slow) statusLine = 'Preparing audio…'
  else if (notice) statusLine = notice

  return (
    <section ref={ref} className="vd-player" aria-label="Audio player" data-player-bar>
      {/* Always rendered: screen readers only announce changes to a live region that already exists */}
      <p className="vd-player-status" aria-live="polite" data-tone={status === 'error' || notice ? 'error' : undefined}>
        {statusLine}
      </p>

      <div className="vd-player-row">
        <div className="vd-player-voice">{voiceControl}</div>
        <div className="vd-player-controls">
          <button type="button" className="vd-icon-btn" onClick={player.prev} disabled={currentIdx === 0} aria-label="Previous sentence">
            <Icon name="prev" />
          </button>
          <button
            type="button"
            className="vd-play"
            onClick={player.toggle}
            disabled={!ready}
            // aria-disabled while a clip loads: a disabled button would drop keyboard focus
            aria-disabled={loading || undefined}
            data-loading={slow || undefined}
            aria-label={playing ? 'Pause' : 'Play'}
          >
            <Icon name={playing ? 'pause' : 'play'} size="lg" />
          </button>
          <button type="button" className="vd-icon-btn" onClick={player.next} disabled={currentIdx >= last} aria-label="Next sentence">
            <Icon name="next" />
          </button>
        </div>
        <p className="vd-player-title" aria-hidden="true">
          {title}
        </p>
        <div className="vd-player-speed">{speedControl}</div>
      </div>

      <div className="vd-seek">
        <input
          className="vd-range"
          type="range"
          min={0}
          max={last}
          step={1}
          value={position}
          style={{ '--vd-pct': `${pct}%` }}
          onChange={(e) => setScrub(Number(e.target.value))}
          aria-label="Position in the document"
          aria-valuetext={`Sentence ${position + 1} of ${sentenceCount}`}
          disabled={!ready || last === 0}
        />
        <div className="vd-seek-labels" aria-hidden="true">
          <span>Sentence {position + 1}</span>
          <span>of {sentenceCount}</span>
        </div>
      </div>
    </section>
  )
}
