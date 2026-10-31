import { useState } from 'react'
import { api } from '../api'
import { useAction } from '../app-context'
import { AutoText, ErrorText, MotionPill } from '../parts'
import type { ScriptCard } from '../types'

export function ScriptView({ card, active }: { card: ScriptCard; active: boolean }) {
  const [note, setNote] = useState(card.draft_note ?? '')
  const [allOpen, setAllOpen] = useState(false)
  const { busy, error, run } = useAction()
  const id = card.video_id

  return (
    <div className="script">
      <h3 className="card-topic">{card.topic}</h3>
      <div className="stats">
        <span>{card.scene_count} scenes</span>
        <span>{card.word_count.toLocaleString()} words</span>
        <span>about {card.est_minutes} min</span>
        <span className="spacer" />
        <button className="link" onClick={() => setAllOpen((o) => !o)}>{allOpen ? 'Collapse all' : 'Expand all'}</button>
      </div>

      {card.places && card.places.length > 0 && (
        <details className="script-places">
          <summary>{card.places.length} place{card.places.length === 1 ? '' : 's'}, each drawn once and reused</summary>
          <ul>
            {card.places.map((p) => <li key={p.name}><b>{p.name}</b>: {p.look}</li>)}
          </ul>
        </details>
      )}

      <div className="script-beats">
        {card.beats.map((b) => (
          // the key flips with allOpen so the uncontrolled <details> picks up the new default
          <details key={`${b.n}-${allOpen}`} open={allOpen} className="script-beat">
            <summary>
              <span className="beat-n">{b.n}</span>
              <span className="beat-label">{b.label}</span>
              <span className="beat-title">{b.title}</span>
              <span className="muted">{b.scenes.length} scene{b.scenes.length === 1 ? '' : 's'}</span>
            </summary>
            {b.scenes.map((s) => (
              <div key={s.idx} className="scene-line">
                <span className="scene-idx">{s.idx}</span>
                <div>
                  {(s.place || s.tracker || (s.cast && s.cast.length > 0)) && (
                    <p className="scene-meta">
                      {s.place && <span className="pill place">{s.place}</span>}
                      {s.cast && s.cast.length > 0 && <span>with {s.cast.join(', ')}</span>}
                      {s.tracker && <span className="tracker">{s.tracker}</span>}
                    </p>
                  )}
                  <p className="narration">{s.narration}</p>
                  <p className="visual"><MotionPill motion={s.motion} /> {s.visual_prompt}</p>
                  {s.set_change && <p className="visual">From here on: {s.set_change}</p>}
                  {s.looks && <p className="visual">From here on, {s.looks}</p>}
                </div>
              </div>
            ))}
          </details>
        ))}
      </div>

      {active && (
        <div className="card-actions">
          <AutoText className="note" value={note} onChange={setNote}
            placeholder="What should change? Sends the script back to be rewritten with your note." />
          <div className="row">
            <button className="btn" disabled={busy || !note.trim()}
              onClick={() => run(() => api.act(id, 'revise', { gate: 'script', note }))}>Revise with note</button>
            <span className="spacer" />
            <button className="btn primary" disabled={busy}
              onClick={() => run(() => api.act(id, 'approve', { gate: 'script' }))}>
              Approve script and generate
            </button>
          </div>
          <ErrorText>{error}</ErrorText>
        </div>
      )}
    </div>
  )
}
