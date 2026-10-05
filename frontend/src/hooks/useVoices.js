import { useEffect, useState } from 'react'
import { getVoices } from '../api'

// One request per page load, shared by every component that asks
let voicesPromise = null

/** The presets, from one shared request; a failed request is retried on the next call. */
export function loadVoices() {
  voicesPromise ??= getVoices().catch((err) => {
    voicesPromise = null
    throw err
  })
  return voicesPromise
}

/** GET /voices. status: 'loading' | 'ready' | 'error' */
export function useVoices() {
  const [state, setState] = useState({ status: 'loading', voices: null, error: null })

  useEffect(() => {
    let active = true
    loadVoices()
      .then((voices) => active && setState({ status: 'ready', voices, error: null }))
      .catch((err) => active && setState({ status: 'error', voices: null, error: err.message }))
    return () => {
      active = false
    }
  }, [])

  return state
}
