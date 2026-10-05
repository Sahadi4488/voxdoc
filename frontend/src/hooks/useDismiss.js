import { useEffect, useRef } from 'react'

/**
 * Closes a popover on a pointer press outside `ref` or on Escape.
 * onClose(viaEscape) runs with the latest closure, without re-subscribing.
 */
export function useDismiss(ref, open, onClose) {
  const onCloseRef = useRef(onClose)
  useEffect(() => {
    onCloseRef.current = onClose
  })

  useEffect(() => {
    if (!open) return
    const onPointer = (e) => {
      if (ref.current && !ref.current.contains(e.target)) onCloseRef.current(false)
    }
    const onKey = (e) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        onCloseRef.current(true)
      }
    }
    document.addEventListener('pointerdown', onPointer)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('pointerdown', onPointer)
      document.removeEventListener('keydown', onKey)
    }
  }, [ref, open])
}
