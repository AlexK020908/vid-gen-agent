import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import { useAction, useApp } from '../app-context'
import { clock, fromLocalInput, toLocalInput, when } from '../format'
import { AutoText, Counter, ErrorText } from '../parts'
import type { PublishCard } from '../types'

interface Form {
  title: string
  description: string
  tags: string
  publish_at: string
  ai_disclosure: boolean
}
type Field = keyof Form

const fromCard = (card: PublishCard): Form => ({
  title: card.title,
  description: card.description,
  tags: card.tags.join(', '),
  publish_at: toLocalInput(card.publish_at),
  ai_disclosure: card.ai_disclosure,
})

export function PublishView({ card, active }: { card: PublishCard; active: boolean }) {
  const [form, setForm] = useState<Form>(() => fromCard(card))
  const [dirty, setDirty] = useState<Set<Field>>(new Set())
  const dirtyRef = useRef(dirty)
  dirtyRef.current = dirty
  const { busy, error, run } = useAction()
  const { channels, threads } = useApp()
  const stub = card.youtube_mode === 'stub'
  // Read the live sidebar state, so connecting the channel clears the warning without a new card.
  const channelId = Object.values(threads).find((t) => t.video_id === card.video_id)?.channel_id
  const connected = channels.find((c) => c.id === channelId)?.youtube.connected ?? card.youtube_connected

  // The card was refreshed (after Save, or a new pick on the render card): take the server's
  // values for every field you haven't touched.
  useEffect(() => {
    const next = fromCard(card)
    setForm((cur) => {
      const kept = Object.fromEntries([...dirtyRef.current].map((k) => [k, cur[k]]))
      return { ...next, ...kept }
    })
  }, [card])

  const set = <K extends Field>(k: K, v: Form[K]) => {
    setForm((cur) => ({ ...cur, [k]: v }))
    setDirty((cur) => new Set(cur).add(k))
  }

  const changes = () => {
    const out: Record<string, unknown> = {}
    for (const k of dirty) {
      if (k === 'tags') out.tags = form.tags.split(',').map((t) => t.trim()).filter(Boolean)
      else if (k === 'publish_at') out.publish_at = fromLocalInput(form.publish_at)
      else out[k] = form[k]
    }
    return out
  }

  const save = async () => {
    if (await run(() => api.act(card.video_id, 'publish_fields', changes()))) setDirty(new Set())
  }
  const publish = () => {
    const at = when(fromLocalInput(form.publish_at))
    if (!stub && !window.confirm(`Upload "${form.title}" to YouTube as private, scheduled to go public ${at}?`)) return
    run(() => api.act(card.video_id, 'publish', changes()))
  }

  const badChars = /[<>]/.test(form.title + form.description)
  const locked = !active || busy

  return (
    <div className="publish">
      {stub && <p className="notice">Stub mode: Publish writes publish_request.json instead of uploading.</p>}
      {!stub && connected === false && active && (
        <p className="notice">This channel isn't connected to YouTube yet: click Connect YouTube under it in the sidebar.</p>
      )}
      <div className="publish-grid">
        <div className="publish-side">
          {card.thumbnail && <img className="publish-thumb" src={card.thumbnail} alt="Chosen thumbnail" />}
          <label className="field">
            <span className="field-label">Goes public</span>
            <input type="datetime-local" value={form.publish_at} disabled={locked}
              onChange={(e) => set('publish_at', e.target.value)} />
            <span className="muted">Uploaded as private; YouTube makes it public at this time.</span>
          </label>
          <label className="check">
            <input type="checkbox" checked={form.ai_disclosure} disabled={locked}
              onChange={(e) => set('ai_disclosure', e.target.checked)} />
            Label as altered or synthetic content
          </label>
          <div className="chapters">
            <span className="field-label">Chapters</span>
            {card.chapters.map((c) => (
              <div key={c.t_ms} className="chapter"><span className="mono">{clock(c.t_ms)}</span> {c.title}</div>
            ))}
          </div>
        </div>
        <div className="publish-main">
          <label className="field">
            <span className="field-label">Title <Counter n={form.title.length} max={100} /></span>
            <input value={form.title} disabled={locked} onChange={(e) => set('title', e.target.value)} />
          </label>
          <label className="field">
            <span className="field-label">Description <Counter n={form.description.length} max={5000} /></span>
            <AutoText value={form.description} max={420} disabled={locked}
              onChange={(v) => set('description', v)} />
          </label>
          <label className="field">
            <span className="field-label">Tags</span>
            <input value={form.tags} disabled={locked} placeholder="comma, separated"
              onChange={(e) => set('tags', e.target.value)} />
          </label>
          {badChars && <ErrorText>YouTube rejects &lt; and &gt; in the title and description.</ErrorText>}
        </div>
      </div>

      {active && (
        <div className="card-actions">
          <div className="row">
            <button className="btn" disabled={busy || dirty.size === 0} onClick={save}>Save changes</button>
            <span className="spacer" />
            <button className="btn primary" disabled={busy} onClick={publish}>
              {stub ? 'Publish (stub)' : 'Publish to YouTube'}
            </button>
          </div>
          <ErrorText>{error}</ErrorText>
        </div>
      )}
    </div>
  )
}
