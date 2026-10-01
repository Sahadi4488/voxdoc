import { useEffect, useState } from 'react'
import ReaderPage from './components/ReaderPage'
import Uploader from './components/Uploader'

// The open document lives in the URL (?doc=<public id>): refresh-safe and shareable.
const docIdFromUrl = () => new URLSearchParams(window.location.search).get('doc')

function navigate(docId) {
  const url = new URL(window.location.href)
  if (docId) url.searchParams.set('doc', docId)
  else url.searchParams.delete('doc')
  window.history.pushState(null, '', url)
}

export default function App() {
  const [docId, setDocId] = useState(docIdFromUrl)

  // Back/forward buttons
  useEffect(() => {
    const onPop = () => setDocId(docIdFromUrl())
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [])

  const open = (id) => {
    navigate(id)
    setDocId(id)
  }

  return (
    <main className={`mx-auto max-w-[40rem] px-6 pt-16 ${docId ? 'pb-40' : 'pb-16'}`}>
      <header className="flex items-baseline justify-between gap-4">
        <p className="font-bold tracking-wide">VoxDoc</p>
        {docId && (
          <button
            type="button"
            onClick={() => open(null)}
            className="cursor-pointer text-sm font-bold text-pen underline underline-offset-4 outline-offset-4 outline-pen hover:text-ink focus-visible:outline-2"
          >
            Upload another file
          </button>
        )}
      </header>

      {docId ? (
        // key: a different document mounts a fresh ReaderPage (player, prefs, everything)
        <ReaderPage key={docId} docId={docId} />
      ) : (
        <>
          <h1 className="mt-10 font-reading text-headline font-semibold">Listen to any document.</h1>
          <p className="mt-4 font-reading text-reading">
            Upload a PDF or Word file. VoxDoc reads it aloud and highlights each word as it&rsquo;s
            spoken.
          </p>
          <Uploader onUploaded={(meta) => open(meta.id)} />
        </>
      )}
    </main>
  )
}
