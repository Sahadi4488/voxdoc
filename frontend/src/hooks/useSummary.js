import { useCallback, useEffect, useRef, useState } from 'react'
import { summarizeDocument } from '../api'
import { formatWait } from '../lib/wait'

function errorText(err) {
  if (err.status === 429) return `The summary service is busy. Try again in ${formatWait(err.retryAfter ?? 10)}.`
  if (err.status === 503) return "Summaries aren't available on this server."
  return err.message
}

/**
 * The document's summary, fetched only when asked for: the free Groq quota is too
 * small to summarise every document. Lives in ReaderPage, so switching between
 * the document and the summary keeps it.
 * Returns [state, generate]; state.status: 'idle' | 'loading' | 'done' | 'error'.
 */
export function useSummary(docId) {
  const [state, setState] = useState({ status: 'idle' })
  const busy = useRef(false) // set synchronously: a fast double-click can't start two requests
  const abort = useRef(null)

  // Leaving the document cancels a running request
  useEffect(() => {
    const controller = new AbortController()
    abort.current = controller
    return () => controller.abort()
  }, [])

  const generate = useCallback(async () => {
    if (busy.current) return
    busy.current = true
    setState({ status: 'loading' })
    try {
      const summary = await summarizeDocument(docId, abort.current.signal)
      setState({ status: 'done', summary })
    } catch (err) {
      if (err.name !== 'AbortError') setState({ status: 'error', message: errorText(err) })
    } finally {
      busy.current = false
    }
  }, [docId])

  return [state, generate]
}
