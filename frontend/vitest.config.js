import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test/setup.js',
    css: false,
    // The suite exercises the offline demo data layer; live behaviour is
    // covered by src/test/liveMode.test.js, which stubs the env explicitly.
    env: { VITE_USE_MOCKS: 'true' },
  },
})
