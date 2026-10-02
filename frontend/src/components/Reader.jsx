import { memo, useEffect, useMemo, useRef } from 'react'

// A paragraph that is one short sentence without terminal punctuation reads as a heading
const isHeading = (sentences) =>
  sentences.length === 1 && sentences[0].text.length < 80 && !/[.?!:;,]["'”’)]*$/.test(sentences[0].text)

const reducedMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches

/**
 * One sentence. Memoised: a word change re-renders only the active sentence,
 * because every other sentence gets the same primitive props as before
 * (isActive false, wordStart/wordEnd null) and the same stable onClick.
 */
const Sentence = memo(function Sentence({ ref, idx, text, isActive, wordSync, wordStart, wordEnd, onClick }) {
  if (import.meta.env.DEV) (window.__sentenceRenders ??= {})[idx] = (window.__sentenceRenders[idx] ?? 0) + 1

  const hasWord = isActive && wordStart !== null && wordEnd !== null
  // The highlighter means "the voice is here", at two levels of focus: the sentence
  // faintly and the word at full strength. Without word timings, the whole sentence.
  const sentenceBg = isActive ? (wordSync ? 'bg-highlighter/35' : 'bg-highlighter') : ''
  return (
    <>
      <span
        ref={ref}
        data-idx={idx}
        aria-current={isActive ? 'true' : undefined}
        onClick={() => onClick(idx)}
        className={`cursor-pointer rounded-sm box-decoration-clone decoration-pen decoration-2 underline-offset-4 ${
          isActive ? sentenceBg : 'hover:underline'
        }`}
      >
        {hasWord ? (
          <>
            {text.slice(0, wordStart)}
            <mark className="rounded-sm bg-highlighter box-decoration-clone text-ink">{text.slice(wordStart, wordEnd)}</mark>
            {text.slice(wordEnd)}
          </>
        ) : (
          text
        )}
      </span>{' '}
    </>
  )
})

/**
 * The document text, grouped into paragraphs. `activeIdx` (or null) gets the
 * highlighter; clicking a sentence calls onSentenceClick(idx), which must be
 * stable (useCallback) for the memoised sentences to skip re-rendering.
 * `bottomInset()` returns the height covered by the fixed player bar.
 * `header` is shown under the title (the summary button and panel).
 */
export default function Reader({
  doc,
  activeIdx,
  wordSync,
  wordStart,
  wordEnd,
  onSentenceClick,
  bottomInset = () => 0,
  header = null,
}) {
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
      {header}
      <div className="mt-6 font-reading text-reading">
        {paragraphs.map(({ para, sentences }) => (
          <p key={para} className={isHeading(sentences) ? 'mt-8 font-semibold' : 'mt-5'}>
            {sentences.map((s) => {
              const active = s.idx === activeIdx
              return (
                <Sentence
                  key={s.idx}
                  ref={active ? activeRef : undefined}
                  idx={s.idx}
                  text={s.text}
                  isActive={active}
                  wordSync={active && wordSync}
                  wordStart={active ? wordStart : null}
                  wordEnd={active ? wordEnd : null}
                  onClick={onSentenceClick}
                />
              )
            })}
          </p>
        ))}
      </div>
    </article>
  )
}
