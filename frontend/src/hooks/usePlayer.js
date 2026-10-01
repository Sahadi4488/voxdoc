import { useCallback, useEffect, useRef, useState } from 'react'
import { audioUrl, getTts } from '../api'
import { isUnlockClip, unlockAudio } from '../lib/audio'

/*
  Sentence-by-sentence player for one document (ReaderPage is keyed by docId,
  so a different document means a fresh hook; unmount cleanup stops everything).

  status: 'idle' | 'loading' | 'playing' | 'paused' | 'ended' | 'error'

  Every jump (play from idle, next, prev, sentence click, auto-advance, voice
  change) goes through playFrom(idx), which takes a new request token. After
  each await it checks the token: if a newer jump happened meanwhile, it stops.
  That is what makes "click next five times" play only the fifth sentence.

  State is what the UI shows; refs are what listeners and async code read
  (they always see the latest value, never a stale closure).
*/

const LOAD_ERROR = "Can't load the audio. Check that the VoxDoc server is running, then try again."
const RESTART_DELAY_MS = 250 // arrowing through voices restarts playback once, not per key press

// Dev-only switch for the README metric: open the app with ?noprefetch
const PREFETCH = !(import.meta.env.DEV && new URLSearchParams(window.location.search).has('noprefetch'))

const clipKey = (idx, voice, speed) => `${idx}|${voice}|${speed}`

function getCache(ref) {
  if (!ref.current) ref.current = new Map()
  return ref.current
}

function getAudio(ref) {
  if (!ref.current) {
    ref.current = new Audio() // lazy: useRef(new Audio()) would create one per render
    if (import.meta.env.DEV) window.__voxdocAudio = ref.current
  }
  return ref.current
}

export function usePlayer({ docId, sentenceCount, voice, speed }) {
  const [status, setStatus] = useState('idle')
  const [currentIdx, setCurrentIdx] = useState(0)
  const [clip, setClip] = useState(null) // current /tts response (timings for Day 10)
  const [error, setError] = useState(null)

  const audioRef = useRef(null)
  // Map<clipKey, {idx, voice, speed, promise}>: promises, so in-flight clips aren't requested twice.
  // Keyed by voice and speed too, so a clip in the old voice can never play after a change.
  const cacheRef = useRef(null)
  const tokenRef = useRef(0) // incremented by every jump; stale async work compares and bails
  const idxRef = useRef(0)
  const statusRef = useRef('idle')
  const loadedKeyRef = useRef(null) // clipKey of what's in (or about to be in) audio.src
  const voiceRef = useRef(voice)
  const speedRef = useRef(speed)

  // Declared first: later effects in the same commit read the new values
  useEffect(() => {
    voiceRef.current = voice
    speedRef.current = speed
  }, [voice, speed])

  const changeStatus = useCallback((s) => {
    statusRef.current = s
    setStatus(s)
  }, [])

  const fail = useCallback(
    (message) => {
      setError(message)
      changeStatus('error')
    },
    [changeStatus],
  )

  const fetchClip = useCallback(
    (idx) => {
      const v = voiceRef.current
      const s = speedRef.current
      const cache = getCache(cacheRef)
      const key = clipKey(idx, v, s)
      let entry = cache.get(key)
      if (!entry) {
        entry = { idx, voice: v, speed: s, promise: getTts({ docId, idx, voice: v, speed: s }) }
        cache.set(key, entry)
        const mine = entry
        // Never keep a failure: a retry must make a fresh request. (Also marks
        // the rejection as handled, so an unused failed prefetch doesn't log.)
        entry.promise.catch(() => {
          if (cache.get(key) === mine) cache.delete(key)
        })
      }
      return entry.promise
    },
    [docId],
  )

  const playFrom = useCallback(
    async (idx) => {
      if (!docId || !voiceRef.current || idx < 0 || idx >= sentenceCount) return
      const token = ++tokenRef.current
      const audio = getAudio(audioRef)
      unlockAudio(audio) // first call only; must happen before any await
      audio.pause() // a jump silences the old clip at once: no overlap
      idxRef.current = idx
      setCurrentIdx(idx)
      setError(null)
      changeStatus('loading')
      const v = voiceRef.current
      const s = speedRef.current
      loadedKeyRef.current = clipKey(idx, v, s)
      const cache = getCache(cacheRef)
      for (const [key, entry] of cache) {
        // keep at most one sentence behind, and nothing in another voice/speed
        if (entry.idx < idx - 1 || entry.voice !== v || entry.speed !== s) cache.delete(key)
      }

      let data
      try {
        data = await fetchClip(idx)
      } catch (err) {
        if (token === tokenRef.current) fail(err.message)
        return
      }
      if (token !== tokenRef.current) return // a newer jump won

      setClip(data)
      audio.src = audioUrl(data.audio_url)
      try {
        await audio.play()
      } catch (err) {
        // AbortError: a newer jump interrupted this play(). Anything else is real.
        if (err.name === 'AbortError' || token !== tokenRef.current) return
        fail(err.name === 'NotAllowedError' ? 'The browser blocked playback. Press play to start.' : LOAD_ERROR)
        return
      }
      if (token !== tokenRef.current) return
      changeStatus('playing')
      if (PREFETCH && idx + 1 < sentenceCount) fetchClip(idx + 1)
    },
    [docId, sentenceCount, fetchClip, changeStatus, fail],
  )

  const pause = useCallback(() => {
    if (statusRef.current !== 'playing') return
    audioRef.current?.pause()
    changeStatus('paused')
  }, [changeStatus])

  const resume = useCallback(async () => {
    const audio = audioRef.current
    const current = clipKey(idxRef.current, voiceRef.current, speedRef.current)
    // Voice/speed changed while paused: the loaded clip is stale, fetch the new one
    if (!audio || loadedKeyRef.current !== current) return playFrom(idxRef.current)
    const token = tokenRef.current // not a jump: same clip, same position
    changeStatus('playing')
    try {
      await audio.play()
    } catch (err) {
      if (err.name !== 'AbortError' && token === tokenRef.current) fail(LOAD_ERROR)
    }
  }, [playFrom, changeStatus, fail])

  const play = useCallback(() => {
    switch (statusRef.current) {
      case 'paused':
        return resume()
      case 'ended':
        return playFrom(0)
      case 'idle':
      case 'error':
        return playFrom(idxRef.current)
      default: // playing, or loading (the play button is disabled meanwhile)
    }
  }, [resume, playFrom])

  const toggle = useCallback(() => (statusRef.current === 'playing' ? pause() : play()), [pause, play])
  const next = useCallback(() => playFrom(idxRef.current + 1), [playFrom])
  const prev = useCallback(() => playFrom(idxRef.current - 1), [playFrom])

  // Voice or speed changed while playing: restart the current sentence in the
  // new voice. An effect, not the picker's handler: only here do the new values
  // exist. Harmless on mount and under StrictMode (nothing is playing then).
  useEffect(() => {
    const t = setTimeout(() => {
      const playingNow = statusRef.current === 'playing' || statusRef.current === 'loading'
      const stale = loadedKeyRef.current !== clipKey(idxRef.current, voice, speed)
      if (playingNow && stale) playFrom(idxRef.current)
    }, RESTART_DELAY_MS)
    return () => clearTimeout(t)
  }, [voice, speed, playFrom])

  // Audio element events. Re-registered when playFrom changes, always with cleanup,
  // so a listener is never attached twice (StrictMode would otherwise expose it).
  useEffect(() => {
    const audio = getAudio(audioRef)
    let endedAt = null
    const onEnded = () => {
      if (isUnlockClip(audio)) return
      if (import.meta.env.DEV) endedAt = performance.now()
      const nextIdx = idxRef.current + 1 // ref, not state: this listener may be from an older render
      if (nextIdx < sentenceCount) playFrom(nextIdx)
      else changeStatus('ended')
    }
    const onPlaying = () => {
      if (import.meta.env.DEV && endedAt !== null) {
        ;(window.__voxdocGaps ??= []).push(performance.now() - endedAt) // README metric
        endedAt = null
      }
    }
    const onError = () => {
      // Network failure mid-clip (e.g. the server stopped). Ignore the unlock clip and cleared src.
      if (!audio.getAttribute('src') || isUnlockClip(audio)) return
      if (statusRef.current === 'playing' || statusRef.current === 'paused') fail(LOAD_ERROR)
    }
    audio.addEventListener('ended', onEnded)
    audio.addEventListener('playing', onPlaying)
    audio.addEventListener('error', onError)
    return () => {
      audio.removeEventListener('ended', onEnded)
      audio.removeEventListener('playing', onPlaying)
      audio.removeEventListener('error', onError)
    }
  }, [playFrom, sentenceCount, changeStatus, fail])

  // Unmount (another document opened, or back to upload): stop, forget
  // everything, invalidate in-flight work, so this document's audio can never play.
  useEffect(() => {
    const audio = getAudio(audioRef)
    const cache = getCache(cacheRef)
    return () => {
      // Deliberately the *current* value: this must invalidate the latest jump.
      // (The rule's advice is for DOM refs; this is a counter.)
      // oxlint-disable-next-line react-hooks/exhaustive-deps
      tokenRef.current++
      audio.pause()
      audio.removeAttribute('src')
      audio.load()
      cache.clear()
    }
  }, [])

  // Warm the clip for the current sentence as soon as a document opens (and
  // after a voice change while idle): the first press of play is then instant.
  useEffect(() => {
    if (PREFETCH && docId && voice && sentenceCount > 0 && statusRef.current === 'idle') {
      fetchClip(idxRef.current)
    }
  }, [docId, sentenceCount, voice, speed, fetchClip])

  return { status, currentIdx, clip, error, play, pause, toggle, next, prev, playFrom }
}
