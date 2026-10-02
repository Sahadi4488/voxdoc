import { useCallback, useEffect, useId, useMemo, useRef, useState } from 'react'
import { useDocument } from '../hooks/useDocument'
import { usePlayer } from '../hooks/usePlayer'
import { useVoicePrefs } from '../hooks/useVoicePrefs'
import { useVoices } from '../hooks/useVoices'
import { outlineButton } from '../lib/styles'
import ChatPanel from './ChatPanel'
import PlayerBar from './PlayerBar'
import Reader from './Reader'
import SummaryPanel from './SummaryPanel'
import VoicePicker from './VoicePicker'

const WIDE = '(min-width: 64rem)' // Tailwind's lg: the chat panel sits beside the text

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

  // Questions panel
  const [chatOpen, setChatOpen] = useState(false)
  const askRef = useRef(null)
  const chatId = useId()
  const closeChat = useCallback(() => {
    setChatOpen(false)
    askRef.current?.focus({ preventScroll: true }) // the reader may be scrolled far below the button
  }, [])
  const { playFrom } = player
  // A chip click is a user gesture, so playback may start. The reader's
  // auto-scroll brings the sentence into view; on narrow screens the panel
  // covers the text, so it closes first.
  const onCite = useCallback(
    (idx) => {
      if (!window.matchMedia(WIDE).matches) closeChat()
      playFrom(idx)
    },
    [closeChat, playFrom],
  )
  // Memoised so the memoised SummaryPanel, which shows it, skips the word-rate re-renders
  const askButton = useMemo(
    () => (
      <button
        ref={askRef}
        type="button"
        onClick={() => setChatOpen((o) => !o)}
        aria-expanded={chatOpen}
        aria-controls={chatId}
        className={outlineButton}
      >
        Ask
      </button>
    ),
    [chatOpen, chatId],
  )

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
        header={<SummaryPanel docId={doc.id} actions={askButton} />}
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
      <ChatPanel
        id={chatId}
        open={chatOpen}
        onClose={closeChat}
        docId={doc.id}
        sentences={doc.sentences}
        onCite={onCite}
        barRef={barRef}
      />
    </div>
  )
}
