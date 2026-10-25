import React, { useEffect, useRef } from 'react'
import Icon from '../Icon.jsx'
import Button from './Button.jsx'

export default function Modal({
  isOpen,
  onClose,
  title,
  subtitle,
  children,
  footer,
  maxWidth = 'max-w-2xl',
}) {
  const dialogRef = useRef(null)
  const previousActiveElement = useRef(null)

  useEffect(() => {
    if (!isOpen) return

    previousActiveElement.current = document.activeElement

    // Prevent background scrolling
    const originalOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'

    // Focus the first focusable element inside dialog or dialog itself
    const focusable = dialogRef.current?.querySelectorAll(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    )
    if (focusable && focusable.length > 0) {
      focusable[0].focus()
    } else {
      dialogRef.current?.focus()
    }

    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        onClose?.()
        return
      }

      if (e.key === 'Tab') {
        const focusableNodes = Array.from(
          dialogRef.current?.querySelectorAll(
            'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
          ) || []
        )
        if (focusableNodes.length === 0) return

        const first = focusableNodes[0]
        const last = focusableNodes[focusableNodes.length - 1]

        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault()
          last.focus()
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault()
          first.focus()
        }
      }
    }

    window.addEventListener('keydown', handleKeyDown)

    return () => {
      document.body.style.overflow = originalOverflow
      window.removeEventListener('keydown', handleKeyDown)
      if (previousActiveElement.current && typeof previousActiveElement.current.focus === 'function') {
        previousActiveElement.current.focus()
      }
    }
  }, [isOpen, onClose])

  if (!isOpen) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6"
      data-testid="modal-wrapper"
    >
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/80 backdrop-blur-xs transition-opacity"
        onClick={onClose}
        data-testid="modal-backdrop"
        aria-hidden="true"
      />

      {/* Dialog Window */}
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
        tabIndex={-1}
        className={`relative z-10 w-full ${maxWidth} bg-[#121212] border border-[#333333] shadow-2xl flex flex-col max-h-[85vh] fade-rise focus:outline-none`}
      >
        {/* Header */}
        <div className="px-5 py-4 border-b border-[#262626] bg-[#181818] flex items-center justify-between">
          <div>
            <h2
              id="modal-title"
              className="text-xs mono font-bold text-white tracking-widest uppercase flex items-center gap-2"
            >
              <span className="w-1.5 h-1.5 bg-white inline-block" />
              <span>{title}</span>
            </h2>
            {subtitle && (
              <p className="text-[10px] mono text-[#737373] mt-0.5">{subtitle}</p>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close dialog"
            className="p-1 text-[#737373] hover:text-white border border-transparent hover:border-[#333333] transition-colors focus-visible:ring-1 focus-visible:ring-white focus-visible:outline-none"
          >
            <Icon name="x" className="text-base" />
          </button>
        </div>

        {/* Content Body */}
        <div className="p-5 overflow-y-auto flex-1 text-xs">{children}</div>

        {/* Footer */}
        {footer && (
          <div className="px-5 py-3.5 border-t border-[#262626] bg-[#0e0e0e] flex items-center justify-end gap-2">
            {footer}
          </div>
        )}
      </div>
    </div>
  )
}
