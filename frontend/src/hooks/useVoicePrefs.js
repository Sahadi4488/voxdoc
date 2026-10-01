import { useCallback, useMemo, useState } from 'react'
import { loadPrefs, roundSpeed, savePrefs, validatePrefs } from '../lib/prefs'

/**
 * The listener's {voice, speed} for this document.
 * Load order: this document's prefs -> last used -> the default preset.
 * Returns [prefs | null until /voices has loaded, setVoice, setSpeed].
 */
export function useVoicePrefs(docId, voices) {
  // Store only what the user chose (ids, numbers); validated values are derived.
  const [raw, setRaw] = useState(() => loadPrefs(docId))
  const prefs = useMemo(() => (voices ? validatePrefs(raw, voices) : null), [raw, voices])

  const commit = useCallback(
    (next) => {
      setRaw(next)
      savePrefs(docId, next)
    },
    [docId],
  )

  // Picking a preset loads its default speed; the slider can override it afterwards.
  const setVoice = useCallback(
    (voiceId) => {
      const preset = voices?.find((v) => v.id === voiceId)
      if (preset) commit({ voice: preset.id, speed: preset.default_speed })
    },
    [voices, commit],
  )

  const setSpeed = useCallback(
    (speed) => {
      if (prefs) commit({ voice: prefs.voice, speed: roundSpeed(speed) })
    },
    [prefs, commit],
  )

  return [prefs, setVoice, setSpeed]
}
