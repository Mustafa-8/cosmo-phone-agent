import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import { fileURLToPath } from 'node:url'

const repositoryRoot = fileURLToPath(new URL('../', import.meta.url))
const voiceWeb = fileURLToPath(new URL('../voice/web/', import.meta.url))

export default defineConfig({
  plugins: [react()],
  publicDir: voiceWeb,
  server: {
    fs: { allow: [repositoryRoot] },
    proxy: {
      '/api': 'http://127.0.0.1:8001',
      '/ws': { target: 'ws://127.0.0.1:8001', ws: true },
    },
  },
})
