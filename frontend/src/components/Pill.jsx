import React from 'react'

// Status chip: a square glyph plus a text label (never colour alone). The colour
// comes from the pill-* class (see index.css).
export default function Pill({ kind = 'info', children, dot = true }) {
  return (
    <span className={`status-pill ${kind}`}>
      {dot && <span aria-hidden="true" />}
      {children}
    </span>
  )
}
