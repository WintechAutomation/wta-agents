import path from 'path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      '@agents':    path.resolve(__dirname, '../config/agents.json'),
      '@knowledge': path.resolve(__dirname, '../config/knowledge.json'),
    },
  },
  server: {
    host: '0.0.0.0',
    port: 5557,
    proxy: {
      '/api': {
        target: 'http://localhost:5555',
        changeOrigin: true,
      },
      '/socket.io': {
        target: 'http://localhost:5555',
        changeOrigin: true,
        ws: true,
      },
    },
  },
  base: '/',
  build: {
    outDir: './static/v2',
    emptyOutDir: true,
  },
})
