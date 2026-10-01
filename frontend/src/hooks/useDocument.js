import { useEffect, useState } from 'react'
import { getDocument } from '../api'

/** Loads a document (with sentences) by public id. status: 'idle' | 'loading' | 'ready' | 'error' */
export function useDocument(docId) {
  // The last finished request, tagged with its docId. "Loading" is derived:
  // the stored result belongs to a different docId than the one asked for.
  const [result, setResult] = useState({ docId: null, doc: null, error: null })

  useEffect(() => {
    if (!docId) return
    const controller = new AbortController()
    getDocument(docId, controller.signal)
      .then((doc) => setResult({ docId, doc, error: null }))
      .catch((err) => {
        if (err.name !== 'AbortError') setResult({ docId, doc: null, error: err.message })
      })
    // A newer docId (or unmount) cancels this request, so a slow old response can't win
    return () => controller.abort()
  }, [docId])

  if (!docId) return { status: 'idle', doc: null, error: null }
  if (result.docId !== docId) return { status: 'loading', doc: null, error: null }
  if (result.error) return { status: 'error', doc: null, error: result.error }
  return { status: 'ready', doc: result.doc, error: null }
}
