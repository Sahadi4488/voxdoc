const STEPS = [
  { title: 'Upload', text: 'Drop in a PDF or Word document.' },
  { title: 'Choose', text: 'Pick your voice and listening speed.' },
  { title: 'Listen', text: 'VoxDoc reads aloud while following the document with you.' },
]

export default function HowItWorks() {
  return (
    <section className="vd-section" id="how-it-works" aria-labelledby="vd-how-title">
      <div className="vd-container">
        <p className="vd-eyebrow">How it works</p>
        <h2 className="vd-h2" id="vd-how-title">
          Three steps, then just listen.
        </h2>
        <ol className="vd-steps">
          {STEPS.map((s, i) => (
            <li className="vd-step" key={s.title}>
              <span className="vd-step-num" aria-hidden="true">
                {String(i + 1).padStart(2, '0')}
              </span>
              <span className="vd-step-title">{s.title}</span>
              <p className="vd-step-text">{s.text}</p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  )
}
