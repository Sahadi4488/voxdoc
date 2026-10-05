import { memo } from 'react'
import Icon from '../ui/Icon'

/**
 * The summary as a page of the reader, same width and type as the document.
 * Generated only when asked (free-tier quota); `state` comes from useSummary.
 */
function SummaryView({ title, state, onGenerate }) {
  const { status } = state
  return (
    <article className="vd-doc vd-summary" aria-labelledby="vd-summary-title" aria-busy={status === 'loading'}>
      <header className="vd-doc-header">
        <p className="vd-doc-meta">Summary</p>
        <h1 className="vd-doc-title" id="vd-summary-title">
          {title}
        </h1>
      </header>

      <p className="vd-sr-only" aria-live="polite">
        {status === 'loading' ? 'Summarizing…' : status === 'done' ? 'Summary ready.' : ''}
      </p>

      <div className="vd-doc-body">
        {status === 'idle' && (
          <div className="vd-summary-start">
            <p>Get the main points of this document in a few lines.</p>
            <button type="button" className="vd-btn vd-btn--dark" onClick={onGenerate}>
              <Icon name="summary" size="sm" /> Summarize document
            </button>
          </div>
        )}

        {status === 'loading' && (
          <div aria-hidden="true">
            {[100, 96, 88, 92, 60].map((w, i) => (
              <div key={i} className="vd-skeleton" style={{ width: `${w}%` }} />
            ))}
          </div>
        )}

        {status === 'error' && (
          <>
            <p className="vd-error" role="alert">
              {state.message}
            </p>
            <button type="button" className="vd-btn vd-btn--outline vd-btn--sm" style={{ marginTop: 16 }} onClick={onGenerate}>
              Try again
            </button>
          </>
        )}

        {status === 'done' && (
          <>
            <p className="vd-summary-lead">{state.summary.overview}</p>
            {state.summary.key_points.length > 0 && (
              <>
                <h2 className="vd-summary-label">Key ideas</h2>
                <ul>
                  {state.summary.key_points.map((point, i) => (
                    <li key={i}>{point}</li>
                  ))}
                </ul>
              </>
            )}
            {state.summary.source === 'excerpts' && (
              <p className="vd-summary-note">Based on selected passages from this document.</p>
            )}
          </>
        )}
      </div>
    </article>
  )
}

export default memo(SummaryView)
