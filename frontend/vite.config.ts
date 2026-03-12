import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  base: '/stock/',
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/stock/api': {
        target: 'http://localhost:8000',
        rewrite: (path) => path.replace(/^\/stock/, ''),
      },
    },
  },
})
