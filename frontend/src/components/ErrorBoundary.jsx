import { Component } from 'react'
import { focusRing } from '../lib/styles'

/**
 * Catches a crash while rendering a document, so a bug shows a message instead
 * of a blank page. React 19 still needs a class for this: there's no hook for
 * getDerivedStateFromError / componentDidCatch. App keys it by document, so
 * opening another document starts over.
 */
export default class ErrorBoundary extends Component {
  state = { crashed: false }

  static getDerivedStateFromError() {
    return { crashed: true }
  }

  componentDidCatch(error, info) {
    console.error('VoxDoc: rendering the document failed', error, info.componentStack)
  }

  render() {
    if (!this.state.crashed) return this.props.children
    return (
      <div role="alert" className="mt-10">
        <p className="text-error">Something went wrong while showing this document. Reload the page.</p>
        <button
          type="button"
          onClick={() => window.location.reload()}
          className={`mt-4 cursor-pointer rounded-md bg-pen px-4 py-2 font-bold text-paper hover:bg-ink ${focusRing}`}
        >
          Reload
        </button>
      </div>
    )
  }
}
