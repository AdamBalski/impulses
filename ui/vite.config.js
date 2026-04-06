import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

export default defineConfig(({ mode, command }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const apiUrl = env.VITE_API_URL || process.env.VITE_API_URL || '/impulses/api'
  const base = command === 'serve' ? '/' : '/impulses/'
  
  return {
    base,
    plugins: [react()],
    resolve: {
      alias: {
        '@impulses/sdk-typescript': path.resolve(__dirname, '../client-sdks/typescript/src/index.ts'),
      },
    },
    server: {
      host: '0.0.0.0',
      port: 3001,
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
