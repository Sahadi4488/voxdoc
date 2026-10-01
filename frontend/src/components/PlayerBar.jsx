import { useEffect, useState } from 'react'

const Icon = ({ d }) => (
  <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" fill="currentColor">
    <path d={d} />
  </svg>
)
const ICONS = {
  play: 'M8 5.14v13.72a1 1 0 0 0 1.5.86l11-6.86a1 1 0 0 0 0-1.72l-11-6.86A1 1 0 0 0 8 5.14z',
  pause: 'M7 5h3.5v14H7zM13.5 5H17v14h-3.5z',
  prev: 'M6 5h2.5v14H6zM19 5.6v12.8a.8.8 0 0 1-1.25.66L9.5 12.66a.8.8 0 0 1 0-1.32l8.25-6.4A.8.8 0 0 1 19 5.6z',
  next: 'M15.5 5H18v14h-2.5zM5 5.6v12.8a.8.8 0 0 0 1.25.66l8.25-6.4a.8.8 0 0 0 0-1.32L6.25 4.94A.8.8 0 0 0 5 5.6z',
}

const focusRing = 'outline-offset-2 outline-pen focus-visible:outline-2'
const quietButton = `rounded-md p-2 text-ink hover:text-pen disabled:cursor-not-allowed disabled:opacity-40 ${focusRing}`

export default function PlayerBar({ ref, player, sentenceCount, voicePicker, notice }) {
  const { status, currentIdx, error } = player
  const playing = status === 'playing'
  const loading = status === 'loading'

  // "Preparing audio…" only once loading the current sentence has lasted
  // 300 ms, so a prefetched clip doesn't make the text flash for a split second.
  const [slowIdx, setSlowIdx] = useState(null)
  useEffect(() => {
    if (!loading) return
    const t = setTimeout(() => setSlowIdx(currentIdx), 300)
    return () => clearTimeout(t)
  }, [loading, currentIdx])
  const slow = loading && slowIdx === currentIdx

  return (
    <div ref={ref} className="fixed inset-x-0 bottom-0 border-t border-rule bg-paper">
      <div className="mx-auto flex max-w-[40rem] flex-wrap items-center gap-x-4 gap-y-1 px-6 py-3">
        <div className="flex items-center gap-1">
          <button
            type="button"
            aria-label="Previous sentence"
            onClick={player.prev}
            disabled={currentIdx === 0}
            className={quietButton}
          >
            <Icon d={ICONS.prev} />
          </button>
          <button
            type="button"
            aria-label={playing ? 'Pause' : 'Play'}
            onClick={player.toggle}
            disabled={loading || !player.ready}
            className={`rounded-full bg-pen p-3 text-paper hover:bg-ink disabled:cursor-wait disabled:opacity-60 ${focusRing}`}
          >
            <Icon d={playing ? ICONS.pause : ICONS.play} />
          </button>
          <button
            type="button"
            aria-label="Next sentence"
            onClick={player.next}
            disabled={currentIdx >= sentenceCount - 1}
            className={quietButton}
          >
            <Icon d={ICONS.next} />
          </button>
        </div>

        <p className="text-sm text-graphite">
          Sentence {currentIdx + 1} of {sentenceCount}
        </p>
        <div className="ml-auto">{voicePicker}</div>

        {/* Not display:none when empty: live regions must exist before their content changes */}
        <div aria-live="polite" className="basis-full text-sm">
          {status === 'error' ? (
            <span className="text-error">
              {error}{' '}
              <button
                type="button"
                onClick={() => player.playFrom(currentIdx)}
                className={`cursor-pointer font-bold text-pen underline underline-offset-4 hover:text-ink ${focusRing}`}
              >
                Try again
              </button>
            </span>
          ) : loading && slow ? (
            <span className="text-graphite">Preparing audio…</span>
          ) : notice ? (
            <span className="text-error">{notice}</span>
          ) : null}
        </div>
      </div>
    </div>
  )
}
