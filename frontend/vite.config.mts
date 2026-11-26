import { fileURLToPath } from 'node:url'
import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig(({ mode }) => {
  const root = fileURLToPath(new URL('.', import.meta.url))
  const env = loadEnv(mode, root, '')
  const proxy = { '/api': { target: env.SPORT_API_TARGET || 'http://127.0.0.1:8000', changeOrigin: true } }
  return {
    root,
    plugins: [vue(), {
      name: 'assessment-offline-shell',
      apply: 'build',
      generateBundle(_, bundle) {
        const runner = readFileSync(new URL('./public/runner.webp', import.meta.url))
        const source = readFileSync(new URL('./sw.js', import.meta.url), 'utf8')
        const files = [...new Set(['/index.html', '/runner.webp', ...Object.keys(bundle).map((name) => `/${name}`)])]
        const version = createHash('sha256').update(files.join('\n')).update(source).update(runner).digest('hex').slice(0, 16)
        this.emitFile({ type: 'asset', fileName: 'sw.js', source: source.replace('__CACHE_VERSION__', version).replace('/* SHELL_FILES */ []', JSON.stringify(files)) })
      },
    }],
    server: { host: '127.0.0.1', port: 5173, proxy },
    preview: { host: '127.0.0.1', port: 4173, proxy },
  }
})
