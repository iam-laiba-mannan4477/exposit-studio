import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// In development the interface runs on port 5173 and forwards /api to the studio on 8600.
// In normal use the built files in dist/ are served by the studio itself, on one port.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { '/api': 'http://127.0.0.1:8600' } },
  build: { outDir: 'dist', sourcemap: false },
})
