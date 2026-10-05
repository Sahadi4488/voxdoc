import Icon from '../ui/Icon'

const FEATURES = [
  {
    icon: 'voice',
    title: 'Natural voices',
    text: 'Hear documents through realistic, comfortable voices designed for longer listening.',
  },
  {
    icon: 'book',
    title: 'Read along',
    text: 'VoxDoc follows the narration word by word, so you never lose your place.',
  },
  {
    icon: 'spark',
    title: 'Understand faster',
    text: 'Summarize documents and ask questions, with answers that point back to the exact sentence.',
  },
]

export default function Features() {
  return (
    <section className="vd-section" id="features" aria-labelledby="vd-features-title">
      <div className="vd-container">
        <p className="vd-eyebrow">Features</p>
        <h2 className="vd-h2" id="vd-features-title">
          Documents shouldn&rsquo;t require staring at a screen.
        </h2>
        <p className="vd-lede">Turn long PDFs and Word files into something you can simply listen to.</p>

        <div className="vd-features">
          {FEATURES.map((f) => (
            <article className="vd-feature" key={f.title}>
              <div className="vd-feature-icon">
                <Icon name={f.icon} size="lg" />
              </div>
              <h3>{f.title}</h3>
              <p>{f.text}</p>
            </article>
          ))}
        </div>
      </div>
    </section>
  )
}
