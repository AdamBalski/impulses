import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const apiUrl = env.VITE_API_URL || process.env.VITE_API_URL || '/impulses/api'
  
  return {
    base: '/impulses/',
    plugins: [react()],
    server: {
      port: 3000,
      proxy: {
        '/impulses/api': {
          target: apiUrl,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/impulses\/api/, '')
        }
      }
    }
  }
})
