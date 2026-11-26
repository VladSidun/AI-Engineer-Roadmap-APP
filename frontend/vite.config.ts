import react from '@vitejs/plugin-react'
import tailwind from '@tailwindcss/vite'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [react(), tailwind()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': { target: `http://127.0.0.1:${process.env.QUEST_PORT ?? '8000'}` },
      '/health': { target: `http://127.0.0.1:${process.env.QUEST_PORT ?? '8000'}` },
    },
  },
  test: { environment: 'jsdom', include: ['src/**/*.test.ts?(x)'] },
})
