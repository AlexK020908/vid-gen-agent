import { api } from '../api'
import { useAction } from '../app-context'
import { ErrorText } from '../parts'
import type { ConfirmCard } from '../types'

/** The agent wants to edit a prompt or channel file. Nothing changes until Approve. */
export function ConfirmView({ card, messageId, active }: { card: ConfirmCard; messageId: number; active: boolean }) {
  const { busy, error, run } = useAction()
  const answer = (allow: boolean) => run(() => api.confirm(messageId, allow))
  return (
    <div>
      <p className="card-topic mono">{card.path}</p>
      <Diff diff={card.diff} />
      {active && (
        <div className="card-actions">
          <div className="row">
            <span className="hint">Nothing changes until you approve.</span>
            <span className="spacer" />
            <button className="btn" disabled={busy} onClick={() => answer(false)}>Deny</button>
            <button className="btn primary" disabled={busy} onClick={() => answer(true)}>Approve change</button>
          </div>
          <ErrorText>{error}</ErrorText>
        </div>
      )}
    </div>
  )
}

function Diff({ diff }: { diff: string }) {
  // Skip the ---/+++ file header; the path is shown above.
  const lines = diff.split('\n').filter((l, i) => !(i < 2 && (l.startsWith('---') || l.startsWith('+++'))))
  if (!lines.some((l) => l.trim())) return <p className="muted">No visible change.</p>
  return (
    <pre className="diff">
      {lines.map((l, i) => {
        const kind = l.startsWith('@@') ? 'hunk' : l.startsWith('+') ? 'add' : l.startsWith('-') ? 'del' : ''
        return <div key={i} className={kind}>{l || ' '}</div>
      })}
    </pre>
  )
}
