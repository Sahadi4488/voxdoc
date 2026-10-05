import { useCallback, useEffect, useId, useMemo, useRef, useState } from 'react'
import { useDocument } from '../../hooks/useDocument'
import { usePlayer } from '../../hooks/usePlayer'
import { useSummary } from '../../hooks/useSummary'
import { useVoicePrefs } from '../../hooks/useVoicePrefs'
import { useVoices } from '../../hooks/useVoices'
import { groupParagraphs, headings, scrollToSentence } from '../../lib/document'
import { countWords, fileKind, listenMinutes, uploadedLabel } from '../../lib/format'
import { forgetLastDoc, saveLastDoc } from '../../lib/lastDoc'
import AskPanel from './AskPanel'
import DocumentView from './DocumentView'
import PlayerBar from './PlayerBar'
import ReaderLayout from './ReaderLayout'
import ReaderSidebar from './ReaderSidebar'
import SpeedPicker from './SpeedPicker'
import SummaryView from './SummaryView'
import VoicePicker from './VoicePicker'

const WIDE = '(min-width: 80rem)' // 1280px: the Ask panel sits beside the text instead of over it

/**
 * Everything that belongs to one open document. App renders it with
 * key={docId}, so opening another document unmounts this one: all state starts
 * over and the player's unmount cleanup stops its audio, by construction.
 */
export default function ReaderPage({ docId, onHome, onNewDocument, theme }) {
  const { status, doc, error } = useDocument(docId)
  const { voices, error: voicesError } = useVoices()
  const [prefs, setVoice, setSpeed] = useVoicePrefs(docId, voices)
  const player = usePlayer({
    docId: doc?.id ?? null,
    sentenceCount: doc?.sentences.length ?? 0,
    voice: prefs?.voice ?? null, // null until /voices has loaded and the stored prefs are validated
    speed: prefs?.speed,
  })
  const [summary, generateSummary] = useSummary(docId)
  const [view, setView] = useState('document')
  const [askOpen, setAskOpen] = useState(false)
  const askId = useId()
  const playerRef = useRef(null)
  const titleRef = useRef(null)
  const askItemRef = useRef(null)
  const mobileAskRef = useRef(null)
  const bottomInset = useCallback(() => playerRef.current?.offsetHeight ?? 0, [])

  const paragraphs = useMemo(() => (doc ? groupParagraphs(doc.sentences) : []), [doc])
  const toc = useMemo(() => headings(paragraphs), [paragraphs])
  const words = useMemo(() => (doc ? countWords(doc.sentences) : 0), [doc])

  // "Open Reader" on the landing page returns here; a missing document is forgotten
  useEffect(() => {
    if (status === 'ready') saveLastDoc(docId)
    if (status === 'error') forgetLastDoc(docId)
  }, [status, docId])

  useEffect(() => {
    if (!doc) return
    document.title = `${doc.title} · VoxDoc`
    return () => {
      document.title = 'VoxDoc'
    }
  }, [doc])

  // Arriving from the upload sheet or a link: start at the title, unless focus is already somewhere
  useEffect(() => {
    if (status === 'ready' && (!document.activeElement || document.activeElement === document.body)) {
      titleRef.current?.focus({ preventScroll: true })
    }
  }, [status])

  // Switching between the document and the summary starts the new page at the top
  const viewRef = useRef(view)
  const showView = useCallback((next) => {
    if (viewRef.current === next) return
    viewRef.current = next
    setView(next)
    window.scrollTo({ top: 0 })
  }, [])

  // Questions panel. Closing returns focus to whichever Ask control is on screen.
  const toggleAsk = useCallback(() => setAskOpen((o) => !o), [])
  const closeAsk = useCallback(() => {
    setAskOpen(false)
    const target = [askItemRef.current, mobileAskRef.current].find((el) => el?.offsetParent)
    target?.focus({ preventScroll: true }) // the reader may be scrolled far below it
  }, [])

  const { playFrom } = player
  // A citation click is a user gesture, so playback may start. The reader's
  // auto-scroll brings the sentence into view; where the panel covers the text,
  // it closes first.
  const onCite = useCallback(
    (idx) => {
      showView('document')
      if (!window.matchMedia(WIDE).matches) closeAsk()
      playFrom(idx)
    },
    [showView, closeAsk, playFrom],
  )

  const onTocSelect = useCallback(
    (idx) => {
      showView('document')
      setTimeout(() => scrollToSentence(idx), 0) // after the document view has rendered
    },
    [showView],
  )

  // Keyboard: Space = play/pause, arrows = previous/next sentence
  const { toggle, next, prev, pause } = player
  useEffect(() => {
    if (!doc) return
    const onKey = (e) => {
      if (e.ctrlKey || e.metaKey || e.altKey || e.defaultPrevented) return
      // Fields, sliders, radio groups and open dialogs use these keys themselves
      if (e.target.closest('input, textarea, select, [contenteditable="true"], [role="dialog"]')) return
      if (e.key === ' ') {
        // A focused button already turns Space into a click; handling it here
        // too would toggle twice and nothing would happen.
        if (e.target.closest('button, a, [role="button"]')) return
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

  if (status === 'loading' || status === 'idle') {
    return (
      <div className="vd-reader">
        <main className="vd-state" style={{ paddingTop: 120 }}>
          <p role="status">Opening the document…</p>
        </main>
      </div>
    )
  }
  if (status === 'error') {
    // e.g. "Document not found. Check the link, or upload the file again." plus the ways on
    return (
      <div className="vd-reader">
        <main className="vd-state" style={{ paddingTop: 120 }}>
          <h1 className="vd-state-title">This document couldn&rsquo;t be opened</h1>
          <p role="alert">{error}</p>
          <div className="vd-state-actions">
            <button type="button" className="vd-btn vd-btn--dark" onClick={onNewDocument}>
              Upload a document
            </button>
            <button type="button" className="vd-btn vd-btn--outline" onClick={onHome}>
              Back to home
            </button>
          </div>
        </main>
      </div>
    )
  }

  const showHighlight = !['idle', 'ended'].includes(player.status)
  const activeIdx = showHighlight ? player.currentIdx : null
  let activeTocIdx = null
  for (const t of toc) if (t.idx <= player.currentIdx) activeTocIdx = t.idx
  const minutes = listenMinutes(words, prefs?.speed ?? 1)
  const meta = [fileKind(doc.filename), minutes && `${minutes} min listen`].filter(Boolean).join(' · ')

  return (
    <ReaderLayout
      title={doc.title}
      focus={player.status === 'playing'}
      panelOpen={askOpen}
      askOpen={askOpen}
      onToggleAsk={toggleAsk}
      mobileAskRef={mobileAskRef}
      sidebar={
        <ReaderSidebar
          view={view}
          onViewChange={showView}
          askOpen={askOpen}
          onToggleAsk={toggleAsk}
          askItemRef={askItemRef}
          askPanelId={askId}
          toc={toc}
          activeTocIdx={activeTocIdx}
          onTocSelect={onTocSelect}
          onHome={onHome}
          onNewDocument={onNewDocument}
          theme={theme}
        />
      }
      player={
        <PlayerBar
          ref={playerRef}
          player={player}
          sentenceCount={doc.sentences.length}
          ready={!!prefs}
          notice={voicesError}
          title={doc.title}
          voiceControl={
            prefs && (
              <VoicePicker
                voices={voices}
                voiceId={prefs.voice}
                speed={prefs.speed}
                onVoiceChange={setVoice}
                docId={doc.id}
                currentIdx={player.currentIdx}
                onPreviewStart={pause}
              />
            )
          }
          speedControl={prefs && <SpeedPicker speed={prefs.speed} onSpeedChange={setSpeed} />}
        />
      }
      panel={<AskPanel id={askId} open={askOpen} onClose={closeAsk} docId={doc.id} sentences={doc.sentences} onCite={onCite} />}
    >
      {view === 'summary' ? (
        <SummaryView title={doc.title} state={summary} onGenerate={generateSummary} />
      ) : (
        <DocumentView
          doc={doc}
          paragraphs={paragraphs}
          meta={meta}
          uploaded={uploadedLabel(doc.created_at)}
          titleRef={titleRef}
          activeIdx={activeIdx}
          wordSync={player.wordSync}
          wordStart={player.wordStart}
          wordEnd={player.wordEnd}
          onSentenceClick={player.playFrom}
          bottomInset={bottomInset}
        />
      )}
    </ReaderLayout>
  )
}
