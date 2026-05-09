import { Component, type ErrorInfo, type ReactNode } from 'react'

interface Props { children: ReactNode }
interface State { error: Error | null }

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error('Render error', error, info)
  }

  render() {
    if (!this.state.error) return this.props.children
    return (
      <div style={{ padding: 24, fontFamily: 'sans-serif' }}>
        <h1>Something went wrong</h1>
        <pre style={{ color: 'var(--red)', whiteSpace: 'pre-wrap' }}>{this.state.error.message}</pre>
        <button onClick={() => location.reload()} style={{ marginTop: 12 }}>Reload</button>
      </div>
    )
  }
}
