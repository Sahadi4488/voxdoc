/*
  Voice preferences live in the browser, not the database: with no accounts,
  the browser is the listener's identity, a preference belongs to the listener
  rather than the document, and it adds no API surface to secure.
  (Wrong choice once there are accounts: preferences should follow the user
  across devices, so they'd belong on the server.)
*/
export const MIN_SPEED = 0.5
export const MAX_SPEED = 2
export const SPEED_STEP = 0.05

const docKey = (docId) => `voxdoc:prefs:${docId}`
const LAST_KEY = 'voxdoc:prefs:last'

/** Snap to the slider grid and drop float noise (0.1 steps give 1.2000000000000002). */
export const roundSpeed = (x) => Number((Math.round(x / SPEED_STEP) * SPEED_STEP).toFixed(2))

/** "1.0×", "1.1×", "0.85×", "2.0×" */
export function formatSpeed(x) {
  const two = x.toFixed(2)
  return `${two.endsWith('0') ? x.toFixed(1) : two}×`
}

function read(key) {
  try {
    return JSON.parse(localStorage.getItem(key) ?? 'null') // throws on corrupt data
  } catch {
    return null // corrupt, or storage blocked (private mode)
  }
}

/** Raw stored preferences, unvalidated: this document's, else the last used, else null. */
export function loadPrefs(docId) {
  const isObject = (v) => v !== null && typeof v === 'object'
  const own = read(docKey(docId))
  if (isObject(own)) return own
  const last = read(LAST_KEY)
  return isObject(last) ? last : null
}

export function savePrefs(docId, prefs) {
  try {
    const json = JSON.stringify(prefs)
    localStorage.setItem(docKey(docId), json)
    localStorage.setItem(LAST_KEY, json)
  } catch {
    // storage full or blocked: preferences just won't persist
  }
}

/** Valid {voice, speed} for these presets; anything unknown falls back without crashing. */
export function validatePrefs(raw, voices) {
  const fallback = voices.find((v) => v.is_default) ?? voices[0]
  const preset = voices.find((v) => v.id === raw?.voice)
  if (!preset) return { voice: fallback.id, speed: fallback.default_speed }
  const speed = Number(raw.speed)
  const valid = Number.isFinite(speed) && speed >= MIN_SPEED && speed <= MAX_SPEED
  return { voice: preset.id, speed: valid ? roundSpeed(speed) : preset.default_speed }
}
