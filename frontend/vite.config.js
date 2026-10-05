import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
// /api goes to FastAPI, so the browser sees one origin, as in production where
// FastAPI serves the built app itself. 127.0.0.1, not localhost: on Windows
// localhost can resolve to IPv6 first, where uvicorn isn't listening.
const api = { '/api': 'http://127.0.0.1:8000' }

export default defineConfig({
  plugins: [react()],
  server: { proxy: api },
  preview: { proxy: api },
})
