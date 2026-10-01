import { useEffect, useState } from 'react'
import { getVoices } from '../api'

// One request per page load, shared by every component that asks
let voicesPromise = null

/** GET /voices. status: 'loading' | 'ready' | 'error' */
export function useVoices() {
  const [state, setState] = useState({ status: 'loading', voices: null, error: null })

  useEffect(() => {
    let active = true
    voicesPromise ??= getVoices()
    voicesPromise
      .then((voices) => active && setState({ status: 'ready', voices, error: null }))
      .catch((err) => {
        voicesPromise = null // allow a retry on the next mount
        if (active) setState({ status: 'error', voices: null, error: err.message })
      })
    return () => {
      active = false
    }
  }, [])

  return state
}
