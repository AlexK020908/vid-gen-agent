import { api } from '../api'
import { useAction, useApp } from '../app-context'
import { ErrorText } from '../parts'
import type { TopicIdea, TopicsCard } from '../types'

export function TopicsView({ card }: { card: TopicsCard }) {
  return (
    <div className="topics">
      {card.topics.map((t) => <TopicRow key={t.id} topic={t} />)}
    </div>
  )
}

function TopicRow({ topic }: { topic: TopicIdea }) {
  const { threads, openThread } = useApp()
  const { busy, error, run } = useAction()
  const start = () => run(async () => openThread((await api.startTopic(topic.id)).thread_id))
  const thread = Object.values(threads).find((t) => topic.video_id !== null && t.video_id === topic.video_id)
  return (
    <div className={`topic topic-${topic.status}`}>
      <div className="topic-title">
        {topic.title}
        {topic.family && <span className="chip">{topic.family}</span>}
      </div>
      {topic.note && topic.status === 'queued' && <div className="topic-note">{topic.note}</div>}
      {topic.why && <p className="topic-why">{topic.why}</p>}
      {topic.based_on.map((h) => (
        <div className="topic-hit muted" key={h.title}>
          Builds on {h.url ? <a href={h.url} target="_blank" rel="noreferrer">“{h.title}”</a> : `“${h.title}”`}
          {' '}by {h.channel}: {h.per_day.toLocaleString()} views a day
        </div>
      ))}
      <div className="row">
        <span className="spacer" />
        {topic.status === 'queued' && (
          <>
            <button className="btn small" disabled={busy} onClick={() => run(() => api.dismissTopic(topic.id))}>
              Dismiss
            </button>
            <button className="btn small primary" disabled={busy} onClick={start}>Start video</button>
          </>
        )}
        {topic.status === 'used' && (thread
          ? <button className="link" onClick={() => openThread(thread.id)}>Started as #{topic.video_id}</button>
          : <span className="muted">Started</span>)}
        {topic.status === 'dismissed' && <span className="muted">Dismissed</span>}
      </div>
      <ErrorText>{error}</ErrorText>
    </div>
  )
}
