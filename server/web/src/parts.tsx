import { useLayoutEffect, useRef, type ReactNode, type TextareaHTMLAttributes } from 'react'
import { STATES } from './format'
import type { VideoState } from './types'

export function StateBadge({ state }: { state: VideoState }) {
  const [label, tone] = STATES[state]
  return <span className={`badge tone-${tone}`}>{label}</span>
}

export function ErrorText({ children }: { children: ReactNode }) {
  return children ? <p className="error-text" role="alert">{children}</p> : null
}

export function MotionPill({ motion }: { motion: string }) {
  return motion === 'clip' ? <span className="pill clip" title="Gets a short AI video clip">clip</span> : null
}

/** A textarea that grows with its content, up to `max` pixels. */
export function AutoText({
  value, onChange, max = 240, ...rest
}: { value: string; onChange: (v: string) => void; max?: number } & Omit<
  TextareaHTMLAttributes<HTMLTextAreaElement>, 'value' | 'onChange'
>) {
  const ref = useRef<HTMLTextAreaElement>(null)
  useLayoutEffect(() => {
    const el = ref.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight + 2, max)}px`
  }, [value, max])
  return <textarea ref={ref} rows={1} value={value} onChange={(e) => onChange(e.target.value)} {...rest} />
}

export function Counter({ n, max }: { n: number; max: number }) {
  return <span className={`counter ${n > max ? 'over' : ''}`}>{n.toLocaleString()}/{max.toLocaleString()}</span>
}
