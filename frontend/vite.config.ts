import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Served by FastAPI at /ui3/, so every asset URL must start with /ui3/.
export default defineConfig({
  base: '/ui3/',
  plugins: [react()],
  build: { outDir: 'dist', sourcemap: false },
})
