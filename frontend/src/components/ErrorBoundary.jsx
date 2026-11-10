import React from 'react'
import Icon from './Icon.jsx'

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, errorInfo) {
    console.error('ChattamAI Uncaught Application Error:', error, errorInfo)
  }

  handleReload = () => {
    window.location.reload()
  }

  handleReturnHome = () => {
    this.setState({ hasError: false, error: null })
    window.location.assign('/')
  }

  render() {
    if (this.state.hasError) {
      const errorMessage =
        this.state.error?.message ||
        (typeof this.state.error === 'string'
          ? this.state.error
          : 'An unexpected application exception occurred.')

      return (
        <div
          role="alert"
          aria-live="assertive"
          className="min-h-screen bg-[#0a0a0a] text-[#f5f5f5] flex items-center justify-center p-6 blueprint-grid relative"
        >
          <div className="max-w-xl w-full bg-[#121212] border border-[#262626] p-8 shadow-2xl space-y-6 relative z-10">
            <div className="border-b border-[#262626] pb-4 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 bg-[#ef4444] inline-block" />
                <span className="text-[10px] mono text-[#ef4444] font-bold uppercase tracking-widest">
                  SYSTEM FAULT // RUNTIME EXCEPTION
                </span>
              </div>
              <span className="text-[10px] mono text-[#737373] border border-[#262626] px-2 py-0.5">
                FAULT ISOLATION
              </span>
            </div>

            <div className="space-y-3">
              <div className="w-12 h-12 border border-white bg-white text-black flex items-center justify-center font-mono font-bold text-xl">
                !
              </div>
              <h1 className="text-2xl font-bold font-sans text-white uppercase tracking-tight">
                Something went wrong
              </h1>
              <p className="text-xs text-[#a3a3a3] mono leading-relaxed">
                An unhandled error interrupted the component tree. The boundary caught this error before application state corrupted.
              </p>
            </div>

            <div className="p-4 bg-[#0e0e0e] border border-[#262626] text-xs mono text-[#fca5a5] break-words leading-relaxed overflow-x-auto">
              <span className="text-[#737373] select-none block text-[10px] uppercase mb-1">
                ERROR DIAGNOSTIC:
              </span>
              <code>{errorMessage}</code>
            </div>

            <div className="flex flex-col sm:flex-row gap-3 pt-2">
              <button
                type="button"
                onClick={this.handleReload}
                className="flex-1 bg-white text-black font-mono font-bold text-xs uppercase px-5 py-3 border border-white hover:bg-[#e5e5e5] transition-colors cursor-pointer flex items-center justify-center gap-2"
              >
                <Icon name="refresh-cw" className="text-sm" />
                <span>RELOAD APPLICATION</span>
              </button>
              <button
                type="button"
                onClick={this.handleReturnHome}
                className="flex-1 text-xs mono uppercase text-[#a3a3a3] hover:text-white border border-[#333333] hover:border-white bg-[#0e0e0e] px-5 py-3 transition-colors cursor-pointer flex items-center justify-center gap-2"
              >
                <Icon name="layout-dashboard" className="text-sm" />
                <span>RETURN TO DASHBOARD</span>
              </button>
            </div>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}
