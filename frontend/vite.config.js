import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      // Route all backend API calls through the Vite dev server to FastAPI on 8000.
      // Using a single /api prefix avoids any ambiguity between proxy key matching
      // and direct Axios calls. The rewrite strips /api so FastAPI sees the real path.
      //
      // IMPORTANT: The Axios client (src/api/client.js) must use baseURL: '/api'
      // so that all requests go through this proxy rule.
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
