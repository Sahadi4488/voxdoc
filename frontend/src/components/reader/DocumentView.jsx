import { Fragment, memo, useEffect, useRef } from 'react'
import { isHeading } from '../../lib/document'

const reducedMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches

/**
 * One sentence. Memoised: a word change re-renders only the active sentence,
 * because every other sentence gets the same primitive props as before
 * (isActive false, wordStart/wordEnd null) and the same stable onClick.
 * The spoken word is cut out of the text by its character range (aligned on the
 * backend), so the highlight always lands on exactly the displayed characters.
 */
const Sentence = memo(function Sentence({ ref, idx, text, isActive, wordSync, wordStart, wordEnd, onClick }) {
  if (import.meta.env.DEV) (window.__sentenceRenders ??= {})[idx] = (window.__sentenceRenders[idx] ?? 0) + 1

  const hasWord = isActive && wordStart !== null && wordEnd !== null
  // Faint sentence + clear word; without word timings, the whole sentence at word strength
  const className = isActive ? (wordSync ? 'vd-sentence vd-sentence--active' : 'vd-sentence vd-sentence--whole') : 'vd-sentence'
  return (
    <>
      <span ref={ref} data-idx={idx} aria-current={isActive ? 'true' : undefined} onClick={() => onClick(idx)} className={className}>
        {hasWord ? (
          <>
            {text.slice(0, wordStart)}
            <mark className="vd-word">{text.slice(wordStart, wordEnd)}</mark>
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
 * The book-like page: a small metadata line, the title, then the text.
 * `activeIdx` (or null) is the sentence being read; clicking a sentence calls
 * onSentenceClick(idx), which must be stable for the memoised sentences.
 * `bottomInset()` is the height covered by the floating player.
 */
export default function DocumentView({
  doc,
  paragraphs,
  meta,
  uploaded,
  titleRef,
  activeIdx,
  wordSync,
  wordStart,
  wordEnd,
  onSentenceClick,
  bottomInset,
}) {
  // Dev only: ?crash makes this throw, to test the error boundary (stripped from builds)
  if (import.meta.env.DEV && new URLSearchParams(window.location.search).has('crash')) {
    throw new Error('Test crash (?crash)')
  }
  const activeRef = useRef(null)

  // Keep the spoken sentence in view without chasing it: scroll only when it
  // leaves the middle ~60% of the visible area, then centre it.
  useEffect(() => {
    const el = activeRef.current
    if (activeIdx === null || !el) return
    const visibleHeight = window.innerHeight - bottomInset()
    const rect = el.getBoundingClientRect()
    if (rect.top >= visibleHeight * 0.2 && rect.bottom <= visibleHeight * 0.8) return
    window.scrollBy({
      top: rect.top + rect.height / 2 - visibleHeight / 2,
      behavior: reducedMotion() ? 'auto' : 'smooth',
    })
  }, [activeIdx, bottomInset])

  return (
    <article className="vd-doc" aria-labelledby="vd-doc-title">
      <header className="vd-doc-header">
        <p className="vd-doc-meta">{meta}</p>
        <h1 className="vd-doc-title" id="vd-doc-title" ref={titleRef} tabIndex={-1}>
          {doc.title}
        </h1>
        {uploaded && <p className="vd-doc-sub">{uploaded}</p>}
      </header>

      <div className="vd-doc-body">
        {paragraphs.map(({ para, sentences, newPage }) => {
          const Tag = isHeading(sentences) ? 'h2' : 'p'
          return (
            <Fragment key={para}>
              {newPage !== null && (
                <div className="vd-page-break" role="separator" aria-label={`Page ${newPage}`}>
                  Page {newPage}
                </div>
              )}
              <Tag>
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
              </Tag>
            </Fragment>
          )
        })}
      </div>
    </article>
  )
}
