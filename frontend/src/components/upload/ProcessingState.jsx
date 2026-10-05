/** Understated progress: a hairline bar and a short checklist of the real steps. */
export default function ProcessingState({ fileName, steps, stage }) {
  const pct = Math.min(100, ((stage + 0.5) / steps.length) * 100)
  return (
    <div className="vd-processing">
      <h2 className="vd-processing-title" id="vd-upload-title">
        Preparing your document
      </h2>
      <p className="vd-processing-file">{fileName}</p>
      <div className="vd-progress" aria-hidden="true">
        <span style={{ width: `${pct}%` }} />
      </div>
      <ol className="vd-steps-list">
        {steps.map((label, i) => {
          const state = i < stage ? 'done' : i === stage ? 'active' : 'pending'
          return (
            <li key={label} data-state={state} aria-current={state === 'active' ? 'step' : undefined}>
              <span className="vd-step-dot" aria-hidden="true">
                {state === 'done' && (
                  <svg
                    className="vd-icon vd-icon--sm"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <path d="M5 12.5l4.5 4.5L19 7.5" />
                  </svg>
                )}
              </span>
              {label}
            </li>
          )
        })}
      </ol>
      {/* One short announcement per step, not the whole list each time */}
      <p className="vd-sr-only" aria-live="polite">
        {stage < steps.length ? `${steps[stage]}…` : 'Opening the reader.'}
      </p>
    </div>
  )
}
