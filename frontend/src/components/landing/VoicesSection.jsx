import { useVoices } from '../../hooks/useVoices'
import { voiceDescription } from '../../lib/voices'
import Icon from '../ui/Icon'

/** The presets from GET /api/voices; the section hides itself if they can't load. */
export default function VoicesSection() {
  const { voices } = useVoices()
  if (!voices?.length) return null
  return (
    <section className="vd-section" id="voices" aria-labelledby="vd-voices-title">
      <div className="vd-container">
        <p className="vd-eyebrow">Voices</p>
        <h2 className="vd-h2" id="vd-voices-title">
          A voice for every kind of reading.
        </h2>
        <p className="vd-lede">
          {voices.length} natural voices, American and British, generated on VoxDoc&rsquo;s own server.
        </p>
        <ul className="vd-voices">
          {voices.map((v) => (
            <li key={v.id} className="vd-voice-chip">
              <span className="vd-voice-avatar">
                <Icon name="wave" size="sm" />
              </span>
              <span>
                {v.name} <small>· {voiceDescription(v)}</small>
              </span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  )
}
