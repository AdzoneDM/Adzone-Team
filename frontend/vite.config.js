import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { fileURLToPath, URL } from 'node:url'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  // «@/» apunta a src/: los imports no dependen de dónde está cada archivo
  resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
  server: {
    proxy: {
      // Proxy para las solicitudes /api al backend Django
      '/api': {
        target: 'http://localhost:8000', // Tu servidor Django
        changeOrigin: true, // Necesario para hosts virtuales
        // secure: false, // Descomentar si tu backend Django corre en HTTPS con certificado autofirmado
        // rewrite: (path) => path.replace(/^\/api/, '/api') // Usualmente no es necesario si el prefijo es el mismo
      },
      // Fotos y PDF de evidencia de las tareas
      '/media': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      }
    }
  },
})
