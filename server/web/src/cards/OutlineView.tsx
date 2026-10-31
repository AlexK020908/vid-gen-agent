import { useMemo, useState } from 'react'
import { api } from '../api'
import { useAction } from '../app-context'
import { AutoText, ErrorText } from '../parts'
import type { Beat, OutlineCard } from '../types'

type BeatFields = Pick<Beat, 'label' | 'title' | 'summary' | 'hero'>

type Op =
  | { op: 'set_hook' | 'set_backstory' | 'set_ending'; text: string }
  | ({ op: 'edit_beat'; beat: number } & Partial<BeatFields>)
  | { op: 'cut_beat'; beat: number }
  | { op: 'move_beat'; beat: number; to: number }
  | ({ op: 'add_beat'; after: number } & BeatFields)

interface Draft {
  hook: string
  backstory: string
  ending: string
  beats: Beat[]
}

const clamp = (n: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, n))

/** Same rules as _apply_outline_op in core/actions.py, so the preview matches what the server saves. */
function apply(d: Draft, op: Op): Draft {
  const beats = d.beats.slice()
  switch (op.op) {
    case 'set_hook':
      return { ...d, hook: op.text }
    case 'set_backstory':
      return { ...d, backstory: op.text }
    case 'set_ending':
      return { ...d, ending: op.text }
    case 'edit_beat': {
      const b = { ...beats[op.beat - 1] }
      if (op.label !== undefined) b.label = op.label
      if (op.title !== undefined) b.title = op.title
      if (op.summary !== undefined) b.summary = op.summary
      if (op.hero !== undefined) b.hero = op.hero
      beats[op.beat - 1] = b
      break
    }
    case 'cut_beat':
      beats.splice(op.beat - 1, 1)
      break
    case 'move_beat': {
      const [b] = beats.splice(op.beat - 1, 1)
      beats.splice(clamp(op.to, 1, beats.length + 1) - 1, 0, b)
      break
    }
    case 'add_beat':
      beats.splice(clamp(op.after, 0, beats.length), 0, {
        n: 0, skill: '', label: op.label, title: op.title, summary: op.summary, hero: op.hero, cast: [],
      })
      break
  }
  return { ...d, beats: beats.map((b, i) => ({ ...b, n: i + 1 })) }
}

export function OutlineView({ card, active }: { card: OutlineCard; active: boolean }) {
  const [ops, setOps] = useState<Op[]>([])
  const [editing, setEditing] = useState<string | null>(null) // 'hook' | 'ending' | 'beat:N' | 'add'
  const [note, setNote] = useState(card.draft_note ?? '')
  const { busy, error, run } = useAction()
  const draft = useMemo(
    () => ops.reduce(apply, { hook: card.hook, backstory: card.backstory ?? '', ending: card.ending, beats: card.beats }),
    [card, ops],
  )
  const push = (op: Op) => {
    setOps((o) => [...o, op])
    setEditing(null)
  }
  const id = card.video_id
  const save = () => run(() => api.act(id, 'edit_outline', { ops }))
  const approve = () =>
    run(async () => {
      if (ops.length) await api.act(id, 'edit_outline', { ops })
      await api.act(id, 'approve', { gate: 'outline' })
    })
  const revise = () => run(() => api.act(id, 'revise', { gate: 'outline', note }))

  return (
    <div className="outline">
      <h3 className="card-topic">{card.topic}</h3>

      <TextBlock label="Hook" text={draft.hook} editable={active} editing={editing === 'hook'}
        onEdit={() => setEditing('hook')} onCancel={() => setEditing(null)}
        onSave={(text) => push({ op: 'set_hook', text })} />

      {card.backstory !== undefined && (
        <TextBlock label="Backstory" text={draft.backstory} editable={active} editing={editing === 'backstory'}
          onEdit={() => setEditing('backstory')} onCancel={() => setEditing(null)}
          onSave={(text) => push({ op: 'set_backstory', text })} />
      )}

      {card.tracker && card.tracker.length > 0 && (
        <div className="text-block">
          <span className="field-label">Tracker</span>
          <p className="tracker-items">
            {card.tracker.map((t) => (
              <span key={t.item} className="pill">{t.item}: {t.start} {t.unit}</span>
            ))}
          </p>
        </div>
      )}

      {card.cast && card.cast.length > 0 && (
        <div className="text-block">
          <span className="field-label">Cast</span>
          <ul className="cast-list">
            {card.cast.map((c) => (
              <li key={c.name}>
                <b>{c.name}</b>, {c.role}. {c.thread}
                <span className="muted"> Looks: {c.look}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <ol className="beats">
        {draft.beats.map((b) =>
          editing === `beat:${b.n}` ? (
            <li key={`edit-${b.n}`} className="beat editing">
              <BeatForm initial={b} onCancel={() => setEditing(null)}
                onSave={(f) => push({ op: 'edit_beat', beat: b.n, ...f })} />
            </li>
          ) : (
            <li key={b.n} className={`beat ${b.hero ? 'hero' : ''}`}>
              <span className="beat-n">{b.n}</span>
              <div className="beat-main">
                <div className="beat-top">
                  <span className="beat-label">{b.label}</span>
                  <span className="beat-title">{b.title}</span>
                  {b.hero && <span className="pill hero" title="Hero beats get a video clip">hero</span>}
                </div>
                {b.summary && <p className="beat-summary">{b.summary}</p>}
                {b.skill && <p className="beat-skill">Skill: {b.skill}</p>}
                {b.cast && b.cast.length > 0 && <p className="beat-skill">With: {b.cast.join(', ')}</p>}
              </div>
              {active && (
                <div className="beat-tools">
                  <button className="icon" title="Move up" disabled={b.n === 1}
                    onClick={() => push({ op: 'move_beat', beat: b.n, to: b.n - 1 })}>↑</button>
                  <button className="icon" title="Move down" disabled={b.n === draft.beats.length}
                    onClick={() => push({ op: 'move_beat', beat: b.n, to: b.n + 1 })}>↓</button>
                  <button className={`icon ${b.hero ? 'on' : ''}`}
                    title={b.hero ? 'Make it a normal beat' : 'Make it a hero beat (gets a video clip)'}
                    onClick={() => push({ op: 'edit_beat', beat: b.n, hero: !b.hero })}>★</button>
                  <button className="icon" title="Edit" onClick={() => setEditing(`beat:${b.n}`)}>✎</button>
                  <button className="icon" title={draft.beats.length <= 3 ? 'An outline needs at least 3 beats' : 'Cut'}
                    disabled={draft.beats.length <= 3}
                    onClick={() => push({ op: 'cut_beat', beat: b.n })}>✕</button>
                </div>
              )}
            </li>
          ),
        )}
        {active && editing === 'add' && (
          <li className="beat editing">
            <BeatForm initial={{ label: '', title: '', summary: '', hero: false }} onCancel={() => setEditing(null)}
              onSave={(f) => push({ op: 'add_beat', after: draft.beats.length, ...f })} />
          </li>
        )}
      </ol>
      {active && editing !== 'add' && (
        <button className="link add-beat" onClick={() => setEditing('add')}>+ Add a beat</button>
      )}

      <TextBlock label="Ending" text={draft.ending} editable={active} editing={editing === 'ending'}
        onEdit={() => setEditing('ending')} onCancel={() => setEditing(null)}
        onSave={(text) => push({ op: 'set_ending', text })} />

      {active && ops.length > 0 && (
        <div className="pending-bar">
          <span>{ops.length} unsaved edit{ops.length === 1 ? '' : 's'}</span>
          <button className="link" onClick={() => setOps((o) => o.slice(0, -1))}>Undo</button>
          <button className="link" onClick={() => setOps([])}>Discard</button>
          <button className="btn small" disabled={busy} onClick={save}>Save edits</button>
        </div>
      )}

      {active && (
        <div className="card-actions">
          <AutoText className="note" value={note} onChange={setNote}
            placeholder="What should change? Sends the outline back to be rewritten with your note." />
          <div className="row">
            <button className="btn" disabled={busy || !note.trim() || ops.length > 0} onClick={revise}
              title={ops.length ? 'Save or discard your edits first' : undefined}>Revise with note</button>
            <span className="spacer" />
            <button className="btn primary" disabled={busy} onClick={approve}>
              {ops.length ? 'Save edits and approve' : 'Approve outline'}
            </button>
          </div>
          <ErrorText>{error}</ErrorText>
        </div>
      )}
    </div>
  )
}

function TextBlock({ label, text, editable, editing, onEdit, onSave, onCancel }: {
  label: string; text: string; editable: boolean; editing: boolean
  onEdit: () => void; onSave: (text: string) => void; onCancel: () => void
}) {
  const [value, setValue] = useState(text)
  if (editing) {
    return (
      <div className="text-block editing">
        <span className="field-label">{label}</span>
        <AutoText value={value} onChange={setValue} autoFocus />
        <div className="row">
          <button className="btn small" disabled={!value.trim()} onClick={() => onSave(value.trim())}>Done</button>
          <button className="link" onClick={onCancel}>Cancel</button>
        </div>
      </div>
    )
  }
  return (
    <div className="text-block">
      <span className="field-label">{label}</span>
      <p>{text}</p>
      {editable && <button className="icon" title={`Edit the ${label.toLowerCase()}`}
        onClick={() => { setValue(text); onEdit() }}>✎</button>}
    </div>
  )
}

function BeatForm({ initial, onSave, onCancel }: {
  initial: BeatFields; onSave: (f: BeatFields) => void; onCancel: () => void
}) {
  const [f, setF] = useState<BeatFields>({
    label: initial.label, title: initial.title, summary: initial.summary, hero: initial.hero,
  })
  const set = <K extends keyof BeatFields>(k: K, v: BeatFields[K]) => setF((cur) => ({ ...cur, [k]: v }))
  return (
    <form className="beat-form" onSubmit={(e) => { e.preventDefault(); onSave(f) }}>
      <div className="row">
        <input className="label-input" value={f.label} onChange={(e) => set('label', e.target.value)}
          placeholder="Day 30" />
        <input className="grow" value={f.title} onChange={(e) => set('title', e.target.value)}
          placeholder="What happens" autoFocus />
      </div>
      <AutoText value={f.summary} onChange={(v) => set('summary', v)} placeholder="Summary" />
      <div className="row">
        <label className="check">
          <input type="checkbox" checked={f.hero} onChange={(e) => set('hero', e.target.checked)} /> Hero beat (gets a clip)
        </label>
        <span className="spacer" />
        <button type="button" className="link" onClick={onCancel}>Cancel</button>
        <button type="submit" className="btn small" disabled={!f.title.trim()}>Done</button>
      </div>
    </form>
  )
}
