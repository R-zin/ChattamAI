import React, { useId } from 'react'

export default function Slider({
  label,
  value,
  min = 0,
  max = 100,
  step = 1,
  unit = '',
  baseline = null,
  onChange,
  disabled = false,
  className = '',
  id: customId,
}) {
  const generatedId = useId()
  const id = customId || generatedId

  const percentage = Math.max(
    0,
    Math.min(100, ((parseFloat(value) - min) / (max - min)) * 100)
  )

  return (
    <div className={`space-y-1.5 ${className}`}>
      <div className="flex items-center justify-between text-xs">
        <label
          htmlFor={id}
          className="mono text-[11px] text-[#a3a3a3] uppercase tracking-wider font-semibold"
        >
          {label}
        </label>
        <div className="flex items-center gap-2">
          {baseline && (
            <span className="mono text-[10px] text-[#737373]">
              [{baseline}]
            </span>
          )}
          <span className="mono font-bold text-white bg-[#1a1a1a] border border-[#333333] px-2 py-0.5 text-xs">
            {value} {unit}
          </span>
        </div>
      </div>

      <div className="relative flex items-center h-6">
        <input
          id={id}
          type="range"
          min={min}
          max={max}
          step={step}
          value={value}
          disabled={disabled}
          onChange={(e) => onChange?.(parseFloat(e.target.value))}
          aria-label={label}
          aria-valuemin={min}
          aria-valuemax={max}
          aria-valuenow={value}
          aria-valuetext={`${value} ${unit}`}
          className="w-full h-1 bg-[#262626] appearance-none cursor-pointer focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-white disabled:opacity-40 disabled:cursor-not-allowed accent-white"
          style={{
            background: `linear-gradient(to right, #ffffff ${percentage}%, #262626 ${percentage}%)`,
          }}
        />
      </div>

      <div className="flex justify-between text-[9px] mono text-[#555555]">
        <span>
          {min} {unit}
        </span>
        <span>
          {max} {unit}
        </span>
      </div>
    </div>
  )
}
