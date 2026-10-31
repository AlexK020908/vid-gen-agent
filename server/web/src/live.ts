import { useEffect, useRef, useState } from 'react'
import type { LiveEvent } from './types'

/**
 * One websocket to /ws that reconnects on its own. `onOpen` runs on every (re)connect so the
 * caller can re-fetch whatever it might have missed while disconnected.
 */
export function useLive(onEvent: (event: LiveEvent) => void, onOpen: () => void): boolean {
  const eventRef = useRef(onEvent)
  const openRef = useRef(onOpen)
  eventRef.current = onEvent
  openRef.current = onOpen
  const [connected, setConnected] = useState(false)

  useEffect(() => {
    let socket: WebSocket | null = null
    let retry: number | undefined
    let ping: number | undefined
    let stopped = false

    const connect = () => {
      const scheme = location.protocol === 'https:' ? 'wss' : 'ws'
      socket = new WebSocket(`${scheme}://${location.host}/ws`)
      socket.onopen = () => {
        setConnected(true)
        openRef.current()
        ping = window.setInterval(() => socket?.send('ping'), 25_000)
      }
      socket.onmessage = (ev) => eventRef.current(JSON.parse(ev.data) as LiveEvent)
      socket.onclose = () => {
        setConnected(false)
        window.clearInterval(ping)
        if (!stopped) retry = window.setTimeout(connect, 1500)
      }
    }

    connect()
    return () => {
      stopped = true
      window.clearTimeout(retry)
      window.clearInterval(ping)
      socket?.close()
    }
  }, [])

  return connected
}
