import { memo, useEffect, useId, useReducer, useRef, useState } from 'react'
import { askQuestion } from '../api'
import { focusRing } from '../lib/styles'
import { formatMinutes, formatWait } from '../lib/wait'

const MAX_QUESTION = 500 // the backend's limit too (AskRequest)

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

const CloseIcon = () => (
  <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M6 6l12 12M18 6 6 18" />
  </svg>
)

/** Shows the sentence number people count (idx + 1); the title previews the sentence. */
function CitationChip({ idx, sentence, onCite }) {
  return (
    <button
      type="button"
      onClick={() => onCite(idx)}
      aria-label={`Jump to sentence ${idx + 1}`}
      title={sentence?.text}
      className={`mx-0.5 cursor-pointer rounded-full border border-pen px-1.5 font-ui text-sm leading-tight font-bold text-pen hover:bg-pen hover:text-paper ${focusRing}`}
    >
      {idx + 1}
    </button>
  )
}

function Message({ message, sentences, onCite }) {
  if (message.role === 'question') {
    return (
      <p className="ml-8 rounded-md bg-rule/50 px-3 py-2 whitespace-pre-line">
        <span className="sr-only">You asked: </span>
        {message.text}
      </p>
    )
  }
  if (message.role === 'error') return <p className="text-sm text-error">{message.text}</p>
  return (
    <div>
      <p className="font-reading leading-7 whitespace-pre-line">
        <span className="sr-only">Answer: </span>
        {message.parts.map((part, i) =>
          'cite' in part ? (
            <CitationChip key={i} idx={part.cite} sentence={sentences[part.cite]} onCite={onCite} />
          ) : (
            <span key={i}>{part.text}</span>
          ),
        )}
      </p>
      {message.found && !message.grounded && (
        <p className="mt-1 text-sm text-graphite">This answer couldn't be linked to specific sentences.</p>
      )}
    </div>
  )
}

/**
 * Questions about the open document. Wide screens: fixed to the right, above
 * the player bar (index.css shifts the page left while it's open). Narrow
 * screens: covers the page. Always mounted while the document is open, so
 * closing and reopening keeps the conversation; ReaderPage's key resets it
 * for another document. Memoised: its props only change when it opens or closes.
 */
function ChatPanel({ id, open, onClose, docId, sentences, onCite, barRef }) {
  const [state, dispatch] = useReducer(reducer, initialState)
  const [draft, setDraft] = useState('')
  const [barHeight, setBarHeight] = useState(0)
  // Message keys: crypto.randomUUID() doesn't exist on plain-HTTP pages served from an IP
  const nextId = useRef(0)
  const busy = useRef(false) // set synchronously: a double Enter can't send twice
  const abort = useRef(null)
  const textareaRef = useRef(null)
  const listRef = useRef(null)
  const titleId = useId()
  const inputId = useId()
  const hintId = useId()

  // Leaving the document cancels a pending question
  useEffect(() => {
    const controller = new AbortController()
    abort.current = controller
    return () => controller.abort()
  }, [])

  // Wide screens: the panel ends where the player bar begins, whatever its height
  useEffect(() => {
    const bar = barRef.current
    if (!bar) return
    const observer = new ResizeObserver(() => setBarHeight(bar.offsetHeight))
    observer.observe(bar)
    return () => observer.disconnect()
  }, [barRef])

  useEffect(() => {
    if (open) textareaRef.current?.focus()
  }, [open])

  // Keep the newest message in view
  useEffect(() => {
    const list = listRef.current
    if (open && list) list.scrollTop = list.scrollHeight
  }, [open, state.messages.length, state.pending])

  async function send() {
    const question = draft.trim()
    if (!question || busy.current) return
    busy.current = true
    dispatch({ type: 'asked', message: { id: nextId.current++, role: 'question', text: question } })
    setDraft('')
    textareaRef.current?.focus() // after a click on Send, typing continues in the box
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
      aria-labelledby={titleId}
      hidden={!open}
      data-chat-open={open || undefined}
      onKeyDown={(e) => {
        if (e.key === 'Escape') {
          e.stopPropagation()
          onClose()
        }
      }}
      style={{ '--bar-h': `${barHeight}px` }}
      className="fixed inset-0 z-20 flex flex-col bg-paper lg:inset-auto lg:top-0 lg:right-0 lg:bottom-(--bar-h) lg:w-96 lg:border-l lg:border-rule"
    >
      <div className="flex items-center justify-between gap-4 border-b border-rule px-4 py-3">
        <h2 id={titleId} className="font-bold">
          Questions
        </h2>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close questions"
          className={`cursor-pointer rounded-md p-1 text-ink hover:text-pen ${focusRing}`}
        >
          <CloseIcon />
        </button>
      </div>

      <div ref={listRef} role="log" aria-labelledby={titleId} className="flex-1 overflow-y-auto px-4 py-4">
        {messages.length === 0 ? (
          <p className="text-graphite">Ask anything about this document. Answers link to the sentences they come from.</p>
        ) : (
          <ul className="flex flex-col gap-4">
            {messages.map((m) => (
              <li key={m.id}>
                <Message message={m} sentences={sentences} onCite={onCite} />
              </li>
            ))}
          </ul>
        )}
        {pending && <p className="mt-4 text-sm text-graphite">Looking through the document…</p>}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault()
          send()
        }}
        className="border-t border-rule px-4 py-3"
      >
        <label htmlFor={inputId} className="sr-only">
          Your question
        </label>
        <textarea
          ref={textareaRef}
          id={inputId}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={onTextareaKeyDown}
          maxLength={MAX_QUESTION}
          rows={3}
          // Read-only rather than disabled while waiting: a disabled box drops focus,
          // and Space would then reach the page's play/pause shortcut
          readOnly={pending}
          aria-disabled={pending || undefined}
          aria-describedby={hintId}
          placeholder="Ask a question"
          className={`block w-full resize-none rounded-md border border-rule bg-paper px-3 py-2 placeholder:text-graphite aria-disabled:opacity-60 ${focusRing}`}
        />
        <div className="mt-2 flex items-center justify-between gap-2 text-sm text-graphite">
          <span id={hintId}>
            {draft.length}/{MAX_QUESTION} · Shift+Enter for a new line
          </span>
          <button
            type="submit"
            aria-disabled={!canSend || undefined}
            className={`cursor-pointer rounded-md bg-pen px-3 py-1.5 font-bold text-paper hover:bg-ink aria-disabled:cursor-not-allowed aria-disabled:opacity-40 ${focusRing}`}
          >
            Send
          </button>
        </div>
      </form>
    </aside>
  )
}

export default memo(ChatPanel)
