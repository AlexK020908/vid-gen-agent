import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// `npm run dev` serves the UI on :5173 with hot reload and forwards everything else to `run.py serve` on :8000.
const server = 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': server,
      '/media': server,
      '/ws': { target: server.replace('http', 'ws'), ws: true },
    },
  },
})
