import hero1280 from '../../assets/hero-1280.webp'
import hero2560 from '../../assets/hero-2560.webp'
import Icon from '../ui/Icon'

// Photo: Marek Piwnicki on Unsplash (Unsplash License), Dolomites at sunrise.
const PHOTO_PAGE = 'https://unsplash.com/photos/misty-mountain-peaks-at-sunrise-with-soft-pastel-sky-A1IoRfRQHuk'

export default function Hero({ onUploadClick }) {
  return (
    <header className="vd-hero" id="top">
      <img
        className="vd-hero-img"
        src={hero1280}
        srcSet={`${hero1280} 1280w, ${hero2560} 2560w`}
        sizes="100vw"
        alt=""
        fetchPriority="high"
      />
      <div className="vd-hero-scrim" aria-hidden="true" />

      <div className="vd-hero-inner">
        <p className="vd-badge">
          <span aria-hidden="true">✦</span> Read less. Listen more.
        </p>
        <h1 className="vd-hero-title">Listen to any document.</h1>
        <p className="vd-hero-sub">
          Turn PDFs and Word documents into natural speech. Read along while VoxDoc follows every word with you.
        </p>
        <div className="vd-hero-actions">
          <button type="button" className="vd-btn vd-btn--light" onClick={onUploadClick}>
            Upload document <Icon name="arrowRight" size="sm" />
          </button>
          <a className="vd-btn vd-btn--ghost" href="#how-it-works">
            See how it works
          </a>
        </div>
      </div>

      <a className="vd-scroll-cue" href="#features">
        Scroll <Icon name="arrowDown" size="sm" />
      </a>
      <p className="vd-photo-credit">
        Photo:{' '}
        <a href={PHOTO_PAGE} target="_blank" rel="noreferrer">
          Marek Piwnicki
        </a>
      </p>
    </header>
  )
}
