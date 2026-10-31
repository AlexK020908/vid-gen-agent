import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api } from './api'
import { AppContext } from './app-context'
import { useLive } from './live'
import { Sidebar } from './Sidebar'
import { ThreadView } from './ThreadView'
import type { AgentInfo, Channel, LiveEvent, Message, Thread } from './types'

function upsert(list: Message[], msg: Message): Message[] {
  const i = list.findIndex((m) => m.id === msg.id)
  if (i >= 0) return list.map((m) => (m.id === msg.id ? msg : m))
  const next = [...list, msg]
  return list.length && list[list.length - 1].id > msg.id ? next.sort((a, b) => a.id - b.id) : next
}

function applyThreadEvent(threads: Record<number, Thread>, ev: LiveEvent): Record<number, Thread> {
  if (ev.type === 'thread') return { ...threads, [ev.thread.id]: ev.thread }
  if (ev.type === 'turn') {
    const t = threads[ev.thread_id]
    return t ? { ...threads, [t.id]: { ...t, running: ev.running } } : threads
  }
  return threads
}

function threadFromHash(): number | null {
  const m = location.hash.match(/^#t(\d+)$/)
  return m ? Number(m[1]) : null
}

function notify(title: string, body: string, onClick: () => void) {
  if (typeof Notification === 'undefined' || Notification.permission !== 'granted') return
  const n = new Notification(title, { body })
  n.onclick = () => {
    window.focus()
    onClick()
    n.close()
  }
}

export function App() {
  const [channels, setChannels] = useState<Channel[]>([])
  const [threads, setThreads] = useState<Record<number, Thread>>({})
  const [agent, setAgent] = useState<AgentInfo | null>(null)
  const [messages, setMessages] = useState<Record<number, Message[]>>({})
  const [selected, setSelected] = useState<number | null>(threadFromHash)
  const selectedRef = useRef(selected)
  const threadsRef = useRef(threads)
  selectedRef.current = selected
  threadsRef.current = threads

  // A fetch answers with a snapshot taken when the server got the request; websocket events can overtake
  // it. Keep recent events numbered, and replay the ones that arrived after a fetch started on top of
  // its snapshot, so a slow GET never rolls back a newer update (a streamed reply, a turn ending).
  const events = useRef<{ seq: number; ev: LiveEvent }[]>([])
  const seq = useRef(0)
  const since = (start: number) => events.current.filter((e) => e.seq > start).map((e) => e.ev)

  const loadThreads = useCallback(async () => {
    const start = seq.current
    const list = await api.threads()
    setThreads(since(start).reduce(applyThreadEvent, Object.fromEntries(list.map((t) => [t.id, t]))))
  }, [])

  const loadMessages = useCallback(async (threadId: number) => {
    const start = seq.current
    let list = await api.messages(threadId)
    for (const ev of since(start)) {
      if ((ev.type === 'message' || ev.type === 'message_updated') && ev.message.thread_id === threadId) {
        list = upsert(list, ev.message)
      }
    }
    setMessages((prev) => ({ ...prev, [threadId]: list }))
  }, [])

  const refresh = useCallback(() => {
    loadThreads().catch(console.error)
    if (selectedRef.current != null) loadMessages(selectedRef.current).catch(console.error)
  }, [loadThreads, loadMessages])

  const reloadChannels = useCallback(() => {
    api.channels()
      .then((list) => {
        setChannels(list)
        setSelected((cur) => cur ?? list[0]?.home_thread_id ?? null)
      })
      .catch(console.error)
  }, [])

  useEffect(() => {
    reloadChannels()
    api.agent().then(setAgent).catch(console.error)
    loadThreads().catch(console.error)
  }, [loadThreads, reloadChannels])

  useEffect(() => {
    if (selected == null) return
    if (location.hash !== `#t${selected}`) history.replaceState(null, '', `#t${selected}`)
    loadMessages(selected).catch(console.error)
  }, [selected, loadMessages])

  useEffect(() => {
    const onHash = () => {
      const t = threadFromHash()
      if (t != null) setSelected(t)
    }
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  const onEvent = useCallback((ev: LiveEvent) => {
    seq.current += 1
    events.current.push({ seq: seq.current, ev })
    if (events.current.length > 500) events.current.splice(0, events.current.length - 500)
    if (ev.type === 'thread' || ev.type === 'turn') {
      setThreads((prev) => applyThreadEvent(prev, ev))
      return
    }
    const msg = ev.message
    setMessages((prev) => (prev[msg.thread_id] ? { ...prev, [msg.thread_id]: upsert(prev[msg.thread_id], msg) } : prev))
    const gateCard = ev.type === 'message' && msg.role === 'card' && msg.card_status === 'active'
    if (gateCard && (document.hidden || selectedRef.current !== msg.thread_id)) {
      const thread = threadsRef.current[msg.thread_id]
      notify(thread?.title ?? 'Stick Fleet', msg.text ?? 'Something needs you.', () => setSelected(msg.thread_id))
    }
  }, [])

  const connected = useLive(onEvent, refresh)

  const waiting = Object.values(threads).reduce((n, t) => n + t.waiting, 0)
  useEffect(() => {
    document.title = waiting ? `(${waiting}) Stick Fleet` : 'Stick Fleet'
  }, [waiting])

  const value = useMemo(
    () => ({ channels, threads, agent, openThread: setSelected, refresh, reloadChannels }),
    [channels, threads, agent, refresh, reloadChannels],
  )
  const thread = selected != null ? threads[selected] : undefined
  const channel = channels.find((c) => c.id === thread?.channel_id)

  return (
    <AppContext.Provider value={value}>
      <div className="app">
        <Sidebar selected={selected} connected={connected} />
        <main className="main">
          {thread && channel ? (
            <ThreadView key={thread.id} thread={thread} channel={channel} messages={messages[thread.id]} />
          ) : (
            <p className="muted center">Loading…</p>
          )}
        </main>
      </div>
    </AppContext.Provider>
  )
}
