import type { Artifact } from '../generated'
import { resultCount } from '../lib/bulk'
import { shortId } from '../lib/format'

type Spread = Array<{ value: string; count: number }>
type Summary = {
  kind?: string; metric?: string
  completed?: number; not_completed?: number; reasons?: Array<{ reason: string; count: number }>
  prompt_tokens?: number; completion_tokens?: number; mean_latency_ms?: number | null
  verdicts?: Record<string, number>; values?: Record<string, Spread>
  scored?: number; unscored?: number; mean_accuracy?: number | null
  by?: Record<string, Array<{ value: string; count: number; mean_accuracy: number | null }>>
}
type Provenance = { provider?: { model?: string }; model_id?: string; candidate_artifact_id?: string }

const KINDS = ['vlm.answer', 'vlm.tag', 'vlm.judge', 'score.vqa_accuracy']
const TITLE: Record<string, string> = { 'vlm.answer': 'Answers', 'vlm.tag': 'Tags', 'vlm.judge': 'Verdicts', 'score.vqa_accuracy': 'VQA accuracy' }
const percent = (value: number | null | undefined) => (value == null ? 'n/a' : `${(value * 100).toFixed(1)}%`)

export function runSummary(artifact: Artifact): Summary | null {
  const summary = artifact.data?.summary as Summary | undefined
  return summary && typeof summary === 'object' && Object.keys(summary).length ? summary : null
}

function RunCard({ artifact, all }: { artifact: Artifact; all: Artifact[] }) {
  const summary = runSummary(artifact)
  const provenance = (artifact.provenance?.processor_provenance ?? {}) as Provenance
  const candidate = all.find(item => item.id === provenance.candidate_artifact_id)
  const candidateModel = (candidate?.provenance?.processor_provenance as Provenance | undefined)?.provider?.model
  const model = provenance.provider?.model ?? provenance.model_id
  const total = resultCount(artifact)
  return (
    <section aria-label={`Model run ${artifact.id}`}>
      <div className="insp-kicker">{TITLE[artifact.kind]} · {shortId(artifact.id, 12)}</div>
      <p className="hint">{[model, candidate ? `answers of ${candidateModel ?? 'an earlier run'} (${shortId(candidate.id, 12)})` : '', `${total.toLocaleString()} records with a result`].filter(Boolean).join(' · ')}</p>
      {summary?.metric === 'vqa_accuracy' && <>
        <dl className="dl">
          <div><dt>Mean accuracy</dt><dd><strong>{percent(summary.mean_accuracy)}</strong></dd></div>
          <div><dt>Scored / not scored</dt><dd>{(summary.scored ?? 0).toLocaleString()} / {(summary.unscored ?? 0).toLocaleString()}</dd></div>
        </dl>
        {Object.entries(summary.by ?? {}).map(([field, rows]) => (
          <details className="disclosure" key={field}>
            <summary>By {field.replace(/^source\./, '').replaceAll('_', ' ')}</summary>
            <div className="body"><table className="table"><thead><tr><th>Value</th><th>Records</th><th>Accuracy</th></tr></thead><tbody>
              {rows.slice(0, 12).map(row => <tr key={row.value}><td>{row.value}</td><td>{row.count.toLocaleString()}</td><td>{percent(row.mean_accuracy)}</td></tr>)}
            </tbody></table></div>
          </details>
        ))}
      </>}
      {summary?.verdicts && (
        <dl className="dl">{Object.entries(summary.verdicts).map(([verdict, count]) => <div key={verdict}><dt>{verdict}</dt><dd>{count.toLocaleString()}</dd></div>)}</dl>
      )}
      {summary?.values && Object.entries(summary.values).map(([name, rows]) => (
        <details className="disclosure" key={name}>
          <summary>{name}</summary>
          <div className="body"><table className="table"><thead><tr><th>Value</th><th>Records</th></tr></thead><tbody>
            {rows.map(row => <tr key={row.value}><td>{row.value}</td><td>{row.count.toLocaleString()}</td></tr>)}
          </tbody></table></div>
        </details>
      ))}
      {summary?.not_completed ? (
        <p className="hint" role="status">
          {summary.not_completed.toLocaleString()} {summary.not_completed === 1 ? 'record has' : 'records have'} no result{summary.reasons?.length ? `: ${summary.reasons.map(item => `${item.reason} (${item.count.toLocaleString()})`).join('; ')}` : ''}.
        </p>
      ) : null}
      {summary?.completed != null && summary.mean_latency_ms != null && (
        <p className="hint">{(summary.prompt_tokens ?? 0).toLocaleString()} prompt and {(summary.completion_tokens ?? 0).toLocaleString()} reply tokens · {Math.round(summary.mean_latency_ms).toLocaleString()} ms per request on average.</p>
      )}
    </section>
  )
}

/** What each finished model run produced and what did not work, so a partial run is not mistaken for a complete one. */
export function ModelRunResults({ artifacts }: { artifacts: Artifact[] }) {
  const runs = artifacts.filter(artifact => KINDS.includes(artifact.kind)).slice(0, 12)
  if (!runs.length) return null
  return (
    <div className="insp-section">
      <details className="disclosure" open={runs.length <= 3} style={{ borderTop: 0 }}>
        <summary>Finished model runs ({runs.length})</summary>
        <div className="body col" style={{ gap: 16 }}>
          {runs.map(artifact => <RunCard key={artifact.id} artifact={artifact} all={artifacts} />)}
        </div>
      </details>
    </div>
  )
}
