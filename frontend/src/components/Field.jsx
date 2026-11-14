import React from 'react'

// Labelled text input shared by the Login and Register screens.
export default function Field({ label, helper, id, ...props }) {
  const inputId = id || `field-${String(label).toLowerCase().replace(/[^a-z0-9]+/g, '-')}`
  return (
    <div>
      <label
        htmlFor={inputId}
        className="block text-[10px] mono uppercase text-[#737373] mb-1.5 font-semibold"
      >
        {label}
      </label>
      <input
        id={inputId}
        className="w-full mono text-xs bg-[#0e0e0e] border border-[#333333] px-3 py-2.5 text-white outline-none focus:border-white transition-colors"
        {...props}
      />
      {helper && <p className="text-[10px] mono text-[#737373] mt-1">{helper}</p>}
    </div>
  )
}
