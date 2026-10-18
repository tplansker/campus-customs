import { createContext, useContext } from 'react'
import type { PageResults } from './api'

export type PageResultsState = {
  results: PageResults | null
  version: number // bumps on every show(), so the page can react to repeat searches
  show: (results: PageResults) => void
  clear: () => void
}

export const PageResultsContext = createContext<PageResultsState | null>(null)

export function usePageResults() {
  const ctx = useContext(PageResultsContext)
  if (!ctx) throw new Error('usePageResults must be used inside <PageResultsProvider>')
  return ctx
}
