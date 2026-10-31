import { useLayoutEffect, useRef, useState } from 'react'
import { api } from './api'
import { useAction, useApp } from './app-context'
import { CardView } from './cards/CardView'
import { money } from './format'
import { linkify, Markdown } from './markdown'
import { AutoText, ErrorText, StateBadge } from './parts'
import type { Channel, Message, Thread } from './types'

const EXAMPLES = [
  'Day 1 to Day 365 stranded on an oil rig',
  '100 days hiding in an abandoned shopping mall',
  'Surviving the first winter in a lighthouse',
]

export function ThreadView({ thread, channel, messages }: {
  thread: Thread; channel: Channel; messages: Message[] | undefined
}) {
  const { agent } = useApp()
  const [draft, setDraft] = useState('')
  const listRef = useRef<HTMLDivElement>(null)
  const pinned = useRef(true) // follow new messages unless you've scrolled up
  const count = useRef(0)
  const home = thread.video_id == null

  // Move only when a message arrives (or a progress line ticks), never on card updates, so picking a
  // title doesn't yank the view. A new card taller than the view opens at its top, not its bottom.
  useLayoutEffect(() => {
    const el = listRef.current
    if (!el || !messages) return
    const grew = messages.length > count.current
    count.current = messages.length
    if (!pinned.current) return
    const last = messages[messages.length - 1]
    if (grew && last?.role === 'card') {
      const active = el.querySelectorAll<HTMLElement>('.card.active')
      const card = active[active.length - 1]
      if (card && card.offsetHeight > el.clientHeight) {
        el.scrollTop = card.offsetTop - 16
        return
      }
    }
    // Also follow a progress line ticking and the assistant's reply streaming in.
    if (grew || last?.role === 'progress' || last?.role === 'assistant') el.scrollTop = el.scrollHeight
  }, [messages])

  useLayoutEffect(() => {
    const el = listRef.current
    if (el && thread.running && pinned.current) el.scrollTop = el.scrollHeight
  }, [thread.running])

  const onScroll = () => {
    const el = listRef.current
    if (el) pinned.current = el.scrollHeight - el.scrollTop - el.clientHeight < 120
  }

  return (
    <div className="thread-view">
      <header className="thread-head">
        <div className="grow">
          <h1>{home ? channel.name : thread.title}</h1>
          <div className="muted">
            {home
              ? agent?.online ? 'Tell the assistant a video idea, or ask how a video is doing.' : 'Type a video idea below to start one.'
              : `Video #${thread.video_id} · ${channel.name}`}
          </div>
        </div>
        {!home && thread.state && (
          <div className="head-right">
            {(thread.state === 'new' || thread.state === 'outline_approved') && thread.video_id !== null && (
              <StopWriting videoId={thread.video_id} />
            )}
            <StateBadge state={thread.state} />
            <span className="muted">{money(thread.cost_usd)} of {money(channel.budget_usd)}</span>
          </div>
        )}
      </header>

      <div className="messages" ref={listRef} onScroll={onScroll}>
        <div className="messages-inner">
          {messages === undefined && <p className="muted center">Loading…</p>}
          {messages?.length === 0 && home && (
            <div className="welcome">
              <p>Describe a video and the pipeline takes it from outline to upload, stopping whenever it needs you.</p>
              <div className="examples">
                {EXAMPLES.map((e) => <button key={e} className="chip" onClick={() => setDraft(e)}>{e}</button>)}
              </div>
            </div>
          )}
          {messages?.map((m) => <MessageView key={m.id} message={m} home={home} />)}
          {thread.running && <div className="typing" aria-label="The assistant is working"><span /><span /><span /></div>}
        </div>
      </div>

      <Composer thread={thread} channel={channel} draft={draft} setDraft={setDraft} />
    </div>
  )
}

function MessageView({ message, home }: { message: Message; home: boolean }) {
  const { threads, openThread } = useApp()
  switch (message.role) {
    case 'user':
      return <div className="msg user"><div className="bubble">{message.text}</div></div>
    case 'assistant':
      return <div className="msg assistant"><div className="bubble"><Markdown text={message.text ?? ''} /></div></div>
    case 'tool': {
      const card = message.card?.kind === 'tool' ? message.card : null
      return (
        <div className={`msg tool ${card?.error ? 'failed' : ''}`}>
          <span className="tool-name">{card?.name ?? message.text}</span>
          {card?.detail && <span className="tool-detail">{card.detail}</span>}
          {card?.error && <span className="tool-error">{card.error}</span>}
        </div>
      )
    }
    case 'card':
    case 'progress':
      return message.card ? <CardView message={message} /> : null
    default: {
      const target = home && message.video_id != null
        ? Object.values(threads).find((t) => t.video_id === message.video_id)
        : undefined
      return (
        <div className="msg system">
          <span>{linkify(message.text ?? '')}</span>
          {target && <button className="link" onClick={() => openThread(target.id)}>Open</button>}
        </div>
      )
    }
  }
}

function Composer({ thread, channel, draft, setDraft }: {
  thread: Thread; channel: Channel; draft: string; setDraft: (v: string) => void
}) {
  const { openThread, agent } = useApp()
  const { busy, error, run } = useAction()
  const home = thread.video_id == null
  const online = agent?.online ?? false
  const direct = home && !online // without the agent, the home composer starts the video itself

  const send = async () => {
    const text = draft.trim()
    if (!text || busy) return
    const ok = await run(async () => {
      if (direct) openThread((await api.newVideo(channel.id, text)).thread_id)
      else await api.chat(thread.id, text) // mid-turn messages queue up for the next turn
    })
    if (ok) setDraft('')
  }

  const placeholder = direct
    ? `New video idea for ${channel.name}…`
    : home
      ? `A video idea for ${channel.name}, or a question…`
      : online ? 'Message the assistant…' : 'Message (the assistant is offline; use the card buttons)'

  return (
    <form className="composer" onSubmit={(e) => { e.preventDefault(); send() }}>
      <ErrorText>{error}</ErrorText>
      <div className="composer-box">
        <AutoText value={draft} onChange={setDraft} max={200} autoFocus
          placeholder={placeholder}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault()
              send()
            }
          }} />
        {thread.running && (
          <button type="button" className="btn" onClick={() => run(() => api.stop(thread.id))}>Stop</button>
        )}
        <button type="submit" className="btn primary" disabled={busy || !draft.trim()}>
          {direct ? 'Start video' : 'Send'}
        </button>
      </div>
    </form>
  )
}

/** While Claude writes an outline or script: stop it and go back to the card (a revision's note comes back to edit). */
function StopWriting({ videoId }: { videoId: number }) {
  const { busy, error, run } = useAction()
  return (
    <span className="stop-writing">
      <button className="btn small" disabled={busy} title="Stop Claude and go back to the card. If it was rewriting with your note, the note comes back to change."
        onClick={() => run(() => api.act(videoId, 'stop_writing'))}>{busy ? 'Stopping…' : 'Stop'}</button>
      <ErrorText>{error}</ErrorText>
    </span>
  )
}
