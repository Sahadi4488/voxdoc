/**
 * Sentences grouped into paragraphs, in order: [{ para, sentences, newPage }].
 * newPage: the PDF page number when this paragraph starts a later page than the
 * one before ended on, else null (always null for DOCX, which has no pages).
 */
export function groupParagraphs(sentences) {
  const groups = []
  let lastPage = sentences[0]?.page ?? null
  for (const s of sentences) {
    if (groups.at(-1)?.para !== s.para) {
      const newPage = s.page !== null && lastPage !== null && s.page > lastPage ? s.page : null
      groups.push({ para: s.para, sentences: [], newPage })
    }
    groups.at(-1).sentences.push(s)
    if (s.page !== null) lastPage = s.page
  }
  return groups
}

/** A paragraph that is one short sentence without terminal punctuation reads as a heading. */
export const isHeading = (sentences) =>
  sentences.length === 1 && sentences[0].text.length < 80 && !/[.?!:;,]["'”’)]*$/.test(sentences[0].text)

/** The contents list: one entry per heading, keyed by its sentence index. */
export function headings(paragraphs) {
  return paragraphs.filter((p) => isHeading(p.sentences)).map((p) => ({ idx: p.sentences[0].idx, label: p.sentences[0].text }))
}

/** Scroll a sentence (or heading) to the middle of the view. */
export function scrollToSentence(idx) {
  const el = document.querySelector(`[data-idx="${idx}"]`)
  if (!el) return
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  el.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'center' })
}
