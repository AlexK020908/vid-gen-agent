import { clock, when } from '../format'
import type { MetricsCard } from '../types'

const num = (n: number | null) => (n === null ? '–' : n.toLocaleString())
const pct = (n: number | null) => (n === null ? '–' : `${n.toFixed(1)}%`)

const VERDICTS = {
  winner: 'Winner: above the channel’s median on watch time and click-through',
  loser: 'Below the channel’s median on watch time and click-through',
  mixed: 'Mixed: above the median on one, not the other',
}

function Verdict({ card }: { card: MetricsCard }) {
  if (!card.verdict) return null
  if (card.verdict === 'early' || !card.medians) {
    return <p className="verdict">Medians start once {card.min_videos} videos have this reading.</p>
  }
  const m = card.medians
  return (
    <p className={`verdict verdict-${card.verdict}`}>
      {VERDICTS[card.verdict]} (watch {pct(card.avd_pct)} vs {pct(m.avd_pct)}, click-through {pct(card.ctr)} vs
      {' '}{pct(m.ctr)}; medians of the last {m.n}).
    </p>
  )
}

export function MetricsView({ card }: { card: MetricsCard }) {
  const reach = card.impressions === null
  return (
    <div className="metrics">
      <div className="metric-grid">
        <Metric label="Views" value={num(card.views)} />
        <Metric label="Average view" value={card.avd_seconds === null ? '–' : clock(card.avd_seconds * 1000)}
          sub={card.avd_pct === null ? undefined : `${card.avd_pct.toFixed(1)}% of the video`} />
        <Metric label="Subscribers gained" value={num(card.subs_gained)} />
        <Metric label="Impressions" value={reach ? 'pending' : num(card.impressions)}
          sub={card.ctr === null ? undefined : `${card.ctr.toFixed(1)}% clicked`} />
      </div>
      <Verdict card={card} />
      {card.swap && (
        <p className="muted">
          Swapped {[card.swap.title && 'the title', card.swap.thumb !== null && 'the thumbnail'].filter(Boolean)
            .join(' and ')} {when(card.swap.applied_at)}
          {card.swap.ctr_before !== null && `, when click-through was ${pct(card.swap.ctr_before)}`}
          {card.swap.ctr_since !== null ? `; ${pct(card.swap.ctr_since)} since.` : '; click-through since shows once '
            + 'its days are in.'}
        </p>
      )}
      <p className="muted">
        {card.simulated ? 'Made-up numbers (youtube.mode is stub). ' : ''}
        {reach && !card.simulated ? 'Impressions and click-through fill in when YouTube’s daily reach files cover the '
          + 'window, a day or two later. ' : ''}
        {card.late_h ? `Read ${card.late_h} hours late (the app was off). ` : ''}
        {!card.simulated ? 'YouTube’s watch-time numbers lag a day or two, so early ones run low.' : ''}
      </p>
    </div>
  )
}

function Metric({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="metric">
      <span className="metric-label">{label}</span>
      <span className="metric-value">{value}</span>
      {sub && <span className="metric-sub">{sub}</span>}
    </div>
  )
}
