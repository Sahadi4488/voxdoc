import { useCallback, useEffect, useRef } from 'react'
import { useDocument } from '../hooks/useDocument'
import { usePlayer } from '../hooks/usePlayer'
import { useVoicePrefs } from '../hooks/useVoicePrefs'
import { useVoices } from '../hooks/useVoices'
import PlayerBar from './PlayerBar'
import Reader from './Reader'
import VoicePicker from './VoicePicker'

/**
 * Everything that belongs to one open document. App renders it with
 * key={docId}, so opening another document unmounts this one: all state starts
 * over and the player's unmount cleanup stops its audio, by construction.
 */
export default function ReaderPage({ docId }) {
  const { status, doc, error } = useDocument(docId)
  const { voices, error: voicesError } = useVoices()
  const [prefs, setVoice, setSpeed] = useVoicePrefs(docId, voices)
  const player = usePlayer({
    docId: doc?.id ?? null,
    sentenceCount: doc?.sentences.length ?? 0,
    voice: prefs?.voice ?? null, // null until /voices has loaded and the stored prefs are validated
    speed: prefs?.speed,
  })
  const barRef = useRef(null)
  const bottomInset = useCallback(() => barRef.current?.offsetHeight ?? 0, [])

  // Keyboard: Space = play/pause, arrows = previous/next sentence
  const { toggle, next, prev, pause } = player
  useEffect(() => {
    if (!doc) return
    const onKey = (e) => {
      if (e.ctrlKey || e.metaKey || e.altKey) return
      // Radios and the speed slider use arrows themselves
      if (e.target.closest('input, textarea, select, [contenteditable="true"]')) return
      if (e.key === ' ') {
        // A focused button already turns Space into a click; handling it here
        // too would toggle twice and nothing would happen.
        if (e.target.closest('button, a')) return
        e.preventDefault() // otherwise the page scrolls
        if (!e.repeat) toggle()
      } else if (e.key === 'ArrowRight') {
        e.preventDefault()
        next()
      } else if (e.key === 'ArrowLeft') {
        e.preventDefault()
        prev()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey) // same function reference
  }, [doc, toggle, next, prev])

  if (status === 'loading' || status === 'idle') return <p className="mt-10 text-graphite">Opening the document…</p>
  if (status === 'error') {
    return (
      <p className="mt-10 text-error" role="alert">
        {error}
      </p>
    )
  }

  const showHighlight = !['idle', 'ended'].includes(player.status)
  return (
    <div className="mt-10">
      <Reader
        doc={doc}
        activeIdx={showHighlight ? player.currentIdx : null}
        wordSync={player.wordSync}
        wordStart={player.wordStart}
        wordEnd={player.wordEnd}
        onSentenceClick={player.playFrom}
        bottomInset={bottomInset}
      />
      <PlayerBar
        ref={barRef}
        player={{ ...player, ready: !!prefs }}
        sentenceCount={doc.sentences.length}
        notice={voicesError}
        voicePicker={
          prefs && (
            <VoicePicker
              voices={voices}
              voiceId={prefs.voice}
              speed={prefs.speed}
              onVoiceChange={setVoice}
              onSpeedChange={setSpeed}
              docId={doc.id}
              currentIdx={player.currentIdx}
              onPreviewStart={pause}
            />
          )
        }
      />
    </div>
  )
}
