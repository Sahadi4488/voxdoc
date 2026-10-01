import { useState } from 'react'
import { uploadDocument } from '../api'

const MAX_MB = 20
const EXTENSIONS = ['.pdf', '.docx']

function validate(file) {
  const name = file.name.toLowerCase()
  if (!EXTENSIONS.some((ext) => name.endsWith(ext))) {
    return 'VoxDoc reads PDF and Word (.docx) files. Choose one of those.'
  }
  if (file.size > MAX_MB * 1024 * 1024) {
    return `This file is larger than ${MAX_MB} MB. Choose a smaller one.`
  }
  return null
}

export default function Uploader({ onUploaded }) {
  // One status instead of isUploading/isError/isDone booleans: impossible
  // combinations (uploading AND error) can't be represented.
  const [status, setStatus] = useState('idle') // 'idle' | 'uploading' | 'error' | 'done'
  const [message, setMessage] = useState('')
  // Independent of status: a user can drag a new file while an error shows.
  const [isDragging, setIsDragging] = useState(false)
  const busy = status === 'uploading'

  async function handleFile(file) {
    if (!file || busy) return
    const problem = validate(file) // `accept` doesn't apply to dropped files
    if (problem) {
      setStatus('error')
      setMessage(problem)
      return
    }
    setStatus('uploading')
    setMessage(`Preparing ${file.name}…`)
    try {
      const doc = await uploadDocument(file)
      setStatus('done')
      setMessage('')
      onUploaded(doc)
    } catch (err) {
      setStatus('error')
      setMessage(err.message)
    }
  }

  function handleChange(e) {
    const file = e.target.files[0]
    e.target.value = '' // so choosing the same file again still fires onChange
    handleFile(file)
  }

  function handleDragOver(e) {
    e.preventDefault() // without this, drop never fires and the browser opens the file
    e.dataTransfer.dropEffect = busy ? 'none' : 'copy'
    if (!busy) setIsDragging(true)
  }

  function handleDragLeave(e) {
    // dragleave also fires when the pointer moves onto a child: ignore those
    if (e.currentTarget.contains(e.relatedTarget)) return
    setIsDragging(false)
  }

  function handleDrop(e) {
    e.preventDefault()
    setIsDragging(false)
    handleFile(e.dataTransfer.files[0])
  }

  return (
    <section aria-label="Upload a document" className="mt-10">
      <div
        onDragEnter={handleDragOver}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={`rounded-md border-2 border-dashed px-6 py-8 ${
          isDragging ? 'border-pen bg-pen/5' : 'border-rule'
        }`}
      >
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
          <label
            className={`inline-block rounded-md bg-pen px-4 py-2 font-bold text-paper outline-offset-2 outline-pen has-[:focus-visible]:outline-2 ${
              busy ? 'cursor-wait opacity-60' : 'cursor-pointer hover:bg-ink'
            }`}
          >
            <input
              type="file"
              accept=".pdf,.docx"
              className="sr-only"
              disabled={busy}
              onChange={handleChange}
            />
            Choose a file
          </label>
          <span className="text-graphite">{isDragging ? 'Drop it to upload' : 'or drop it here'}</span>
        </div>
        <p className="mt-3 text-sm text-graphite">PDF or .docx, up to {MAX_MB} MB</p>
      </div>

      {/* Always rendered: screen readers only announce changes to a live region that already exists */}
      <p
        aria-live="polite"
        className={`mt-4 min-h-[1.5em] ${status === 'error' ? 'text-error' : 'text-graphite'}`}
      >
        {message}
      </p>
    </section>
  )
}
