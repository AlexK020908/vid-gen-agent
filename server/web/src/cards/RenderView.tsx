import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import { useAction } from '../app-context'
import { clock, money } from '../format'
import { AutoText, ErrorText } from '../parts'
import type { RenderCard } from '../types'

export function RenderView({ card, active }: { card: RenderCard; active: boolean }) {
  const { busy, error, run } = useAction()
  const [tab, setTab] = useState<'highlight' | 'full'>(card.highlight_url ? 'highlight' : 'full')
  const [selected, setSelected] = useState<number[]>([])
  const [customTitle, setCustomTitle] = useState('')
  const highlightRef = useRef<HTMLVideoElement>(null)
  const fullRef = useRef<HTMLVideoElement>(null)
  const id = card.video_id
  const { title, thumb_idx } = card.picked
  const ready = title != null && thumb_idx != null
  const pick = (body: object) => run(() => api.act(id, 'pick', body))

  const show = (which: 'highlight' | 'full') => {
    setTab(which)
    ;(which === 'full' ? highlightRef : fullRef).current?.pause()
  }
  const jump = (ms: number) => {
    show('full')
    const v = fullRef.current
    if (v) {
      v.currentTime = ms / 1000
      v.play().catch(() => {})
    }
  }
  const toggle = (idx: number) =>
    setSelected((cur) => (cur.includes(idx) ? cur.filter((i) => i !== idx) : [...cur, idx].sort((a, b) => a - b)))

  return (
    <div className="render">
      <div className="render-head">
        <h3 className="card-topic">{card.topic}</h3>
        <span className="muted">{clock(card.duration_ms)} · {card.scenes.length} scenes</span>
        <span className="spacer" />
        <Budget spent={card.cost_usd} budget={card.budget_usd} />
      </div>

      <div className="player">
        <div className="tabs">
          <button className={tab === 'highlight' ? 'on' : ''} disabled={!card.highlight_url}
            onClick={() => show('highlight')}>Highlight reel</button>
          <button className={tab === 'full' ? 'on' : ''} onClick={() => show('full')}>Full video</button>
        </div>
        {card.highlight_url && <video ref={highlightRef} src={card.highlight_url} controls preload="metadata"
          hidden={tab !== 'highlight'} />}
        {card.video_url && <video ref={fullRef} src={card.video_url} controls preload="metadata"
          hidden={tab !== 'full'} />}
      </div>

      <h4>Thumbnail</h4>
      <div className="thumbs">
        {card.thumbs.map((src, i) => (
          <button key={src} className={`thumb ${thumb_idx === i ? 'picked' : ''}`} disabled={!active || busy}
            onClick={() => pick({ thumb_idx: i })} aria-pressed={thumb_idx === i}>
            <img src={src} alt={`Thumbnail option ${i + 1}`} />
            {thumb_idx === i && <span className="check">✓</span>}
          </button>
        ))}
      </div>

      <h4>Title</h4>
      <div className="titles">
        {card.titles.map((t, i) => (
          <button key={t} className={`title-opt ${title === t ? 'picked' : ''}`} disabled={!active || busy}
            onClick={() => pick({ title_idx: i })} aria-pressed={title === t}>
            <span className="radio" />
            <span className="grow">{t}</span>
            <span className="counter">{t.length}</span>
          </button>
        ))}
        {title != null && !card.titles.includes(title) && (
          <div className="title-opt picked">
            <span className="radio" />
            <span className="grow">{title}</span>
            <span className="counter">{title.length}</span>
          </div>
        )}
        {active && (
          <form className="row" onSubmit={(e) => {
            e.preventDefault()
            if (customTitle.trim()) pick({ title: customTitle }).then((ok) => ok && setCustomTitle(''))
          }}>
            <input className="grow" value={customTitle} maxLength={100} placeholder="Or write your own title"
              onChange={(e) => setCustomTitle(e.target.value)} />
            <button className="btn" disabled={busy || !customTitle.trim()}>Use this title</button>
          </form>
        )}
      </div>

      <h4>
        Scenes{' '}
        <span className="muted">
          {active ? 'click scenes to send them back · ▶ plays the full video from there' : '▶ plays the full video from there'}
        </span>
      </h4>
      <div className="sheet">
        {card.scenes.map((s) => {
          const on = selected.includes(s.idx)
          return (
            <div key={s.idx} className={`tile ${on ? 'on' : ''}`}>
              <button className="tile-img" disabled={!active} onClick={() => toggle(s.idx)}
                title={`Scene ${s.idx} · ${s.label}\n${s.narration}`} aria-pressed={on}>
                {s.preview_url ? <img src={s.preview_url} alt={`Scene ${s.idx}`} loading="lazy" /> : <span />}
              </button>
              <div className="tile-meta">
                <span className="tile-n">{s.idx}</span>
                {s.motion === 'clip' && <span className="pill clip">clip</span>}
                {s.regen_count > 0 && <span className="pill warn">redone {s.regen_count}×</span>}
                <span className="spacer" />
                {s.start_ms != null && card.video_url && (
                  <button className="icon" title={`Play from ${clock(s.start_ms)}`}
                    onClick={() => jump(s.start_ms!)}>▶</button>
                )}
              </div>
            </div>
          )
        })}
      </div>

      {active && selected.length > 0 && (
        <FlagPanel card={card} idxs={selected} onClear={() => setSelected([])} />
      )}

      {active && (
        <div className="card-actions">
          <div className="row">
            <span className="hint">
              {selected.length > 0
                ? 'Send the selected scenes back, or clear the selection to approve.'
                : !ready ? 'Pick a thumbnail and a title to approve.' : 'Approving moves on to the publish details.'}
            </span>
            <span className="spacer" />
            <button className="btn primary" disabled={busy || !ready || selected.length > 0}
              onClick={() => run(() => api.act(id, 'approve', { gate: 'render' }))}>Approve render</button>
          </div>
          <ErrorText>{error}</ErrorText>
        </div>
      )}
    </div>
  )
}

function Budget({ spent, budget }: { spent: number; budget: number }) {
  const pct = Math.min(100, (100 * spent) / (budget || 1))
  return (
    <span className="budget" title="Spend on this video against the channel's per-video budget">
      <span className="bar"><span style={{ width: `${pct}%` }} className={pct > 85 ? 'hot' : ''} /></span>
      {money(spent)} of {money(budget)}
    </span>
  )
}

type Mode = 'visual' | 'narration' | 'manual'

const MODES: Record<Mode, [label: string, help: string]> = {
  visual: ['New picture', 'Keeps the narration and makes a new picture (and clip). The note tweaks the prompt.'],
  narration: ['Change the line', 'Rewrites the narration with your note and re-voices it. Keeps the picture.'],
  manual: ['Edit by hand', 'Write the prompt or the line yourself; the scene is redone exactly as written.'],
}

function FlagPanel({ card, idxs, onClear }: { card: RenderCard; idxs: number[]; onClear: () => void }) {
  const one = idxs.length === 1 ? card.scenes.find((s) => s.idx === idxs[0]) : undefined
  const [mode, setMode] = useState<Mode>('visual')
  const [note, setNote] = useState('')
  const [prompt, setPrompt] = useState(one?.visual_prompt ?? '')
  const [line, setLine] = useState(one?.narration ?? '')
  const { busy, error, run } = useAction()

  useEffect(() => {
    setPrompt(one?.visual_prompt ?? '')
    setLine(one?.narration ?? '')
    if (!one) setMode((m) => (m === 'manual' ? 'visual' : m))
  }, [one?.idx]) // not `one`: a card refresh makes a new object and would wipe what you typed

  const changed = one
    ? { ...(prompt !== one.visual_prompt ? { visual_prompt: prompt } : {}),
        ...(line !== one.narration ? { narration: line } : {}) }
    : {}
  const canSend = mode === 'manual' ? Object.keys(changed).length > 0 : mode === 'visual' || note.trim().length > 0

  const send = async () => {
    const ok = await run(() =>
      mode === 'manual'
        ? api.act(card.video_id, 'edit_scene', { idx: one!.idx, ...changed })
        : api.act(card.video_id, 'flag', { idxs, kind: mode, note }),
    )
    if (ok) onClear()
  }

  return (
    <div className="flag-panel">
      <div className="row">
        <strong>{idxs.length === 1 ? `Scene ${idxs[0]}` : `${idxs.length} scenes: ${idxs.join(', ')}`}</strong>
        <span className="spacer" />
        <button className="link" onClick={onClear}>Clear selection</button>
      </div>
      <div className="segmented">
        {(Object.keys(MODES) as Mode[]).map((m) => (
          <button key={m} className={mode === m ? 'on' : ''} disabled={m === 'manual' && !one}
            title={m === 'manual' && !one ? 'Select a single scene to edit it by hand' : undefined}
            onClick={() => setMode(m)}>{MODES[m][0]}</button>
        ))}
      </div>
      <p className="muted">{MODES[mode][1]}</p>
      {mode === 'manual' && one ? (
        <>
          <span className="field-label">Picture prompt</span>
          <AutoText value={prompt} onChange={setPrompt} />
          <span className="field-label">Narration</span>
          <AutoText value={line} onChange={setLine} />
        </>
      ) : (
        <AutoText className="note" value={note} onChange={setNote}
          placeholder={mode === 'visual' ? 'Optional: what should the picture show instead?' : 'How should the line change?'} />
      )}
      <div className="row">
        <span className="spacer" />
        <button className="btn danger" disabled={busy || !canSend} onClick={send}>
          {mode === 'manual' ? `Redo scene ${one?.idx}` : `Send back ${idxs.length} scene${idxs.length === 1 ? '' : 's'}`}
        </button>
      </div>
      <ErrorText>{error}</ErrorText>
    </div>
  )
}
