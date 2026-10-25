import React from 'react'
import Icon from '../Icon.jsx'
import Button from './Button.jsx'

export default function EmptyState({
  icon = 'folder',
  eyebrow = 'NO RECORDS FOUND',
  title = 'No Data Available',
  description = 'There are no active records matching the current parameters or filter criteria.',
  actionLabel,
  onAction,
  actionIcon,
  className = '',
}) {
  return (
    <div
      role="status"
      className={`border border-[#262626] bg-[#121212] p-8 md:p-12 text-center flex flex-col items-center justify-center relative overflow-hidden ${className}`}
    >
      <div className="blueprint-grid absolute inset-0 opacity-30 pointer-events-none" />

      <div className="relative z-10 flex flex-col items-center max-w-md">
        <div className="w-12 h-12 border border-[#404040] bg-[#181818] flex items-center justify-center mb-4">
          <Icon name={icon} className="text-xl text-white" />
        </div>

        {eyebrow && (
          <span className="text-[9px] mono font-bold text-[#737373] tracking-widest uppercase mb-1">
            {eyebrow}
          </span>
        )}

        <h3 className="text-sm mono font-bold text-white tracking-wide uppercase mb-2">
          {title}
        </h3>

        <p className="text-xs text-[#a3a3a3] leading-relaxed mb-6">
          {description}
        </p>

        {actionLabel && onAction && (
          <Button
            variant="primary"
            size="md"
            icon={actionIcon}
            onClick={onAction}
          >
            {actionLabel}
          </Button>
        )}
      </div>
    </div>
  )
}
