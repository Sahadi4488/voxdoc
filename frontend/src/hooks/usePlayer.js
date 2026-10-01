import { useCallback, useEffect, useRef, useState } from 'react'
import { audioUrl, getTts } from '../api'

/*
  Sentence-by-sentence player.

  status: 'idle' | 'loading' | 'playing' | 'paused' | 'ended' | 'error'

  Every jump (play from idle, next, prev, sentence click, auto-advance) goes
  through playFrom(idx), which takes a new request token. After each await it
  checks the token: if a newer jump happened meanwhile, it stops. That is what
  makes "click next five times" play only the fifth sentence.

  State is what the UI shows; refs are what listeners and async code read
  (they always see the latest value, never a stale closure).
*/

// 10 ms of silence. Played synchronously inside the first click so browsers
// that only allow play() during the user gesture itself (Safari) unlock the
// element before we await the network. One element is reused for every clip.
const SILENCE =
  'data:audio/wav;base64,UklGRsQAAABXQVZFZm10IBAAAAABAAEAQB8AAIA+AAACABAAZGF0YaAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'

const LOAD_ERROR = "Can't load the audio. Check that the VoxDoc server is running, then try again."

// Dev-only switch for the README metric: open the app with ?noprefetch
const PREFETCH = !(import.meta.env.DEV && new URLSearchParams(window.location.search).has('noprefetch'))

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
  const cacheRef = useRef(null) // Map<key, {idx, promise}>: promises, so in-flight clips aren't requested twice
  const tokenRef = useRef(0) // incremented by every jump; stale async work compares and bails
  const idxRef = useRef(0)
  const statusRef = useRef('idle')
  const loadedIdxRef = useRef(null) // which sentence's clip is in audio.src
  const unlockedRef = useRef(false)

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
      const cache = getCache(cacheRef)
      const key = `${idx}|${voice}|${speed ?? ''}`
      let entry = cache.get(key)
      if (!entry) {
        entry = { idx, promise: getTts({ docId, idx, voice, speed }) }
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
    [docId, voice, speed],
  )

  const playFrom = useCallback(
    async (idx) => {
      if (!docId || idx < 0 || idx >= sentenceCount) return
      const token = ++tokenRef.current
      const audio = getAudio(audioRef)
      if (!unlockedRef.current) {
        unlockedRef.current = true
        audio.src = SILENCE
        audio.play().catch(() => {}) // interrupted by the pause() below: expected
      }
      audio.pause() // a jump silences the old clip at once: no overlap
      idxRef.current = idx
      setCurrentIdx(idx)
      setError(null)
      changeStatus('loading')
      const cache = getCache(cacheRef)
      for (const [key, entry] of cache) {
        if (entry.idx < idx - 1) cache.delete(key) // keep at most one sentence behind
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
      loadedIdxRef.current = idx
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
    if (!audio || loadedIdxRef.current !== idxRef.current) return playFrom(idxRef.current)
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

  // Audio element events. Re-registered when playFrom changes, always with cleanup,
  // so a listener is never attached twice (StrictMode would otherwise expose it).
  useEffect(() => {
    const audio = getAudio(audioRef)
    let endedAt = null
    const onEnded = () => {
      if (audio.src.startsWith('data:')) return // the unlock clip
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
      if (!audio.getAttribute('src') || audio.src.startsWith('data:')) return
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

  // New document: reset what the UI shows during render ("adjusting state when
  // a prop changes"), so no frame shows the old document's player state.
  const [shownDocId, setShownDocId] = useState(docId)
  if (docId !== shownDocId) {
    setShownDocId(docId)
    setStatus('idle')
    setCurrentIdx(0)
    setClip(null)
    setError(null)
  }

  // ...and in the effect: stop, forget everything, invalidate in-flight work,
  // so the old document's audio can never play.
  useEffect(() => {
    const audio = getAudio(audioRef)
    const cache = getCache(cacheRef)
    statusRef.current = 'idle'
    idxRef.current = 0
    loadedIdxRef.current = null
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
  }, [docId])

  // Warm the clip for the current sentence as soon as a document opens:
  // the first press of play then starts almost instantly.
  useEffect(() => {
    if (PREFETCH && docId && sentenceCount > 0 && statusRef.current === 'idle') {
      fetchClip(idxRef.current)
    }
  }, [docId, sentenceCount, fetchClip])

  return { status, currentIdx, clip, error, play, pause, toggle, next, prev, playFrom }
}
