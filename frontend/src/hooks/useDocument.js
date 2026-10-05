import { useEffect, useState } from 'react'
import { getDocument } from '../api'

// Documents the upload sheet already fetched: the reader opens with them at once
// instead of asking the server again. Kept for the page's lifetime: a document
// never changes after upload, and there is one entry per upload.
const primed = new Map()

export function primeDocument(doc) {
  primed.set(doc.id, doc)
}

/** Loads a document (with sentences) by public id. status: 'idle' | 'loading' | 'ready' | 'error' */
export function useDocument(docId) {
  // The last finished request, tagged with its docId. "Loading" is derived:
  // the stored result belongs to a different docId than the one asked for.
  const [result, setResult] = useState({ docId: null, doc: null, error: null })
  const primedDoc = docId ? primed.get(docId) : undefined

  useEffect(() => {
    if (!docId || primed.has(docId)) return
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
  if (primedDoc) return { status: 'ready', doc: primedDoc, error: null }
  if (result.docId !== docId) return { status: 'loading', doc: null, error: null }
  if (result.error) return { status: 'error', doc: null, error: result.error }
  return { status: 'ready', doc: result.doc, error: null }
}
