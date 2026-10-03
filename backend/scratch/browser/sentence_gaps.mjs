// Day 15: silence between consecutive sentences while playing, with the player's prefetch
// on and off (?noprefetch, a switch that exists only in the dev build).
//
//   cd <a folder with Playwright installed>   # npm i playwright (uses installed Edge)
//   node <repo>\backend\scratch\browser\sentence_gaps.mjs
//
// Starts uvicorn on :8000 and Vite on :5173. Per run: empty audio cache, fresh browser
// context, Play on sample.pdf, let 8 sentences play; gap = the 'playing' event of clip n+1
// minus the 'ended' event of clip n.
import { createRequire } from 'node:module'
import { spawn, execSync } from 'node:child_process'
import { mkdtempSync, readFileSync, readdirSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

const { chromium } = createRequire(join(process.cwd(), 'noop.js'))('playwright') // from the cwd, not a project dependency
const ROOT = fileURLToPath(new URL('../../..', import.meta.url))
const APP = 'http://localhost:5173' // Vite listens on localhost, not 127.0.0.1
const CLIPS = 8
const RUNS = 2 // per mode
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
const data = mkdtempSync(join(tmpdir(), 'voxdoc-gaps-'))
const api = spawn(join(ROOT, 'backend', '.venv', 'Scripts', 'python.exe'), ['-m', 'uvicorn', 'app.main:app', '--port', '8000'], {
  cwd: join(ROOT, 'backend'), stdio: 'ignore',
  env: { ...process.env, PYTHONWARNINGS: 'ignore', HF_HUB_OFFLINE: '1', VOXDOC_WARM_TTS: 'true', VOXDOC_GROQ_API_KEY: '', VOXDOC_DATA_DIR: data },
})
const vite = spawn('node', [join(ROOT, 'frontend', 'node_modules', 'vite', 'bin', 'vite.js'), '--port', '5173', '--strictPort'], { cwd: join(ROOT, 'frontend'), stdio: 'ignore' })
const stop = () => { for (const p of [api, vite]) { try { execSync(`taskkill /PID ${p.pid} /T /F`, { stdio: 'ignore' }) } catch {} } }
process.on('exit', stop)
for (let i = 0; i < 400; i++) { try { if ((await fetch(`${APP}/api/health`)).ok) break } catch {} await sleep(300) }

const form = new FormData()
form.append('file', new Blob([readFileSync(join(ROOT, 'backend', 'tests', 'fixtures', 'sample.pdf'))]), 'sample.pdf')
const { id } = await (await fetch(`${APP}/api/documents`, { method: 'POST', body: form })).json()

const browser = await chromium.launch({ channel: 'msedge' })
const gaps = { prefetch: [], noprefetch: [] }
for (let r = 0; r < 2 * RUNS; r++) {
  const mode = r % 2 ? 'noprefetch' : 'prefetch'
  for (const f of readdirSync(join(data, 'audio_cache'))) rmSync(join(data, 'audio_cache', f))
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } })
  await ctx.addInitScript(() => {
    window.__ev = []
    const play = HTMLMediaElement.prototype.play
    HTMLMediaElement.prototype.play = function () {
      if (!this.__timed) {
        this.__timed = true
        for (const type of ['playing', 'ended']) this.addEventListener(type, () => window.__ev.push([type, performance.now()]))
      }
      return play.call(this)
    }
  })
  const page = await ctx.newPage()
  await page.goto(`${APP}/?doc=${id}${mode === 'noprefetch' ? '&noprefetch' : ''}`)
  await page.locator('button[aria-label="Play"]').click()
  await page.waitForFunction((n) => window.__ev.filter(([t]) => t === 'playing').length >= n, CLIPS, { timeout: 120000, polling: 100 })
  const ev = await page.evaluate(() => window.__ev)
  const run = []
  for (let i = 0; i < ev.length - 1; i++) if (ev[i][0] === 'ended' && ev[i + 1][0] === 'playing') run.push(ev[i + 1][1] - ev[i][1])
  gaps[mode].push(...run)
  console.log(`${mode.padEnd(10)} run: ${run.map((g) => g.toFixed(0)).join(', ')} ms`)
  await ctx.close()
}
const median = (xs) => [...xs].sort((a, b) => a - b)[Math.floor(xs.length / 2)]
for (const [mode, xs] of Object.entries(gaps)) console.log(`${mode}: median ${median(xs).toFixed(0)} ms, range ${Math.min(...xs).toFixed(0)}-${Math.max(...xs).toFixed(0)} ms, n=${xs.length}`)
await browser.close()
stop()
rmSync(data, { recursive: true, force: true })
