/** @type {import('tailwindcss').Config} */

// Colours are CSS variables holding space-separated RGB triplets (see
// src/index.css) so every utility supports opacity (e.g. bg-ink/10) and the
// light/dark themes swap by changing the variables only.
const token = (name) => `rgb(var(--c-${name}) / <alpha-value>)`

export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        bg: token('bg'),
        surface: token('surface'),
        'surface-2': token('surface-2'),
        'surface-3': token('surface-3'),
        inset: token('inset'),
        line: token('line'),
        'line-strong': token('line-strong'),
        ink: token('ink'),
        'ink-2': token('ink-2'),
        'ink-3': token('ink-3'),
        accent: token('accent'),
        'accent-strong': token('accent-strong'),
        'on-accent': token('on-accent'),
        ok: token('ok'),
        warn: token('warn'),
        danger: token('danger'),
        info: token('info'),
        scrim: 'rgb(10 10 10 / 0.6)',
      },
      fontFamily: {
        // One grotesque sans throughout (Swiss Modernism): no monospace UI type.
        sans: ['Inter', 'system-ui', '-apple-system', 'Segoe UI', 'sans-serif'],
        mono: ['Inter', 'system-ui', '-apple-system', 'Segoe UI', 'sans-serif'],
        display: ['Inter', 'system-ui', 'sans-serif'],
      },
      borderRadius: {
        DEFAULT: '2px',
        sm: '2px',
        md: '2px',
        lg: '4px',
      },
    },
  },
  plugins: [],
}
