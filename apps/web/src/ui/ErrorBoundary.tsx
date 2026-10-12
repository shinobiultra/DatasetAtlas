import { Component, type ErrorInfo, type ReactNode } from 'react'
import { VIEW_PREFERENCE_KEYS } from '../lib/storedValue'

function resetViewPreferences() {
  try { for (const key of VIEW_PREFERENCE_KEYS) localStorage.removeItem(key) } catch { /* storage unavailable */ }
  window.location.reload()
}

/** Without a boundary, one render error unmounts the whole app and leaves a blank page. */
export class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state: { error: Error | null } = { error: null }

  static getDerivedStateFromError(error: Error) { return { error } }

  componentDidCatch(error: Error, info: ErrorInfo) { console.error(error, info.componentStack) }

  render() {
    const { error } = this.state
    if (!error) return this.props.children
    return (
      <main role="alert" style={{ maxWidth: 640, margin: '12vh auto', padding: '0 20px' }}>
        <h1>Dataset Atlas could not draw this page</h1>
        <p className="hint">The details are also in the browser console. If it keeps happening after a reload, resetting the saved view preferences usually fixes it; starred datasets and notes are kept.</p>
        <pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{error.message}</pre>
        <div className="row" style={{ gap: 8 }}>
          <button type="button" className="btn primary" onClick={() => window.location.reload()}>Reload</button>
          <button type="button" className="btn" onClick={resetViewPreferences}>Reset view preferences and reload</button>
        </div>
      </main>
    )
  }
}
