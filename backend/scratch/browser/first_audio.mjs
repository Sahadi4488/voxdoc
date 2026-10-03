// Day 15: time to first audio as a visitor sees it, on the production setup (uvicorn
// serving the built frontend, Kokoro loaded at startup).
//
//   cd frontend; npm run build
//   cd <a folder with Playwright installed>   # npm i playwright (uses installed Edge)
//   node <repo>\backend\scratch\browser\first_audio.mjs
//
// Per trial: empty audio cache, fresh browser context (no HTTP cache), open sample.pdf,
// then press Play either as soon as it appears or after 3 s on the page (the player
// prefetches sentence 0 while idle). Measures the click until the audio's 'playing'
// event, then a jump: click sentence 8 (never prefetched) until 'playing' again.
import { createRequire } from 'node:module'
import { spawn, execSync } from 'node:child_process'
import { mkdtempSync, readFileSync, readdirSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

const { chromium } = createRequire(join(process.cwd(), 'noop.js'))('playwright') // from the cwd, not a project dependency
const BACKEND = fileURLToPath(new URL('../..', import.meta.url))
const PYTHON = join(BACKEND, '.venv', 'Scripts', 'python.exe')
const APP = 'http://127.0.0.1:7860'
const TRIALS = 5 // per mode
const JUMP_TO = 8
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
const data = mkdtempSync(join(tmpdir(), 'voxdoc-first-audio-'))
const server = spawn(PYTHON, ['-m', 'uvicorn', 'app.main:app', '--port', '7860'], {
  cwd: BACKEND, stdio: 'ignore',
  env: { ...process.env, PYTHONWARNINGS: 'ignore', HF_HUB_OFFLINE: '1', VOXDOC_WARM_TTS: 'true', VOXDOC_GROQ_API_KEY: '', VOXDOC_DATA_DIR: data },
})
const stop = () => { try { execSync(`taskkill /PID ${server.pid} /T /F`, { stdio: 'ignore' }) } catch {} }
process.on('exit', stop)
for (let i = 0; i < 400; i++) { try { if ((await fetch(`${APP}/api/health`)).ok) break } catch {} await sleep(300) }

const form = new FormData()
form.append('file', new Blob([readFileSync(join(BACKEND, 'tests', 'fixtures', 'sample.pdf'))]), 'sample.pdf')
const { id } = await (await fetch(`${APP}/api/documents`, { method: 'POST', body: form })).json()
const doc = await (await fetch(`${APP}/api/documents/${id}`)).json()
const words = (i) => doc.sentences[i].text.split(/\s+/).length
console.log(`sentence 0: ${words(0)} words "${doc.sentences[0].text}"; sentence ${JUMP_TO}: ${words(JUMP_TO)} words\n`)

const browser = await chromium.launch({ channel: 'msedge' })
const atOnce = [], waited = [], jump = []
for (let t = 0; t < 2 * TRIALS; t++) {
  const wait = t % 2 === 1 // alternate the modes, so drift affects both alike
  for (const f of readdirSync(join(data, 'audio_cache'))) rmSync(join(data, 'audio_cache', f))
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } })
  await ctx.addInitScript(() => {
    window.__playing = []
    const play = HTMLMediaElement.prototype.play
    HTMLMediaElement.prototype.play = function () {
      if (!this.__timed) { this.__timed = true; this.addEventListener('playing', () => window.__playing.push(performance.now())) }
      return play.call(this)
    }
  })
  const page = await ctx.newPage()
  await page.goto(`${APP}/?doc=${doc.id}`)
  const playBtn = page.locator('button[aria-label="Play"]')
  await playBtn.waitFor()
  if (wait) await sleep(3000)
  const clickAt = await playBtn.evaluate((b) => { const at = performance.now(); b.click(); return at })
  await page.waitForFunction(() => window.__playing.length > 0, null, { timeout: 30000 })
  const ms = (await page.evaluate(() => window.__playing[0])) - clickAt
  ;(wait ? waited : atOnce).push(ms)

  await page.locator('button[aria-label="Pause"]').click()
  await sleep(2000) // let the prefetch of sentence 1 finish: measure the jump alone
  const n = await page.evaluate(() => window.__playing.length)
  const jumpAt = await page.locator(`[data-idx="${JUMP_TO}"]`).evaluate((el) => { const at = performance.now(); el.click(); return at })
  await page.waitForFunction((n) => window.__playing.length > n, n, { timeout: 30000 })
  jump.push((await page.evaluate(() => window.__playing.at(-1))) - jumpAt)
  console.log(`trial ${t + 1} ${wait ? 'Play after 3 s' : 'Play at once  '}: ${ms.toFixed(0).padStart(5)} ms; jump to sentence ${JUMP_TO}: ${jump.at(-1).toFixed(0)} ms`)
  await ctx.close()
}
const median = (xs) => [...xs].sort((a, b) => a - b)[Math.floor(xs.length / 2)]
const fmt = (xs) => `median ${median(xs).toFixed(0)} ms (${Math.min(...xs).toFixed(0)}-${Math.max(...xs).toFixed(0)}, n=${xs.length})`
console.log(`\nPlay at once -> audio: ${fmt(atOnce)}\nPlay after 3 s -> audio: ${fmt(waited)}\nJump to an uncached sentence -> audio: ${fmt(jump)}`)
await browser.close()
stop()
rmSync(data, { recursive: true, force: true })
