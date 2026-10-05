/** "820 KB", "8.4 MB" */
export function formatBytes(bytes) {
  if (!Number.isFinite(bytes)) return ''
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

/** "PDF" | "DOCX", from a file name */
export function fileKind(name = '') {
  const ext = name.split('.').pop()?.toLowerCase()
  return ext === 'docx' ? 'DOCX' : ext === 'pdf' ? 'PDF' : (ext || 'FILE').toUpperCase()
}

// Measured (docs/measurements.md, 99 words per voice): the presets speak 126 to 143
// words a minute at 1.0x. 135 is the middle; the listening time is an estimate.
const WORDS_PER_MINUTE = 135

export function countWords(sentences) {
  let words = 0
  for (const s of sentences) words += s.text.split(/\s+/).filter(Boolean).length
  return words
}

/** Estimated listening minutes at this speed (at least 1). */
export function listenMinutes(words, speed = 1) {
  if (!words) return null
  return Math.max(1, Math.round(words / (WORDS_PER_MINUTE * speed)))
}

/** "Uploaded today", "Uploaded yesterday", "Uploaded 3 Oct 2026" (local time). */
export function uploadedLabel(iso, now = new Date()) {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return null
  const day = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime()
  const days = Math.round((day(now) - day(date)) / 86_400_000)
  if (days === 0) return 'Uploaded today'
  if (days === 1) return 'Uploaded yesterday'
  return `Uploaded ${date.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })}`
}
