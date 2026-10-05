import { createContext, useContext } from 'react'

export const ReaderContext = createContext(null)

/** Reading preferences and drawer state, shared by the reader's shell and sidebar. */
export function useReader() {
  const ctx = useContext(ReaderContext)
  if (!ctx) throw new Error('Reader components must be rendered inside <ReaderLayout>')
  return ctx
}
