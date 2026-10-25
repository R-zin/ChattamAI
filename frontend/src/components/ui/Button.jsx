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
    'mono font-bold uppercase tracking-wider inline-flex items-center justify-center transition-all duration-150 cursor-pointer select-none focus-visible:ring-1 focus-visible:ring-white focus-visible:outline-none disabled:opacity-40 disabled:cursor-not-allowed border'

  const variants = {
    primary: 'bg-white text-black border-white hover:bg-[#e5e5e5] hover:border-[#e5e5e5]',
    secondary: 'bg-[#181818] text-[#f5f5f5] border-[#333333] hover:bg-[#222222] hover:border-[#555555]',
    outline: 'bg-transparent text-[#f5f5f5] border-[#404040] hover:border-white hover:bg-[#121212]',
    ghost: 'bg-transparent text-[#a3a3a3] border-transparent hover:text-white hover:bg-[#181818]',
    danger: 'bg-[#220d0d] text-[#fca5a5] border-[#551a1a] hover:bg-[#331414] hover:border-[#772222]',
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
