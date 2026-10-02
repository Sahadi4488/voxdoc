import { memo, useEffect, useId, useRef, useState } from 'react'
import { summarizeDocument } from '../api'
import { outlineButton } from '../lib/styles'
import { formatWait } from '../lib/wait'

const ChevronIcon = ({ up }) => (
  <svg
    viewBox="0 0 24 24"
    width="16"
    height="16"
    aria-hidden="true"
    fill="none"
    stroke="currentColor"
    strokeWidth="2.5"
    className={up ? 'rotate-180' : ''}
  >
    <path d="m6 9 6 6 6-6" />
  </svg>
)

function errorText(err) {
  if (err.status === 429) return `The summary service is busy. Try again in ${formatWait(err.retryAfter ?? 10)}.`
  if (err.status === 503) return "Summaries aren't available on this server."
  return err.message
}

/**
 * The "Summarize" button and the summary it reveals. Fetches only when
 * clicked: the free Groq quota is too small to summarise every document.
 *
 * The button is a disclosure (aria-expanded). Once the summary has loaded,
 * clicking it collapses and reopens the panel instantly, with no new request;
 * after an error, clicking it tries again. `actions` are more buttons for the
 * same row (Ask). Memoised: ReaderPage re-renders on every spoken word, this
 * only when its props change.
 */
function SummaryPanel({ docId, actions = null }) {
  const [state, setState] = useState({ status: 'idle' }) // idle | loading | done | error
  const [open, setOpen] = useState(false)
  const busy = useRef(false) // set synchronously: a fast double-click can't start two requests
  const abort = useRef(null)
  const panelId = useId()
  const labelId = useId()

  // Leaving the document cancels a running request
  useEffect(() => {
    const controller = new AbortController()
    abort.current = controller
    return () => controller.abort()
  }, [])

  async function onClick() {
    if (busy.current) return
    if (state.status === 'done') {
      setOpen((o) => !o)
      return
    }
    busy.current = true
    setState({ status: 'loading' })
    try {
      const summary = await summarizeDocument(docId, abort.current.signal)
      setState({ status: 'done', summary })
      setOpen(true)
    } catch (err) {
      if (err.name !== 'AbortError') setState({ status: 'error', message: errorText(err) })
    } finally {
      busy.current = false
    }
  }

  const { status, summary } = state
  const loading = status === 'loading'
  const expanded = status === 'done' && open
  return (
    <div className="mt-4">
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={onClick}
          aria-expanded={expanded}
          aria-controls={status === 'done' ? panelId : undefined}
          // aria-disabled, not disabled: a disabled button drops keyboard focus
          aria-disabled={loading || undefined}
          className={outlineButton}
        >
          {loading ? 'Summarizing…' : 'Summarize'}
          {!loading && <ChevronIcon up={expanded} />}
        </button>
        {actions}
      </div>

      <p className="sr-only" aria-live="polite">
        {loading ? 'Summarizing…' : expanded ? 'Summary ready.' : ''}
      </p>
      {status === 'error' && (
        <p className="mt-3 text-sm text-error" role="alert">
          {state.message}
        </p>
      )}

      {status === 'done' && (
        <section id={panelId} aria-labelledby={labelId} hidden={!open} className="mt-4 border-l-2 border-rule pl-4">
          <h2 id={labelId} className="text-sm font-bold">
            Summary
          </h2>
          <p className="mt-1 font-reading leading-7">{summary.overview}</p>
          <ul className="mt-3 list-disc space-y-1 pl-5 font-reading leading-7">
            {summary.key_points.map((point, i) => (
              <li key={i}>{point}</li>
            ))}
          </ul>
          {summary.source === 'excerpts' && (
            <p className="mt-3 text-sm text-graphite">Based on selected passages from this document.</p>
          )}
        </section>
      )}
    </div>
  )
}

export default memo(SummaryPanel)
