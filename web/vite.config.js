import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Serve the /api/* serverless handlers under `vite dev` so the front end can call
// them locally exactly as it will on Vercel. On Vercel these files run natively.
function apiDevServer() {
  return {
    name: 'api-dev-server',
    configureServer(server) {
      server.middlewares.use(async (req, res, next) => {
        if (!req.url || !req.url.startsWith('/api/')) return next()
        const name = req.url.split('?')[0].replace('/api/', '')
        try {
          const mod = await server.ssrLoadModule(`/api/${name}.js`)
          await mod.default(req, res)
        } catch (e) {
          res.statusCode = 500
          res.setHeader('Content-Type', 'application/json')
          res.end(JSON.stringify({ error: String(e && e.message) }))
        }
      })
    },
  }
}

export default defineConfig({
  plugins: [react(), apiDevServer()],
  server: {
    port: 5173,
  },
})
