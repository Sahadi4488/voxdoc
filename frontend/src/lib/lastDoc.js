// The last document that opened successfully, so "Open Reader" on the landing page
// can return to it. Like the voice preferences, it lives in this browser only.
const KEY = 'voxdoc:last-doc'

export function loadLastDoc() {
  try {
    return localStorage.getItem(KEY)
  } catch {
    return null // storage blocked (private mode)
  }
}

export function saveLastDoc(docId) {
  try {
    localStorage.setItem(KEY, docId)
  } catch {
    // not remembered: "Open Reader" then asks for an upload
  }
}

export function forgetLastDoc(docId) {
  try {
    if (localStorage.getItem(KEY) === docId) localStorage.removeItem(KEY)
  } catch {
    // nothing to forget
  }
}
