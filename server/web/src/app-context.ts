import { createContext, useCallback, useContext, useState } from 'react'
import type { AgentInfo, Channel, Thread } from './types'

export interface AppContextValue {
  channels: Channel[]
  threads: Record<number, Thread>
  /** null until /api/agent answers. */
  agent: AgentInfo | null
  openThread: (threadId: number) => void
  /** Re-fetch threads and the open thread's messages (in case the websocket missed something). */
  refresh: () => void
  /** Re-fetch the channel list (after connecting one to YouTube). */
  reloadChannels: () => void
}

export const AppContext = createContext<AppContextValue>({
  channels: [],
  threads: {},
  agent: null,
  openThread: () => {},
  refresh: () => {},
  reloadChannels: () => {},
})

export const useApp = () => useContext(AppContext)

/** Runs a card button's request: tracks busy, shows the server's 409 message, refreshes after. */
export function useAction() {
  const { refresh } = useApp()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const run = useCallback(
    async (fn: () => Promise<unknown>): Promise<boolean> => {
      setBusy(true)
      setError(null)
      try {
        await fn()
        refresh()
        return true
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e))
        return false
      } finally {
        setBusy(false)
      }
    },
    [refresh],
  )

  return { busy, error, run, setError }
}
