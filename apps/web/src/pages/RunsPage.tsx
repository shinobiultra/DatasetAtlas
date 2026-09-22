import { useEffect, useState } from 'react'
import type { Run } from '../generated'
import { provider } from '../provider'
import { display, relativeTime, shortId, titleCase } from '../lib/format'
import { Empty, Notice, Spinner, Tag } from '../ui/primitives'
import * as Icon from '../ui/Icons'

const STATUS_TONE: Record<string, 'ok' | 'warn' | 'danger' | 'accent' | 'default'> = {
  completed: 'ok', running: 'accent', queued: 'default', cancelled: 'warn', failed: 'danger', partial: 'warn',
}

function progressOf(run: Run): { done: number; total: number; fraction: number } | null {
  const progress = (run.progress ?? {}) as Record<string, unknown>
  const done = Number(progress.completed ?? progress.done ?? 0)
  const total = Number(progress.total ?? progress.items ?? 0)
  if (!Number.isFinite(total) || total <= 0) return null
  return { done, total, fraction: Math.min(1, done / total) }
}

/** A straightforward list, not an operations dashboard. */
export function RunsPage({ onToast }: { onToast: (message: string) => void }) {
  const [runs, setRuns] = useState<Run[] | null>(null)
  const [error, setError] = useState('')
  const [expanded, setExpanded] = useState<string | null>(null)

  const refresh = () => provider.runs().then(setRuns).catch(failure => setError(String(failure instanceof Error ? failure.message : failure)))
  useEffect(() => {
    void refresh()
    const timer = setInterval(() => { void refresh() }, 5000)
    return () => clearInterval(timer)
  }, [])

  if (provider.mode === 'static') {
    return (
      <div className="work"><div className="work-scroll"><div className="page">
        <header><h1>Runs</h1></header>
        <Notice tone="quiet">Analysis runs happen in the local workbench. The public build shows published results, not job history.</Notice>
      </div></div></div>
    )
  }

  return (
    <div className="work">
      <div className="work-scroll">
        <div className="page">
          <header>
            <div>
              <h1>Runs</h1>
              <p>Every computation records its processor, frozen input selection, configuration and per-item outcome.</p>
            </div>
            <button type="button" className="btn" style={{ marginLeft: 'auto' }} onClick={refresh}><Icon.Reset size={14} />Refresh</button>
          </header>
          {error && <Notice tone="error">{error}</Notice>}
          {runs === null && !error && <Spinner label="Loading runs…" />}
          {runs?.length === 0 && <Empty title="No runs yet">Select samples in a dataset and open Analyze to run a detector, embedding or projection.</Empty>}
          {!!runs?.length && (
            <div className="listcard">
              <div className="listrow runs head">
                <span>Run</span><span>Analysis</span><span>Input population</span><span>Status</span><span>Coverage</span><span>Actions</span>
              </div>
              {runs.map(run => {
                const progress = progressOf(run)
                const status = run.status ?? 'queued'
                return (
                  <div key={run.id}>
                    <div className="listrow runs">
                      <span className="stack">
                        <span className="truncate mono" style={{ fontSize: 'var(--fs-sm)' }} title={run.id}>{shortId(run.id, 14)}</span>
                        <small>{relativeTime(run.created_at)}</small>
                      </span>
                      <span className="truncate" title={run.processor_id}>{run.processor_id}</span>
                      <span className="truncate mono" style={{ fontSize: 'var(--fs-sm)' }} title={run.selection_id}>{shortId(run.selection_id, 12)}</span>
                      <span><Tag tone={STATUS_TONE[status] ?? 'default'}>{titleCase(status)}</Tag></span>
                      <span>
                        {progress
                          ? <><span className="progress"><i style={{ width: `${progress.fraction * 100}%` }} /></span><small>{progress.done.toLocaleString()} / {progress.total.toLocaleString()}</small></>
                          : <small>{display(run.progress ?? {})}</small>}
                      </span>
                      <span className="row" style={{ gap: 6 }}>
                        {['queued', 'running'].includes(status) && (
                          <button type="button" className="btn sm" onClick={() => provider.cancelRun(run.id).then(() => { onToast('Cancellation requested; completed work is kept.'); void refresh() }).catch(failure => setError(String(failure)))}>Cancel</button>
                        )}
                        <button type="button" className="btn sm ghost" onClick={() => setExpanded(expanded === run.id ? null : run.id)} aria-expanded={expanded === run.id}>Details</button>
                      </span>
                    </div>
                    {expanded === run.id && (
                      <div style={{ padding: '0 14px 14px', display: 'grid', gap: 8 }}>
                        <dl className="dl">
                          <div><dt>Run ID</dt><dd className="mono wrap-any">{run.id}</dd></div>
                          <div><dt>Selection</dt><dd className="mono wrap-any">{run.selection_id}</dd></div>
                          <div><dt>Artifacts</dt><dd>{(run.artifact_ids ?? []).length ? (run.artifact_ids ?? []).map(id => shortId(id, 10)).join(', ') : 'None registered yet'}</dd></div>
                          <div><dt>Completed</dt><dd>{run.completed_at ? relativeTime(run.completed_at) : 'Not finished'}</dd></div>
                        </dl>
                        {!!run.errors?.length && (
                          <details className="disclosure" open>
                            <summary>Per-item errors ({run.errors.length})</summary>
                            <div className="body"><pre className="raw">{JSON.stringify(run.errors, null, 2)}</pre></div>
                          </details>
                        )}
                        <details className="disclosure">
                          <summary>Configuration and provenance</summary>
                          <div className="body"><pre className="raw">{JSON.stringify({ config: run.config, provenance: run.provenance }, null, 2)}</pre></div>
                        </details>
                        <p className="hint">Results are attached to the browsing views for the matching snapshot — open the dataset and use the column picker, filters or map colour selector.</p>
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
