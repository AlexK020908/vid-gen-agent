import { useEffect, useState } from 'react'
import { api } from '../api'
import { useAction } from '../app-context'
import { STATES } from '../format'
import { AutoText, ErrorText } from '../parts'
import type { ErrorCard, VideoInfo, VideoState } from '../types'

const MAX_REGENS = 3 // core/actions.py

export function ErrorView({ card, active }: { card: ErrorCard; active: boolean }) {
  const { busy, error, run } = useAction()
  const resume = card.resume_state as VideoState | null
  return (
    <div className="error-card">
      <p className="error-msg">{card.error ?? 'Something went wrong.'}</p>
      <p className="muted">
        {card.state === 'blocked' ? 'Blocked' : 'Failed'}. Retry picks up at “{resume ? STATES[resume][0] : 'the start'}”.
      </p>
      {active && card.state === 'blocked' && <StuckScenes videoId={card.video_id} />}
      {active && (
        <div className="card-actions">
          <div className="row">
            <span className="spacer" />
            <button className="btn primary" disabled={busy}
              onClick={() => run(() => api.act(card.video_id, 'retry'))}>Retry</button>
          </div>
          <ErrorText>{error}</ErrorText>
        </div>
      )}
    </div>
  )
}

/** A scene redone 3 times blocks the video; editing its prompt by hand is the way out. */
function StuckScenes({ videoId }: { videoId: number }) {
  const [info, setInfo] = useState<VideoInfo | null>(null)
  const [fixed, setFixed] = useState<number[]>([])
  useEffect(() => {
    api.video(videoId).then(setInfo).catch(console.error)
  }, [videoId])
  if (!info) return null
  const stuck = info.scene_list.filter((s) => s.regen_count >= MAX_REGENS || fixed.includes(s.idx))
  return (
    <div className="stuck">
      {stuck.map((s) => (
        <SceneEditor key={s.idx} videoId={videoId} scene={s} done={fixed.includes(s.idx)}
          onDone={() => setFixed((f) => [...f, s.idx])} />
      ))}
    </div>
  )
}

function SceneEditor({ videoId, scene, done, onDone }: {
  videoId: number; scene: VideoInfo['scene_list'][number]; done: boolean; onDone: () => void
}) {
  const [prompt, setPrompt] = useState(scene.visual_prompt)
  const [line, setLine] = useState(scene.narration)
  const { busy, error, run } = useAction()
  const body = {
    idx: scene.idx,
    ...(prompt !== scene.visual_prompt ? { visual_prompt: prompt } : {}),
    ...(line !== scene.narration ? { narration: line } : {}),
  }
  const save = async () => {
    if (await run(() => api.act(videoId, 'edit_scene', body))) onDone()
  }
  return (
    <div className="scene-editor">
      {scene.preview_url && <img src={scene.preview_url} alt={`Scene ${scene.idx}`} />}
      <div className="grow">
        <strong>Scene {scene.idx}</strong> <span className="muted">{scene.label}</span>
        <span className="field-label">Picture prompt</span>
        <AutoText value={prompt} onChange={setPrompt} disabled={done} />
        <span className="field-label">Narration</span>
        <AutoText value={line} onChange={setLine} disabled={done} />
        <div className="row">
          <span className="spacer" />
          {done ? <span className="muted">Saved. Retry to redo it.</span> : (
            <button className="btn small" disabled={busy || Object.keys(body).length === 1} onClick={save}>
              Save edit
            </button>
          )}
        </div>
        <ErrorText>{error}</ErrorText>
      </div>
    </div>
  )
}
