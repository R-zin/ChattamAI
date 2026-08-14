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
        <div key={t.id} className="fade-rise bg-[#161D27] border border-[#222C3A] border-l-2 rounded px-4 py-3 shadow-2xl flex items-center gap-3 max-w-sm" style={{ borderLeftColor: t.tone === 'ok' ? 'var(--ok)' : 'var(--accent)' }}>
          <Icon name={t.tone === 'ok' ? 'check-circle' : 'info'} className={t.tone === 'ok' ? 'text-[#34D399]' : 'text-[#22D3EE]'} />
          <span className="text-xs text-[#E7ECF2] leading-snug">{t.msg}</span>
        </div>
      ))}
    </div>,
    document.body
  )
}
