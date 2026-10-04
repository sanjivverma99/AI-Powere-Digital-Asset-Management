import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],

  server: {
    // Bind to all interfaces so Docker can expose the port
    host: '0.0.0.0',
    port: 5173,

    // Proxy /api/* → backend container so the browser never needs
    // to know the backend address (avoids CORS issues in Docker)
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
