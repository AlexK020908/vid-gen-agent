import { useState } from 'react'
import { api } from '../api'
import { useAction } from '../app-context'
import { ErrorText } from '../parts'
import type { SwapCard } from '../types'

export function SwapView({ card, active }: { card: SwapCard; active: boolean }) {
  const [thumb, setThumb] = useState(card.thumb_idx)
  const [title, setTitle] = useState(Math.max(0, card.titles.indexOf(card.title)))
  const { busy, error, run } = useAction()
  const titleChanged = card.titles[title] !== card.title
  const changed = thumb !== card.thumb_idx || titleChanged
  const apply = () => run(() => api.act(card.video_id, 'swap', {
    ...(thumb !== card.thumb_idx ? { thumb_idx: thumb } : {}),
    ...(titleChanged ? { title_idx: title } : {}),
  }))
  return (
    <div className="swap">
      <div className="thumbs">
        {card.thumbs.map((src, i) => (
          <button key={src} className={`thumb ${i === thumb ? 'picked' : ''}`} disabled={!active}
            onClick={() => setThumb(i)} title={card.texts[i] ?? undefined}>
            <img src={src} alt={`Thumbnail ${i + 1}`} />
            {i === card.thumb_idx && <span className="thumb-now">now</span>}
          </button>
        ))}
      </div>
      <div className="titles">
        {card.titles.map((t, i) => (
          <button key={t} className={`title-opt ${i === title ? 'picked' : ''}`} disabled={!active}
            onClick={() => setTitle(i)}>
            {t}{t === card.title && <span className="muted"> (now)</span>}
          </button>
        ))}
      </div>
      {active && (
        <div className="card-actions">
          <div className="row">
            <span className="muted">
              {card.live ? 'Changes the live video on YouTube.' : 'Stub: writes swap_request.json; nothing is sent.'}
            </span>
            <span className="spacer" />
            <button className="btn" disabled={busy} onClick={() => run(() => api.act(card.video_id, 'keep'))}>
              Keep as is
            </button>
            <button className="btn primary" disabled={busy || !changed} onClick={apply}>
              {card.live ? 'Apply on YouTube' : 'Apply (stub)'}
            </button>
          </div>
          <ErrorText>{error}</ErrorText>
        </div>
      )}
    </div>
  )
}
