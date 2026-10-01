// 10 ms of silence. Played synchronously inside a click so browsers that only
// allow play() during the user gesture itself (Safari) unlock the element
// before we await the network.
const SILENCE =
  'data:audio/wav;base64,UklGRsQAAABXQVZFZm10IBAAAAABAAEAQB8AAIA+AAACABAAZGF0YaAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'

const unlocked = new WeakSet()

/** Call synchronously in a click handler, before any await. Safe to call repeatedly. */
export function unlockAudio(audio) {
  if (unlocked.has(audio)) return
  unlocked.add(audio)
  audio.src = SILENCE
  audio.play().catch(() => {}) // interrupted by the caller's pause()/src swap: expected
  audio.pause()
}

/** True while the element holds the unlock clip (its events aren't real playback). */
export const isUnlockClip = (audio) => audio.src.startsWith('data:')
