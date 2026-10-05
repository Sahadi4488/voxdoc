import { memo, useEffect, useId, useReducer, useRef, useState } from 'react'
import { askQuestion } from '../../api'
import { formatMinutes, formatWait } from '../../lib/wait'
import Icon from '../ui/Icon'

const MAX_QUESTION = 500 // the backend's limit too (AskRequest)
const SUGGESTIONS = ['What is this document about?', 'What are the main conclusions?']

const initialState = { messages: [], pending: false }

/**
 * Pure: no fetch and no mutation. The event handler does the fetch and
 * dispatches before ("asked") and after ("answered" or "failed").
 */
function reducer(state, action) {
  switch (action.type) {
    case 'asked':
      return { messages: [...state.messages, action.message], pending: true }
    case 'answered':
    case 'failed':
      return { messages: [...state.messages, action.message], pending: false }
    default:
      return state
  }
}

function errorText(err) {
  // "rate_limited" is this visitor's own limit; any other 429 is Groq being busy
  if (err.status === 429 && err.code === 'rate_limited') {
    return `You've asked a lot of questions. Try again in ${formatMinutes(err.retryAfter ?? 600)}.`
  }
  if (err.status === 429) return `The answer service is busy. Try again in ${formatWait(err.retryAfter ?? 10)}.`
  if (err.status === 503) return "Questions aren't available on this server."
  return err.message
}

/** A citation pill: the sentence number people count (idx + 1); the tooltip previews it. */
function CitationChip({ idx, sentence, onCite }) {
  return (
    <button type="button" className="vd-cite" onClick={() => onCite(idx)} aria-label={`Jump to sentence ${idx + 1}`} title={sentence?.text}>
      {idx + 1}
    </button>
  )
}

function Message({ message, sentences, onCite }) {
  if (message.role === 'question') {
    return (
      <p className="vd-q">
        <span className="vd-sr-only">You asked: </span>
        {message.text}
      </p>
    )
  }
  if (message.role === 'error') return <p className="vd-error">{message.text}</p>
  return (
    <div>
      <p className="vd-a">
        <span className="vd-sr-only">Answer: </span>
        {message.parts.map((part, i) =>
          'cite' in part ? (
            <CitationChip key={i} idx={part.cite} sentence={sentences[part.cite]} onCite={onCite} />
          ) : (
            <span key={i}>{part.text}</span>
          ),
        )}
      </p>
      {message.found && !message.grounded && (
        <p className="vd-a-note">This answer couldn&rsquo;t be linked to specific sentences.</p>
      )}
    </div>
  )
}

/**
 * Questions about the open document, in a panel that slides in from the right.
 * Always mounted while the document is open, so closing and reopening keeps the
 * conversation; ReaderPage's key resets it for another document. Memoised: its
 * props only change when it opens or closes.
 */
function AskPanel({ id, open, onClose, docId, sentences, onCite }) {
  const [state, dispatch] = useReducer(reducer, initialState)
  const [draft, setDraft] = useState('')
  // Message keys: crypto.randomUUID() doesn't exist on plain-HTTP pages served from an IP
  const nextId = useRef(0)
  const busy = useRef(false) // set synchronously: a double Enter can't send twice
  const abort = useRef(null)
  const textareaRef = useRef(null)
  const bodyRef = useRef(null)
  const titleId = useId()
  const inputId = useId()
  const hintId = useId()

  // Leaving the document cancels a pending question
  useEffect(() => {
    const controller = new AbortController()
    abort.current = controller
    return () => controller.abort()
  }, [])

  useEffect(() => {
    if (open) textareaRef.current?.focus()
  }, [open])

  // Keep the newest message in view
  useEffect(() => {
    const body = bodyRef.current
    if (open && body) body.scrollTop = body.scrollHeight
  }, [open, state.messages.length, state.pending])

  async function send(text = draft) {
    const question = text.trim()
    if (!question || busy.current) return
    busy.current = true
    dispatch({ type: 'asked', message: { id: nextId.current++, role: 'question', text: question } })
    setDraft('')
    textareaRef.current?.focus() // after a click on Send or a suggestion, typing continues in the box
    try {
      const answer = await askQuestion(docId, question, abort.current.signal)
      dispatch({ type: 'answered', message: { id: nextId.current++, role: 'answer', ...answer } })
    } catch (err) {
      if (err.name === 'AbortError') return
      dispatch({ type: 'failed', message: { id: nextId.current++, role: 'error', text: errorText(err) } })
    } finally {
      busy.current = false
    }
  }

  function onTextareaKeyDown(e) {
    // Enter sends, Shift+Enter is a new line; not while an IME is composing a character
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      send()
    }
  }

  const { messages, pending } = state
  const canSend = draft.trim().length > 0 && !pending
  return (
    <aside
      id={id}
      className="vd-ask"
      data-open={open}
      inert={!open}
      aria-labelledby={titleId}
      onKeyDown={(e) => {
        if (e.key === 'Escape') {
          e.stopPropagation()
          onClose()
        }
      }}
    >
      <div className="vd-ask-head">
        <h2 id={titleId}>Ask this document</h2>
        <button type="button" className="vd-icon-btn" onClick={onClose} aria-label="Close questions">
          <Icon name="close" size="sm" />
        </button>
      </div>

      <div ref={bodyRef} className="vd-ask-body" role="log" aria-labelledby={titleId}>
        {messages.length === 0 ? (
          <div className="vd-ask-empty">
            Answers come only from this document, with links to the sentences they&rsquo;re based on.
            <div className="vd-ask-suggest">
              {SUGGESTIONS.map((s) => (
                <button type="button" key={s} onClick={() => send(s)} aria-disabled={pending || undefined}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <ul className="vd-ask-list">
            {messages.map((m) => (
              <li key={m.id}>
                <Message message={m} sentences={sentences} onCite={onCite} />
              </li>
            ))}
          </ul>
        )}
        {pending && (
          <div className="vd-typing">
            <span />
            <span />
            <span />
            <span className="vd-sr-only">Looking through the document…</span>
          </div>
        )}
      </div>

      <form
        className="vd-ask-form"
        onSubmit={(e) => {
          e.preventDefault()
          send()
        }}
      >
        <div className="vd-ask-field">
          <label htmlFor={inputId} className="vd-sr-only">
            Your question
          </label>
          <textarea
            ref={textareaRef}
            id={inputId}
            rows={2}
            value={draft}
            maxLength={MAX_QUESTION}
            placeholder="What would you like to know?"
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={onTextareaKeyDown}
            // Read-only rather than disabled while waiting: a disabled box drops focus,
            // and Space would then reach the page's play/pause shortcut
            readOnly={pending}
            aria-disabled={pending || undefined}
            aria-describedby={hintId}
          />
          <button type="submit" className="vd-send" aria-disabled={!canSend || undefined} aria-label="Send question">
            <Icon name="send" size="sm" />
          </button>
        </div>
        <p className="vd-hint" id={hintId}>
          {draft.length}/{MAX_QUESTION} · Shift+Enter for a new line
        </p>
      </form>
    </aside>
  )
}

export default memo(AskPanel)
