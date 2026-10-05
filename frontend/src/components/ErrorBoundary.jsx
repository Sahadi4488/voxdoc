import { Component } from 'react'

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
      <div className="vd-boundary">
        <div className="vd-state" role="alert">
          <h1 className="vd-state-title">Something went wrong</h1>
          <p>Something went wrong while showing this document. Reload the page.</p>
          <div className="vd-state-actions">
            <button type="button" className="vd-btn vd-btn--dark" onClick={() => window.location.reload()}>
              Reload
            </button>
            {this.props.onHome && (
              <button type="button" className="vd-btn vd-btn--outline" onClick={this.props.onHome}>
                Back to home
              </button>
            )}
          </div>
        </div>
      </div>
    )
  }
}
