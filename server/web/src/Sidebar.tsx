import { useState } from 'react'
import { api } from './api'
import { useAction, useApp } from './app-context'
import { money } from './format'
import { ErrorText, StateBadge } from './parts'
import type { Channel } from './types'

const notifications = typeof Notification === 'undefined' ? null : Notification

/** The channel's YouTube sign-in: who it's connected to, or a Connect button (Google's screen opens on this machine). */
function YouTubeRow({ channel }: { channel: Channel }) {
  const { reloadChannels } = useApp()
  const { busy, error, run } = useAction()
  const yt = channel.youtube
  const connect = () => run(async () => {
    await api.connect(channel.id)
    reloadChannels()
  })
  if (yt.connected) {
    return (
      <div className="yt-row" title={yt.channel_id ?? undefined}>
        <span className="yt-mark" aria-hidden>▶</span> {yt.title ?? 'YouTube connected'}
        {yt.signin_error && <span className="muted" title={yt.signin_error}>sign-in refused</span>}
        {(yt.missing_scopes.length > 0 || yt.signin_error) && (
          <button className="link" disabled={busy} onClick={connect}
            title={`Needs access it didn't ask for before: ${yt.missing_scopes.join(', ')}`}>
            {busy ? 'Waiting for Google sign-in…' : 'Reconnect'}
          </button>
        )}
        <ErrorText>{error}</ErrorText>
      </div>
    )
  }
  return (
    <div className="yt-row">
      <button className="link" disabled={busy} onClick={connect}>
        {busy ? 'Waiting for Google sign-in…' : 'Connect YouTube'}
      </button>
      {!yt.client_secret && !busy && <span className="muted">needs secrets/client_secret.json</span>}
      {yt.error && <span className="muted" title={yt.error}>keychain unavailable</span>}
      <ErrorText>{error}</ErrorText>
    </div>
  )
}

export function Sidebar({ selected, connected }: { selected: number | null; connected: boolean }) {
  const { channels, threads, openThread } = useApp()
  const [permission, setPermission] = useState(notifications?.permission ?? 'denied')
  const all = Object.values(threads)

  return (
    <nav className="sidebar">
      <div className="brand">
        <span className="logo" aria-hidden>
          <svg viewBox="0 0 32 32" width="22" height="22">
            <rect width="32" height="32" rx="7" fill="var(--accent)" />
            <g stroke="#fff" strokeWidth="2.6" strokeLinecap="round" fill="none">
              <circle cx="16" cy="8.5" r="3.6" />
              <path d="M16 12.5v9M16 21.5l-5 6M16 21.5l5 6M9.5 15.5h13" />
            </g>
          </svg>
        </span>
        Stick Fleet
      </div>

      <div className="channels">
        {channels.map((c) => {
          const videos = all.filter((t) => t.channel_id === c.id && t.video_id != null).sort((a, b) => b.id - a.id)
          return (
            <section key={c.id} className="channel">
              <button className={`thread-row home ${selected === c.home_thread_id ? 'selected' : ''}`}
                onClick={() => openThread(c.home_thread_id)}>
                <span className="channel-name">{c.name}</span>
                <span className="new-video">+ New video</span>
              </button>
              <YouTubeRow channel={c} />
              {videos.map((t) => (
                <button key={t.id} className={`thread-row ${selected === t.id ? 'selected' : ''}`}
                  onClick={() => openThread(t.id)}>
                  <span className="thread-title">
                    {t.waiting > 0 && <span className="dot" title="Waiting for you" />}
                    {t.title}
                  </span>
                  <span className="thread-meta">
                    {t.state && <StateBadge state={t.state} />}
                    <span className="muted">{money(t.cost_usd)}</span>
                  </span>
                </button>
              ))}
            </section>
          )
        })}
      </div>

      <footer className="sidebar-foot">
        <span className={`conn ${connected ? 'on' : 'off'}`}>{connected ? 'Connected' : 'Reconnecting…'}</span>
        {notifications && permission === 'default' && (
          <button className="link" onClick={async () => setPermission(await notifications.requestPermission())}>
            Turn on notifications
          </button>
        )}
      </footer>
    </nav>
  )
}
