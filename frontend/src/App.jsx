import { useState } from 'react'
import Uploader from './components/Uploader'

export default function App() {
  const [doc, setDoc] = useState(null)

  return (
    <main className="mx-auto max-w-[40rem] px-6 py-16">
      <p className="font-bold tracking-wide">VoxDoc</p>

      {doc === null ? (
        <>
          <h1 className="mt-10 font-reading text-headline font-semibold">Listen to any document.</h1>
          <p className="mt-4 font-reading text-reading">
            Upload a PDF or Word file. VoxDoc reads it aloud and highlights each word as it&rsquo;s
            spoken.
          </p>
          <Uploader onUploaded={setDoc} />
        </>
      ) : (
        // Placeholder: Day 7 replaces this with the Reader
        <section className="mt-10">
          <h1 className="font-reading text-section font-semibold">{doc.title} is ready.</h1>
          <p className="mt-2 font-reading text-reading">
            {doc.sentence_count} {doc.sentence_count === 1 ? 'sentence' : 'sentences'}.
          </p>
          <button
            type="button"
            onClick={() => setDoc(null)}
            className="mt-6 cursor-pointer font-bold text-pen underline underline-offset-4 outline-offset-4 outline-pen hover:text-ink focus-visible:outline-2"
          >
            Upload another file
          </button>
        </section>
      )}
    </main>
  )
}
