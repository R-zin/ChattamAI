import React from 'react'
import Icon from '../Icon.jsx'

export default function Button({
  children,
  variant = 'primary',
  size = 'md',
  loading = false,
  disabled = false,
  icon = null,
  iconRight = null,
  fullWidth = false,
  className = '',
  type = 'button',
  onClick,
  'aria-label': ariaLabel,
  ...props
}) {
  const baseStyles =
    'font-semibold uppercase tracking-wider inline-flex items-center justify-center transition-all duration-150 cursor-pointer select-none disabled:opacity-40 disabled:cursor-not-allowed border'

  const variants = {
    primary: 'bg-accent text-on-accent border-accent hover:bg-accent-strong hover:border-accent-strong',
    secondary: 'bg-surface-2 text-ink border-line hover:bg-surface-3 hover:border-line-strong',
    outline: 'bg-transparent text-ink border-line-strong hover:border-ink hover:bg-surface',
    ghost: 'bg-transparent text-ink-2 border-transparent hover:text-ink hover:bg-surface-2',
    danger: 'bg-danger/10 text-danger border-danger/40 hover:bg-danger/10 hover:border-danger/40',
  }

  const sizes = {
    sm: 'px-2.5 py-1 text-[10px] gap-1.5',
    md: 'px-4 py-2 text-xs gap-2',
    lg: 'px-5 py-2.5 text-sm gap-2.5',
  }

  const currentVariant = variants[variant] || variants.primary
  const currentSize = sizes[size] || sizes.md
  const widthClass = fullWidth ? 'w-full' : ''

  return (
    <button
      type={type}
      disabled={disabled || loading}
      aria-busy={loading}
      aria-label={ariaLabel}
      onClick={onClick}
      className={`${baseStyles} ${currentVariant} ${currentSize} ${widthClass} ${className}`}
      {...props}
    >
      {loading ? (
        <Icon name="loader" className="animate-spin text-current" />
      ) : (
        icon && (typeof icon === 'string' ? <Icon name={icon} className="text-current" /> : icon)
      )}
      <span>{children}</span>
      {!loading &&
        iconRight &&
        (typeof iconRight === 'string' ? <Icon name={iconRight} className="text-current" /> : iconRight)}
    </button>
  )
}
