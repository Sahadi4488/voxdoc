import { useCallback, useEffect, useRef, useState } from 'react'
import PlayerBar from './components/PlayerBar'
import Reader from './components/Reader'
import Uploader from './components/Uploader'
import { useDocument } from './hooks/useDocument'
import { usePlayer } from './hooks/usePlayer'

const VOICE = { id: 'presenter', label: 'Presenter' } // Day 9: becomes the voice picker

// The open document lives in the URL (?doc=<public id>): refresh-safe and shareable.
const docIdFromUrl = () => new URLSearchParams(window.location.search).get('doc')

function navigate(docId) {
  const url = new URL(window.location.href)
  if (docId) url.searchParams.set('doc', docId)
  else url.searchParams.delete('doc')
  window.history.pushState(null, '', url)
}

export default function App() {
  const [docId, setDocId] = useState(docIdFromUrl)
  const { status: docStatus, doc, error: docError } = useDocument(docId)
  const player = usePlayer({
    docId: doc?.id ?? null,
    sentenceCount: doc?.sentences.length ?? 0,
    voice: VOICE.id,
    speed: undefined, // the preset's default speed
  })
  const barRef = useRef(null)
  const bottomInset = useCallback(() => barRef.current?.offsetHeight ?? 0, [])

  // Back/forward buttons
  useEffect(() => {
    const onPop = () => setDocId(docIdFromUrl())
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [])

  const open = (id) => {
    navigate(id)
    setDocId(id)
  }

  // Keyboard: Space = play/pause, arrows = previous/next sentence
  const { toggle, next, prev } = player
  useEffect(() => {
    if (!doc) return
    const onKey = (e) => {
      if (e.ctrlKey || e.metaKey || e.altKey) return
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

  const reading = docStatus === 'ready'
  const showHighlight = !['idle', 'ended'].includes(player.status)

  return (
    <main className={`mx-auto max-w-[40rem] px-6 pt-16 ${reading ? 'pb-40' : 'pb-16'}`}>
      <header className="flex items-baseline justify-between gap-4">
        <p className="font-bold tracking-wide">VoxDoc</p>
        {docId && (
          <button
            type="button"
            onClick={() => open(null)}
            className="cursor-pointer text-sm font-bold text-pen underline underline-offset-4 outline-offset-4 outline-pen hover:text-ink focus-visible:outline-2"
          >
            Upload another file
          </button>
        )}
      </header>

      {!docId && (
        <>
          <h1 className="mt-10 font-reading text-headline font-semibold">Listen to any document.</h1>
          <p className="mt-4 font-reading text-reading">
            Upload a PDF or Word file. VoxDoc reads it aloud and highlights each word as it&rsquo;s
            spoken.
          </p>
          <Uploader onUploaded={(meta) => open(meta.id)} />
        </>
      )}

      {docStatus === 'loading' && <p className="mt-10 text-graphite">Opening the document…</p>}

      {docStatus === 'error' && (
        <p className="mt-10 text-error" role="alert">
          {docError}
        </p>
      )}

      {reading && (
        <div className="mt-10">
          <Reader
            doc={doc}
            activeIdx={showHighlight ? player.currentIdx : null}
            onSentenceClick={player.playFrom}
            bottomInset={bottomInset}
          />
          <PlayerBar
            ref={barRef}
            player={player}
            sentenceCount={doc.sentences.length}
            voiceLabel={VOICE.label}
          />
        </div>
      )}
    </main>
  )
}
