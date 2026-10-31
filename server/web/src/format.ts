import type { VideoState } from './types'

export type Tone = 'needs' | 'working' | 'done' | 'error'

export const STATES: Record<VideoState, [label: string, tone: Tone]> = {
  new: ['Writing outline', 'working'],
  outlined: ['Review outline', 'needs'],
  outline_approved: ['Writing script', 'working'],
  scripted: ['Review script', 'needs'],
  generating: ['Generating', 'working'],
  assembled: ['Review render', 'needs'],
  render_approved: ['Ready to publish', 'needs'],
  publishing: ['Publishing', 'working'],
  scheduled: ['Scheduled', 'done'],
  live: ['Live', 'done'],
  failed: ['Failed', 'error'],
  blocked: ['Blocked', 'error'],
}

export const STAGES: Record<string, string> = {
  outline: 'Outline',
  script: 'Script',
  regen: 'Redo flagged scenes',
  voice: 'Voice',
  stills: 'Pictures',
  clips: 'Clips',
  thumbs: 'Thumbnails',
  assemble: 'Render',
  upload: 'Upload to YouTube',
}

export const money = (usd: number | null | undefined) => `$${(usd ?? 0).toFixed(2)}`

/** 83_000 -> "1:23", 3_723_000 -> "1:02:03" */
export function clock(ms: number | null | undefined): string {
  const total = Math.floor((ms ?? 0) / 1000)
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const s = String(total % 60).padStart(2, '0')
  return h ? `${h}:${String(m).padStart(2, '0')}:${s}` : `${m}:${s}`
}

export function when(epoch: number): string {
  return new Date(epoch * 1000).toLocaleString(undefined, {
    weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', timeZoneName: 'short',
  })
}

/** Epoch seconds <-> the local "YYYY-MM-DDTHH:mm" a datetime-local input uses. */
export function toLocalInput(epoch: number): string {
  const d = new Date(epoch * 1000)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

export function fromLocalInput(value: string): number {
  return new Date(value).getTime() / 1000
}
