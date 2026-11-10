import React, { useEffect, useState } from 'react'
import ReactDOM from 'react-dom'
import Icon from './Icon.jsx'

let push = null

export function toast(msg, tone = 'info') {
  if (push) push({ msg, tone, id: Math.random().toString(36).slice(2) })
}

const TONE_CONFIG = {
  ok: {
    border: 'border-l-white',
    iconColor: 'text-white',
    icon: 'check-circle',
  },
  warn: {
    border: 'border-l-[#f59e0b]',
    iconColor: 'text-[#fcd34d]',
    icon: 'alert-triangle',
  },
  danger: {
    border: 'border-l-[#ef4444]',
    iconColor: 'text-[#fca5a5]',
    icon: 'alert-triangle',
  },
  info: {
    border: 'border-l-white',
    iconColor: 'text-white',
    icon: 'info',
  },
}

export function ToastHost() {
  const [items, setItems] = useState([])
  useEffect(() => {
    push = (t) => {
      setItems((x) => [...x, t])
      setTimeout(() => setItems((x) => x.filter((i) => i.id !== t.id)), 3200)
    }
    return () => { push = null }
  }, [])
  return ReactDOM.createPortal(
    <div
      role="status"
      aria-live="polite"
      className="fixed bottom-6 right-6 z-[100] space-y-2 pointer-events-none"
    >
      {items.map((t) => {
        const config = TONE_CONFIG[t.tone] || TONE_CONFIG.info
        return (
          <div
            key={t.id}
            className={`fade-rise bg-[#121212] border border-[#404040] border-l-2 ${config.border} px-4 py-3 shadow-2xl flex items-center gap-3 max-w-sm pointer-events-auto`}
          >
            <Icon name={config.icon} className={`${config.iconColor} shrink-0`} />
            <span className="text-xs mono text-[#f5f5f5] leading-snug">{t.msg}</span>
          </div>
        )
      })}
    </div>,
    document.body
  )
}
