import { useCallback, useEffect, useState } from 'react'
import ErrorBoundary from './components/ErrorBoundary'
import LandingPage from './components/landing/LandingPage'
import ReaderPage from './components/reader/ReaderPage'
import UploadModal from './components/upload/UploadModal'
import { useTheme } from './hooks/useTheme'
import { loadLastDoc } from './lib/lastDoc'

// The open document lives in the URL (?doc=<public id>): refresh-safe and shareable.
const docIdFromUrl = () => new URLSearchParams(window.location.search).get('doc')

function navigate(docId) {
  const url = new URL(window.location.href)
  if (docId) url.searchParams.set('doc', docId)
  else url.searchParams.delete('doc')
  url.hash = ''
  window.history.pushState(null, '', url)
}

/** Landing page, or the reader for ?doc=…; the upload sheet floats over either. */
export default function App() {
  const [docId, setDocId] = useState(docIdFromUrl)
  const [uploadOpen, setUploadOpen] = useState(false)
  const theme = useTheme()

  // Back/forward buttons
  useEffect(() => {
    const onPop = () => setDocId(docIdFromUrl())
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [])

  const open = useCallback((id) => {
    navigate(id)
    setDocId(id)
    window.scrollTo({ top: 0 })
  }, [])

  const openUpload = useCallback(() => setUploadOpen(true), [])
  const goHome = useCallback(() => open(null), [open])
  // "Open Reader": back to the last document, or start with an upload
  const openReader = useCallback(() => {
    const last = loadLastDoc()
    if (last) open(last)
    else setUploadOpen(true)
  }, [open])

  const upload = (
    <UploadModal
      open={uploadOpen}
      onClose={() => setUploadOpen(false)}
      onUploaded={(id) => {
        setUploadOpen(false)
        open(id)
      }}
    />
  )

  if (docId) {
    return (
      <>
        {/* key: another document mounts a fresh reader (player, prefs, everything) and a fresh boundary */}
        <ErrorBoundary key={docId} onHome={goHome}>
          <ReaderPage docId={docId} onHome={goHome} onNewDocument={openUpload} theme={theme} />
        </ErrorBoundary>
        {upload}
      </>
    )
  }
  return (
    <>
      <LandingPage onUploadClick={openUpload} onOpenReader={openReader} theme={theme} />
      {upload}
    </>
  )
}
