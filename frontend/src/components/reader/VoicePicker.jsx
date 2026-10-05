import { useEffect, useId, useRef, useState } from 'react'
import { getTts } from '../../api'
import { useDismiss } from '../../hooks/useDismiss'
import { isUnlockClip, unlockAudio } from '../../lib/audio'
import { voiceDescription } from '../../lib/voices'
import Icon from '../ui/Icon'

/**
 * The voice chip and its popover: the presets as a radio group (arrows change the
 * voice straight away), each with a preview of the current sentence in that voice.
 */
export default function VoicePicker({ voices, voiceId, speed, onVoiceChange, docId, currentIdx, onPreviewStart }) {
  const [open, setOpen] = useState(false)
  const wrapRef = useRef(null) // trigger AND popover: a click on the trigger isn't "outside"
  const triggerRef = useRef(null)
  const listRef = useRef(null)
  const popoverId = useId()
  const selected = voices.find((v) => v.id === voiceId)

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
      const clip = await getTts({ docId, idx: currentIdx, voice: voice.id, speed })
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

  // Every way of closing (trigger, Escape, outside press) stops any preview
  const close = (returnFocus) => {
    stopPreview()
    setOpen(false)
    if (returnFocus) triggerRef.current?.focus()
  }
  useDismiss(wrapRef, open, close)

  // On open, focus the checked voice: arrows then change the voice at once
  useEffect(() => {
    if (open) listRef.current?.querySelector('input:checked')?.focus()
  }, [open])

  return (
    <div className="vd-popover-anchor" ref={wrapRef}>
      <button
        ref={triggerRef}
        type="button"
        className="vd-chip-btn"
        aria-expanded={open}
        aria-controls={popoverId}
        aria-label={`Voice: ${selected?.name ?? 'loading'}`}
        onClick={() => (open ? close(false) : setOpen(true))}
      >
        <Icon name="wave" size="sm" />
        <span className="vd-chip-label">{selected?.name ?? 'Voice'}</span>
      </button>

      {open && (
        <div id={popoverId} ref={listRef} className="vd-popover vd-popover--up vd-popover--start" role="dialog" aria-label="Voice" style={{ width: 320 }}>
          <fieldset className="vd-fieldset">
            <legend className="vd-popover-title">Choose a voice</legend>
            <div className="vd-voice-list">
              {voices.map((v) => {
                const checked = v.id === voiceId
                const p = previewing?.id === v.id ? previewing.status : null
                return (
                  <div key={v.id} className="vd-voice-row">
                    <label className="vd-option">
                      <input
                        type="radio"
                        name={`${popoverId}-voice`}
                        value={v.id}
                        checked={checked}
                        onChange={() => onVoiceChange(v.id)}
                        className="vd-sr-only"
                      />
                      <span className="vd-option-check">{checked && <Icon name="check" size="sm" />}</span>
                      <span className="vd-option-body">
                        <span className="vd-option-name">{v.name}</span>
                        <span className="vd-option-desc">{voiceDescription(v)}</span>
                      </span>
                    </label>
                    <button
                      type="button"
                      className="vd-icon-btn"
                      aria-label={p ? `Stop preview of ${v.name}` : `Preview ${v.name}`}
                      data-state={p ?? undefined}
                      onClick={() => startPreview(v)}
                    >
                      <Icon name={p === 'playing' ? 'stop' : 'speaker'} size="sm" />
                    </button>
                  </div>
                )
              })}
            </div>
          </fieldset>
        </div>
      )}
    </div>
  )
}
