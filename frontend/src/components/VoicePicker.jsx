import { useEffect, useId, useRef, useState } from 'react'
import { getTts } from '../api'
import { isUnlockClip, unlockAudio } from '../lib/audio'
import { formatSpeed, MAX_SPEED, MIN_SPEED, roundSpeed, SPEED_STEP } from '../lib/prefs'

const SPEED_COMMIT_MS = 400
const focusRing = 'outline-offset-2 outline-pen focus-visible:outline-2'

const CheckIcon = () => (
  <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="3">
    <path d="M5 12.5l4.5 4.5L19 7.5" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
)
const SpeakerIcon = () => (
  <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" fill="currentColor">
    <path d="M4 9.5h3.5L12 5.5v13l-4.5-4H4z" />
    <path d="M15.5 8.5a5 5 0 0 1 0 7M18 6a8.5 8.5 0 0 1 0 12" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
  </svg>
)
const StopIcon = () => (
  <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" fill="currentColor">
    <rect x="6.5" y="6.5" width="11" height="11" rx="1.5" />
  </svg>
)

/**
 * "Voice: Presenter" button that opens a panel with the presets (radio group,
 * each with a preview of the current sentence) and a debounced speed slider.
 */
export default function VoicePicker({ voices, voiceId, speed, onVoiceChange, onSpeedChange, docId, currentIdx, onPreviewStart }) {
  const [open, setOpen] = useState(false)
  const wrapperRef = useRef(null) // holds trigger AND panel, so a click on the trigger isn't "outside"
  const triggerRef = useRef(null)
  const panelRef = useRef(null)
  const panelId = useId()
  const selected = voices.find((v) => v.id === voiceId)


  // --- speed: the label follows the drag at once; the value commits 400 ms after the last change
  const [draft, setDraft] = useState(speed)
  const [shownSpeed, setShownSpeed] = useState(speed)
  if (speed !== shownSpeed) {
    // e.g. picking a preset loaded its default speed: the slider follows
    setShownSpeed(speed)
    setDraft(speed)
  }
  useEffect(() => {
    if (draft === speed) return // nothing to commit (also on mount)
    const t = setTimeout(() => onSpeedChange(draft), SPEED_COMMIT_MS)
    return () => clearTimeout(t) // each new drag step cancels the pending commit
  }, [draft, speed, onSpeedChange])

  // --- previews: the current sentence in another voice, on a separate audio element
  const previewRef = useRef(null)
  const previewTokenRef = useRef(0)
  const [previewing, setPreviewing] = useState(null) // { id, status: 'loading' | 'playing' }

  const stopPreview = () => {
    previewTokenRef.current++
    previewRef.current?.pause()
    setPreviewing(null)
  }

  async function startPreview(voice) {
    if (previewing?.id === voice.id) return stopPreview() // the same button stops it
    const audio = (previewRef.current ??= new Audio())
    unlockAudio(audio) // before any await (Safari)
    const token = ++previewTokenRef.current // a newer preview cancels this one
    audio.pause()
    onPreviewStart() // pauses main playback; it doesn't resume by itself afterwards
    setPreviewing({ id: voice.id, status: 'loading' })
    try {
      const clip = await getTts({ docId, idx: currentIdx, voice: voice.id, speed: draft })
      if (token !== previewTokenRef.current) return
      audio.src = clip.audio_url
      await audio.play()
      if (token === previewTokenRef.current) setPreviewing({ id: voice.id, status: 'playing' })
    } catch (err) {
      if (err.name !== 'AbortError' && token === previewTokenRef.current) setPreviewing(null)
    }
  }

  // A preview that ends by itself clears its state; unmounting stops it
  useEffect(() => {
    const audio = (previewRef.current ??= new Audio())
    if (import.meta.env.DEV) window.__voxdocPreview = audio
    const onEnded = () => !isUnlockClip(audio) && setPreviewing(null)
    audio.addEventListener('ended', onEnded)
    return () => {
      audio.removeEventListener('ended', onEnded)
      audio.pause()
    }
  }, [])

  // Every way of closing (trigger, Escape, outside click) stops any preview
  const closePanel = (returnFocus) => {
    stopPreview()
    setOpen(false)
    if (returnFocus) triggerRef.current?.focus()
  }
  const closeRef = useRef(closePanel)
  useEffect(() => {
    closeRef.current = closePanel
  })

  // On open, focus the checked voice: arrows change the voice straight away
  // (a radio group is one Tab stop, and the preview buttons come first in DOM order)
  useEffect(() => {
    if (open) panelRef.current?.querySelector('input[type=radio]:checked')?.focus()
  }, [open])

  useEffect(() => {
    if (!open) return
    const onMouseDown = (e) => {
      if (!wrapperRef.current.contains(e.target)) closeRef.current(false)
    }
    const onKeyDown = (e) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        closeRef.current(true) // focus back on the "Voice" button
      }
    }
    document.addEventListener('mousedown', onMouseDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('mousedown', onMouseDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [open])

  return (
    <div ref={wrapperRef} className="relative">
      <button
        ref={triggerRef}
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => (open ? closePanel(false) : setOpen(true))}
        className={`cursor-pointer rounded-md px-2 py-1 text-sm text-graphite hover:text-pen ${focusRing}`}
      >
        Voice: <span className="font-bold text-ink">{selected?.name ?? '…'}</span>
        {speed !== selected?.default_speed && <span> · {formatSpeed(speed)}</span>}
      </button>

      {open && (
        <div
          ref={panelRef}
          id={panelId}
          className="absolute right-0 bottom-full mb-3 w-[min(24rem,calc(100vw-2rem))] rounded-md border border-rule bg-paper p-4"
        >
          <fieldset>
            <legend className="mb-2 text-sm font-bold">Voice</legend>
            <div className="flex flex-col gap-1">
              {voices.map((v) => {
                const checked = v.id === voiceId
                const p = previewing?.id === v.id ? previewing.status : null
                return (
                  <div
                    key={v.id}
                    className={`flex items-center gap-2 rounded-md px-3 py-2 ${
                      checked ? 'ring-2 ring-pen' : 'ring-1 ring-transparent hover:ring-rule'
                    } has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-pen`}
                  >
                    <label className="flex min-w-0 flex-1 cursor-pointer items-start gap-3">
                      <input
                        type="radio"
                        name={`${panelId}-voice`}
                        value={v.id}
                        checked={checked}
                        onChange={() => onVoiceChange(v.id)}
                        className="sr-only"
                      />
                      <span className="mt-0.5 w-[18px] shrink-0 text-pen">{checked && <CheckIcon />}</span>
                      <span className="min-w-0">
                        <span className="block font-bold">{v.name}</span>
                        <span className="block text-sm text-graphite">
                          {v.accent}, {v.gender} · {v.use}
                        </span>
                      </span>
                    </label>
                    <button
                      type="button"
                      aria-label={p ? `Stop preview of ${v.name}` : `Preview ${v.name}`}
                      onClick={() => startPreview(v)}
                      className={`shrink-0 cursor-pointer rounded-md p-2 hover:text-pen ${p ? 'text-pen' : 'text-graphite'} ${focusRing}`}
                    >
                      {p === 'loading' ? <span className="text-sm">…</span> : p ? <StopIcon /> : <SpeakerIcon />}
                    </button>
                  </div>
                )
              })}
            </div>
          </fieldset>

          <div className="mt-4 border-t border-rule pt-3">
            <label htmlFor={`${panelId}-speed`} className="text-sm font-bold">
              Speed {formatSpeed(draft)}
            </label>
            <input
              id={`${panelId}-speed`}
              type="range"
              min={MIN_SPEED}
              max={MAX_SPEED}
              step={SPEED_STEP}
              value={draft}
              onChange={(e) => setDraft(roundSpeed(Number(e.target.value)))} // a string, with float noise
              className={`mt-2 block w-full cursor-pointer rounded-sm accent-pen ${focusRing}`}
            />
            <div className="flex justify-between text-sm text-graphite" aria-hidden="true">
              <span>{formatSpeed(MIN_SPEED)}</span>
              <span>{formatSpeed(MAX_SPEED)}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
