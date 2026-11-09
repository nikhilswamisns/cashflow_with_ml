import { Component, type ErrorInfo, type ReactNode } from 'react'

/** A crash in one page should show a message, not a blank screen. Resets when the route changes (via `resetKey`). */
export class ErrorBoundary extends Component<{ children: ReactNode; resetKey?: string }, { error: Error | null }> {
  state = { error: null as Error | null }
  static getDerivedStateFromError(error: Error) {
    return { error }
  }
  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error(error, info.componentStack)
  }
  componentDidUpdate(prev: { resetKey?: string }) {
    if (this.state.error && prev.resetKey !== this.props.resetKey) this.setState({ error: null })
  }
  render() {
    if (!this.state.error) return this.props.children
    return (
      <main className="page">
        <div className="card placeholder">
          <h2>Something went wrong on this page</h2>
          <p>{this.state.error.message}</p>
          <p>
            <button className="btn" onClick={() => location.reload()}>
              Reload
            </button>
          </p>
        </div>
      </main>
    )
  }
}
