import { useRef, useState } from 'react'
import Icon from '../ui/Icon'

/**
 * The drop surface. The native file input is visually hidden but still the thing
 * that opens the picker; the surface itself is a button for keyboards and
 * screen readers.
 */
export default function UploadDropzone({ maxMb, onFile }) {
  const inputRef = useRef(null)
  const [over, setOver] = useState(false)

  return (
    <div
      className={`vd-drop ${over ? 'vd-drop--over' : ''}`}
      role="button"
      tabIndex={0}
      aria-label={`Choose a document: PDF or Word (.docx), up to ${maxMb} MB. You can also drop a file here.`}
      onClick={() => inputRef.current?.click()}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          inputRef.current?.click()
        }
      }}
      onDragEnter={(e) => {
        e.preventDefault()
        setOver(true)
      }}
      onDragOver={(e) => {
        e.preventDefault() // without this, drop never fires and the browser opens the file
        e.dataTransfer.dropEffect = 'copy'
        setOver(true)
      }}
      onDragLeave={(e) => {
        // dragleave also fires when the pointer moves onto a child: ignore those
        if (!e.currentTarget.contains(e.relatedTarget)) setOver(false)
      }}
      onDrop={(e) => {
        e.preventDefault()
        setOver(false)
        const file = e.dataTransfer.files?.[0]
        if (file) onFile(file)
      }}
    >
      <span className="vd-drop-icon">
        <Icon name="arrowUp" />
      </span>
      <p className="vd-drop-title">{over ? 'Release to upload' : 'Drop your file here'}</p>
      <span className="vd-drop-browse">
        or <u>browse files</u>
      </span>
      <span className="vd-drop-meta">PDF · DOCX · {maxMb} MB</span>
      <input
        ref={inputRef}
        className="vd-sr-only"
        type="file"
        accept=".pdf,.docx"
        tabIndex={-1}
        aria-hidden="true"
        onClick={(e) => e.stopPropagation()} // the surface's click handler would open it twice
        onChange={(e) => {
          const file = e.target.files?.[0]
          e.target.value = '' // so choosing the same file again still fires onChange
          if (file) onFile(file)
        }}
      />
    </div>
  )
}
