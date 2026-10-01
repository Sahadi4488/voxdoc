import { useEffect, useMemo, useRef } from 'react'

// A paragraph that is one short sentence without terminal punctuation reads as a heading
const isHeading = (sentences) =>
  sentences.length === 1 && sentences[0].text.length < 80 && !/[.?!:;,]["'”’)]*$/.test(sentences[0].text)

const reducedMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches

/**
 * The document text, grouped into paragraphs. `activeIdx` (or null) gets the
 * highlighter; clicking a sentence calls onSentenceClick(idx).
 * `bottomInset()` returns the height covered by the fixed player bar.
 */
export default function Reader({ doc, activeIdx, onSentenceClick, bottomInset = () => 0 }) {
  const paragraphs = useMemo(() => {
    const groups = []
    for (const s of doc.sentences) {
      if (groups.at(-1)?.para !== s.para) groups.push({ para: s.para, sentences: [] })
      groups.at(-1).sentences.push(s)
    }
    return groups
  }, [doc])

  const activeRef = useRef(null)

  // Keep the spoken sentence in view without chasing it: scroll only when it
  // leaves the middle ~60% of the visible area, then centre it.
  useEffect(() => {
    const el = activeRef.current
    if (activeIdx === null || !el) return
    const visibleHeight = window.innerHeight - bottomInset()
    const rect = el.getBoundingClientRect()
    const comfortTop = visibleHeight * 0.2
    const comfortBottom = visibleHeight * 0.8
    if (rect.top >= comfortTop && rect.bottom <= comfortBottom) return
    window.scrollBy({
      top: rect.top + rect.height / 2 - visibleHeight / 2,
      behavior: reducedMotion() ? 'auto' : 'smooth',
    })
  }, [activeIdx, bottomInset])

  return (
    <article>
      <h1 className="font-reading text-section font-semibold">{doc.title}</h1>
      <div className="mt-6 font-reading text-reading">
        {paragraphs.map(({ para, sentences }) => (
          <p key={para} className={isHeading(sentences) ? 'mt-8 font-semibold' : 'mt-5'}>
            {sentences.map((s) => {
              const active = s.idx === activeIdx
              return (
                <span key={s.idx}>
                  <span
                    ref={active ? activeRef : null}
                    data-idx={s.idx}
                    aria-current={active ? 'true' : undefined}
                    onClick={() => onSentenceClick(s.idx)}
                    className={`cursor-pointer rounded-sm decoration-pen decoration-2 underline-offset-4 ${
                      active ? 'bg-highlighter box-decoration-clone' : 'hover:underline'
                    }`}
                  >
                    {s.text}
                  </span>{' '}
                </span>
              )
            })}
          </p>
        ))}
      </div>
    </article>
  )
}
