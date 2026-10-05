// Every call goes to /api on the page's own origin: FastAPI serves the built app in
// production, and Vite's dev server proxies /api to FastAPI (vite.config.js). One
// origin in both, so no CORS anywhere.
const API = '/api'

const NETWORK_ERROR = "Can't reach the VoxDoc server. Check your connection and try again."

/** Upload a PDF/DOCX. Resolves to the stored document; throws Error with a readable message. */
export async function uploadDocument(file) {
  const form = new FormData()
  form.append('file', file) // must match the FastAPI parameter name
  // No Content-Type header: the browser sets multipart/form-data with its boundary.
  return request('/documents', { method: 'POST', body: form }, 'Upload failed')
}

/** A document with its sentences, by public id. */
export async function getDocument(docId, signal) {
  return request(`/documents/${encodeURIComponent(docId)}`, { signal }, 'Could not open the document')
}

/** The voice presets (voices.py is the single source of truth). */
export async function getVoices() {
  return request('/voices', {}, 'Could not load the voices')
}

/** Audio + word timings for one sentence. `speed` undefined -> the preset's default. */
export async function getTts({ docId, idx, voice, speed }) {
  return request(
    '/tts',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ doc_id: docId, sentence_idx: idx, voice, speed }),
    },
    'Could not prepare the audio',
  )
}

/** The document's summary: generated on the first call (a few seconds), cached after that. */
export async function summarizeDocument(docId, signal) {
  return request(
    `/documents/${encodeURIComponent(docId)}/summary`,
    { method: 'POST', signal },
    'Could not summarize the document',
  )
}

/** Ask a question about the document: { parts, citations, found, grounded }. */
export async function askQuestion(docId, question, signal) {
  return request(
    `/documents/${encodeURIComponent(docId)}/ask`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question }),
      signal,
    },
    'Could not answer the question',
  )
}

async function request(path, options, failure) {
  let res
  try {
    res = await fetch(`${API}${path}`, options)
  } catch (err) {
    if (err.name === 'AbortError') throw err // cancelled on purpose, not a failure
    // fetch only rejects on network failure (TypeError: Failed to fetch)
    throw new Error(NETWORK_ERROR)
  }
  if (!res.ok) {
    const { message, code } = await errorDetails(res, failure)
    const err = new Error(message)
    err.status = res.status
    if (code) err.code = code // e.g. "rate_limited": the visitor's own limit, not a busy server
    // Seconds to wait after a 429 (same origin, so the header is readable)
    const retryAfter = Number.parseInt(res.headers.get('Retry-After'), 10)
    if (retryAfter > 0) err.retryAfter = retryAfter
    throw err
  }
  return res.json()
}

async function errorDetails(res, failure) {
  let body = {}
  try {
    body = await res.json()
  } catch {
    // not JSON (e.g. a proxy error page)
  }
  const { detail, code } = body ?? {}
  // FastAPI: a string for HTTPException, a list of {msg, ...} for validation errors
  if (typeof detail === 'string' && detail) return { message: detail, code }
  if (Array.isArray(detail) && detail.length) return { message: detail.map((d) => d.msg).join(' '), code }
  return { message: `${failure} (HTTP ${res.status}).`, code }
}
