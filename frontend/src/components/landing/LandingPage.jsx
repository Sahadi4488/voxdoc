import Icon from '../ui/Icon'
import Features from './Features'
import Hero from './Hero'
import HowItWorks from './HowItWorks'
import Navbar from './Navbar'
import VoicesSection from './VoicesSection'

/** The cinematic front page. Uploading happens in the floating sheet App renders. */
export default function LandingPage({ onUploadClick, onOpenReader, theme }) {
  return (
    <>
      <Navbar onOpenReader={onOpenReader} theme={theme} />
      <Hero onUploadClick={onUploadClick} />
      <main>
        <Features />
        <HowItWorks />
        <VoicesSection />
        <section className="vd-cta-band" aria-labelledby="vd-cta-title">
          <h2 className="vd-h2" id="vd-cta-title">
            Your next document, read to you.
          </h2>
          <button type="button" className="vd-btn vd-btn--dark" onClick={onUploadClick}>
            Upload document <Icon name="arrowRight" size="sm" />
          </button>
        </section>
      </main>
      <footer className="vd-footer">
        <span>VoxDoc</span>
        <span>Kokoro TTS · FastAPI · React</span>
      </footer>
    </>
  )
}
