import React, { useEffect, useState } from 'react'
import ReactDOM from 'react-dom'
import Icon from './Icon.jsx'

let push = null

export function toast(msg, tone = 'info') {
  if (push) push({ msg, tone, id: Math.random().toString(36).slice(2) })
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
    <div className="fixed bottom-6 right-6 z-[100] space-y-2">
      {items.map((t) => (
        <div
          key={t.id}
          className="fade-rise bg-[#121212] border border-[#404040] border-l-2 border-l-white px-4 py-3 shadow-2xl flex items-center gap-3 max-w-sm"
        >
          <Icon name={t.tone === 'ok' ? 'check-circle' : 'info'} className="text-white shrink-0" />
          <span className="text-xs mono text-[#f5f5f5] leading-snug">{t.msg}</span>
        </div>
      ))}
    </div>,
    document.body
  )
}
