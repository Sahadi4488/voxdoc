import { useEffect, useRef, useState } from 'react'
import { getDocument, getTts, uploadDocument } from '../../api'
import { primeDocument } from '../../hooks/useDocument'
import { loadVoices } from '../../hooks/useVoices'
import { loadPrefs, validatePrefs } from '../../lib/prefs'
import Icon from '../ui/Icon'
import FilePreview from './FilePreview'
import ProcessingState from './ProcessingState'
import UploadDropzone from './UploadDropzone'

const MAX_MB = 20 // the backend's limit too (VOXDOC_MAX_UPLOAD_MB)
const EXTENSIONS = ['.pdf', '.docx']
const STEPS = ['Extracting text', 'Preparing reader', 'Loading voice']
const VOICE_WAIT_MS = 8000 // a cold model can take longer: the reader then waits instead

const wait = (ms) => new Promise((r) => setTimeout(r, ms))

function validate(file) {
  const name = file.name.toLowerCase()
  if (!EXTENSIONS.some((ext) => name.endsWith(ext))) {
    return 'VoxDoc reads PDF and Word (.docx) files. Choose one of those.'
  }
  if (file.size > MAX_MB * 1024 * 1024) {
    return `This file is larger than ${MAX_MB} MB. Choose a smaller one.`
  }
  return null
}

/**
 * Synthesise the first sentence in the listener's saved voice, so the first Play
 * is instant (the server caches it; the player's own prefetch then hits that
 * cache). Never throws: the player retries anything that fails here.
 */
async function warmFirstSentence(doc) {
  if (!doc.sentences.length) return
  try {
    const { voice, speed } = validatePrefs(loadPrefs(doc.id), await loadVoices())
    const clip = getTts({ docId: doc.id, idx: 0, voice, speed })
    clip.catch(() => {}) // may reject after the race is over
    await Promise.race([clip, wait(VOICE_WAIT_MS)])
  } catch {
    // voices unavailable: the reader shows that itself
  }
}

/** Floating upload sheet: pick -> confirm -> processing -> onUploaded(docId). */
export default function UploadModal({ open, ...props }) {
  // Mounted only while open, so every opening starts fresh
  return open ? <UploadSheet {...props} /> : null
}

function UploadSheet({ onClose, onUploaded }) {
  const [file, setFile] = useState(null)
  const [phase, setPhase] = useState('pick') // pick | ready | processing
  const [stage, setStage] = useState(0)
  const [error, setError] = useState('')
  const dialogRef = useRef(null)
  const alive = useRef(true)

  // Latest values for the document-level key handler
  const phaseRef = useRef(phase)
  const onCloseRef = useRef(onClose)
  useEffect(() => {
    phaseRef.current = phase
    onCloseRef.current = onClose
  })

  // Focus, scroll lock, Escape, focus trap: once per opening
  useEffect(() => {
    alive.current = true
    const lastFocus = document.activeElement
    const prevOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    dialogRef.current?.focus()

    function onKey(e) {
      if (e.key === 'Escape' && phaseRef.current !== 'processing') {
        e.preventDefault()
        onCloseRef.current()
      }
      if (e.key === 'Tab' && dialogRef.current) {
        const focusable = dialogRef.current.querySelectorAll('button:not([disabled]), [tabindex="0"], a[href]')
        if (!focusable.length) {
          e.preventDefault()
          return
        }
        const first = focusable[0]
        const last = focusable[focusable.length - 1]
        if (e.shiftKey && (document.activeElement === first || document.activeElement === dialogRef.current)) {
          e.preventDefault()
          last.focus()
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault()
          first.focus()
        }
      }
    }
    document.addEventListener('keydown', onKey)
    return () => {
      alive.current = false
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = prevOverflow
      if (lastFocus?.isConnected) lastFocus.focus({ preventScroll: true })
    }
  }, [])

  function choose(f) {
    const problem = validate(f) // `accept` doesn't apply to dropped files
    if (problem) {
      setError(problem)
      setFile(null)
      setPhase('pick')
      return
    }
    setError('')
    setFile(f)
    setPhase('ready')
  }

  async function start() {
    setPhase('processing')
    setStage(0)
    setError('')
    dialogRef.current?.focus() // the Start button is about to disappear
    let meta
    try {
      meta = await uploadDocument(file) // upload + text extraction on the server
    } catch (err) {
      if (!alive.current) return
      setError(err.message)
      setPhase('ready')
      return
    }
    if (!alive.current) return
    setStage(1)
    try {
      const doc = await getDocument(meta.id)
      primeDocument(doc)
      if (!alive.current) return
      setStage(2)
      await warmFirstSentence(doc)
    } catch {
      // the upload worked; the reader fetches the document itself
    }
    if (!alive.current) return
    setStage(3)
    await wait(250) // the finished checklist stays visible for a moment
    if (alive.current) onUploaded(meta.id)
  }

  const processing = phase === 'processing'
  return (
    <div
      className="vd-modal-backdrop"
      onPointerDown={(e) => {
        if (e.target === e.currentTarget && !processing) onClose()
      }}
    >
      <div
        ref={dialogRef}
        className="vd-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="vd-upload-title"
        aria-busy={processing}
        tabIndex={-1}
      >
        {processing ? (
          <ProcessingState fileName={file?.name} steps={STEPS} stage={stage} />
        ) : (
          <>
            <button type="button" className="vd-icon-btn vd-modal-close" onClick={onClose} aria-label="Close">
              <Icon name="close" size="sm" />
            </button>
            <h2 className="vd-modal-title" id="vd-upload-title">
              Upload a document
            </h2>
            <p className="vd-modal-sub">VoxDoc will prepare it for listening.</p>

            {phase === 'pick' && <UploadDropzone maxMb={MAX_MB} onFile={choose} />}

            {phase === 'ready' && file && (
              <>
                <FilePreview file={file} />
                <div className="vd-modal-actions">
                  <button
                    type="button"
                    className="vd-btn vd-btn--ghost vd-btn--sm"
                    onClick={() => {
                      setFile(null)
                      setError('')
                      setPhase('pick')
                    }}
                  >
                    Choose another
                  </button>
                  <button type="button" className="vd-btn vd-btn--dark" onClick={start} autoFocus>
                    Start reading <Icon name="arrowRight" size="sm" />
                  </button>
                </div>
              </>
            )}

            {error && (
              <p className="vd-error" role="alert">
                {error}
              </p>
            )}
          </>
        )}
      </div>
    </div>
  )
}
