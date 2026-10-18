import { useState, type ReactNode } from 'react'
import type { PageResults } from './api'
import { PageResultsContext } from './usePageResults'

// Holds the product matches the chat agent put on the page. The chat widget writes them;
// the Products page renders them with the same ProductCard used everywhere else.
export function PageResultsProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<{ results: PageResults | null; version: number }>({
    results: null,
    version: 0,
  })

  const value = {
    ...state,
    show: (results: PageResults) => setState((s) => ({ results, version: s.version + 1 })),
    clear: () => setState((s) => ({ results: null, version: s.version + 1 })),
  }

  return <PageResultsContext.Provider value={value}>{children}</PageResultsContext.Provider>
}
