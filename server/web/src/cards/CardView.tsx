import { useEffect, useState } from 'react'
import { STAGES } from '../format'
import type { CardStatus, Message, ProgressCard } from '../types'
import { ConfirmView } from './ConfirmView'
import { ErrorView } from './ErrorView'
import { MetricsView } from './MetricsView'
import { OutlineView } from './OutlineView'
import { PublishView } from './PublishView'
import { RenderView } from './RenderView'
import { ScriptView } from './ScriptView'
import { SwapView } from './SwapView'
import { TopicsView } from './TopicsView'

const TITLES = {
  outline: 'Outline', script: 'Script', render: 'Render review', publish: 'Publish', error: 'Needs you',
  confirm: 'Approve a change', topics: 'Topic ideas', metrics: 'How it’s doing',
  swap: 'Try another thumbnail or title',
}

const OUTCOMES: Record<CardStatus, string> = {
  active: 'Waiting for you',
  approved: 'Approved',
  revised: 'Sent back with a note',
  regenerated: 'Written again',
  flagged: 'Scenes sent back',
  superseded: 'Replaced by a newer version',
  retried: 'Retried',
  done: 'Done',
  denied: 'Denied',
  kept: 'Kept as is',
}

/** A review card. Active cards are open with live buttons; resolved ones fold to one line. */
export function CardView({ message }: { message: Message }) {
  const card = message.card!
  const status = message.card_status ?? 'done'
  const active = status === 'active'
  const info = card.kind === 'metrics' // nothing to decide, so it stays open
  const [open, setOpen] = useState(active || info)
  useEffect(() => setOpen(active || info), [active, info])

  if (card.kind === 'progress') return <ProgressLine card={card} status={status} />
  if (card.kind === 'tool') return null

  const version = 'version' in card && card.version > 1 ? ` v${card.version}` : ''
  const title = card.kind === 'metrics'
    ? `${TITLES.metrics} after ${card.after_h < 72 ? `${card.after_h} hours` : `${card.after_h / 24} days`}`
    : card.kind === 'topics' && card.winner_video_id !== null ? `Follow-ups to winner #${card.winner_video_id}`
      : TITLES[card.kind]
  return (
    <section className={`card kind-${card.kind} ${active ? 'active' : 'resolved'}`}>
      <header className="card-head" onClick={active ? undefined : () => setOpen((o) => !o)}>
        <span className="card-title">{title}{version}</span>
        {!info && <span className={`outcome status-${status}`}>{OUTCOMES[status]}</span>}
        <span className="spacer" />
        {!active && <span className="chev">{open ? 'Hide' : 'Show'}</span>}
      </header>
      {open && (
        <div className="card-body">
          {message.text && active && <p className="card-intro">{message.text}</p>}
          {card.kind === 'outline' && <OutlineView card={card} active={active} />}
          {card.kind === 'script' && <ScriptView card={card} active={active} />}
          {card.kind === 'render' && <RenderView card={card} active={active} />}
          {card.kind === 'publish' && <PublishView card={card} active={active} />}
          {card.kind === 'error' && <ErrorView card={card} active={active} />}
          {card.kind === 'confirm' && <ConfirmView card={card} messageId={message.id} active={active} />}
          {card.kind === 'topics' && <TopicsView card={card} />}
          {card.kind === 'metrics' && <MetricsView card={card} />}
          {card.kind === 'swap' && <SwapView card={card} active={active} />}
        </div>
      )}
    </section>
  )
}

function count(card: ProgressCard): string {
  if (card.unit === '%') return `${card.done}%`
  return card.unit ? `${card.done} ${card.unit}` : `${card.done}/${card.total}`
}

export function ProgressLine({ card, status }: { card: ProgressCard; status: CardStatus }) {
  const finished = status !== 'active' || (card.total > 0 && card.done >= card.total)
  const pct = finished ? 100 : card.total ? Math.round((100 * card.done) / card.total) : 0
  return (
    <div className={`progress ${finished ? 'finished' : ''}`}>
      <span className="progress-name">{STAGES[card.stage] ?? card.stage}</span>
      <span className="bar"><span style={{ width: `${pct}%` }} /></span>
      <span className="progress-count">{count(card)}</span>
      <span className="tick">{finished ? '✓' : ''}</span>
    </div>
  )
}
