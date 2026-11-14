import React from 'react'

// Labelled text input shared by the Login and Register screens.
export default function Field({ label, helper, id, ...props }) {
  const inputId = id || `field-${String(label).toLowerCase().replace(/[^a-z0-9]+/g, '-')}`
  return (
    <div>
      <label
        htmlFor={inputId}
        className="block text-[11px] uppercase tracking-wider text-ink font-bold mb-1.5"
      >
        {label}
      </label>
      <input
        id={inputId}
        className="w-full text-sm bg-surface border border-line-strong px-3 py-2.5 text-ink placeholder:text-ink-3 outline-none focus:border-accent focus:ring-2 focus:ring-accent/30 disabled:opacity-50 transition-colors"
        {...props}
      />
      {helper && <p className="text-xs text-ink-2 mt-1.5">{helper}</p>}
    </div>
  )
}
