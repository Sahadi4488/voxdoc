// In dev, VITE_API_URL (.env.development) points at the FastAPI server.
// Unset in production builds, so requests go to the same origin.
export const API_URL = import.meta.env.VITE_API_URL ?? ''

const NETWORK_ERROR = "Can't reach the VoxDoc server. Start the backend and try again."

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

/** Absolute URL for an audio path returned by /tts (e.g. "/audio/<key>.wav"). */
export function audioUrl(path) {
  return `${API_URL}${path}`
}

async function request(path, options, failure) {
  let res
  try {
    res = await fetch(`${API_URL}${path}`, options)
  } catch (err) {
    if (err.name === 'AbortError') throw err // cancelled on purpose, not a failure
    // fetch only rejects on network failure (TypeError: Failed to fetch)
    throw new Error(NETWORK_ERROR)
  }
  if (!res.ok) throw new Error(await errorMessage(res, failure))
  return res.json()
}

async function errorMessage(res, failure) {
  let detail
  try {
    detail = (await res.json()).detail
  } catch {
    // not JSON (e.g. a proxy error page)
  }
  // FastAPI: a string for HTTPException, a list of {msg, ...} for validation errors
  if (typeof detail === 'string' && detail) return detail
  if (Array.isArray(detail) && detail.length) return detail.map((d) => d.msg).join(' ')
  return `${failure} (HTTP ${res.status}).`
}
