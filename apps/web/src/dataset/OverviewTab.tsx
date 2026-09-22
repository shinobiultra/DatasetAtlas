import { useEffect, useMemo, useState } from 'react'
import type { Artifact, Dataset, FieldDescriptor, Query, Record as AtlasRecord } from '../generated'
import { provider, type AggregateResponse } from '../provider'
import { compact, display, fieldOrigin, titleCase } from '../lib/format'
import { assetUrl, classColour, primaryAsset } from '../ui/MediaView'
import { runLabel } from './model'
import { Empty, Notice, Spinner, Tag } from '../ui/primitives'
import { useStoredState } from '../lib/hooks'
import * as Icon from '../ui/Icons'

const MAX_CHART_FIELDS = 6

function Bars({ result }: { result: Extract<AggregateResponse['results'][number], { kind: 'categorical' }> }) {
  const top = result.counts.slice(0, 8)
  const max = Math.max(1, ...top.map(entry => entry.count))
  return (
    <div className="bars">
      {top.map(entry => (
        <div className="bar-row" key={entry.value}>
          <span className="name" title={entry.value}>{entry.value === '' ? '(empty)' : entry.value}</span>
          <span className="bar-track"><i className="bar-fill" style={{ width: `${(entry.count / max) * 100}%`, background: classColour(entry.value) }} /></span>
          <span className="n">{compact(entry.count)}</span>
        </div>
      ))}
      <p className="hint">
        {result.denominator.toLocaleString()} records{result.missing ? ` · ${result.missing.toLocaleString()} missing` : ''}
        {result.truncated ? ' · most frequent values shown' : ''}
      </p>
    </div>
  )
}

function Numeric({ result, name }: { result: Extract<AggregateResponse['results'][number], { kind: 'numeric' }>; name: string }) {
  return (
    <div>
      <div className="ov-stats">
        <div className="ov-stat"><span className="v">{display(result.mean === null ? null : Number(result.mean.toFixed(3)))}</span><span className="k">mean</span></div>
        <div className="ov-stat"><span className="v">{display(result.min)}</span><span className="k">min</span></div>
        <div className="ov-stat"><span className="v">{display(result.max)}</span><span className="k">max</span></div>
      </div>
      <p className="hint">{name} · {result.present.toLocaleString()} of {result.denominator.toLocaleString()} present{result.missing ? ` · ${result.missing.toLocaleString()} missing` : ''}</p>
    </div>
  )
}

/** Mockup 8, but every card states the population it describes and nothing is invented. */
export function OverviewTab({ dataset, fields, artifacts, query, records, scopeLabel, onOpenRecord, onOpenAbout, onOpenAnalyze, onBrowse }: {
  dataset: Dataset
  fields: FieldDescriptor[]
  artifacts: Artifact[]
  query: Query | null
  records: AtlasRecord[]
  scopeLabel: string
  onOpenRecord: (id: string) => void
  onOpenAbout: () => void
  onOpenAnalyze: () => void
  onBrowse: () => void
}) {
  const chartFields = useMemo(
    () => fields.filter(field => field.dtype === 'category' || field.dtype === 'boolean' || field.dtype === 'number' || field.values?.length).slice(0, MAX_CHART_FIELDS),
    [fields],
  )
  const [aggregate, setAggregate] = useState<AggregateResponse | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [notes, setNotes] = useStoredState<Record<string, string>>('atlas.notes', {})
  const [draft, setDraft] = useState('')
  useEffect(() => { setDraft(notes[dataset.id] ?? '') }, [dataset.id, notes])

  const signature = query ? JSON.stringify({ ...query, limit: 0, cursor: null }) : ''
  useEffect(() => {
    if (!query || !chartFields.length) { setAggregate(null); return }
    let live = true
    setLoading(true); setError('')
    provider.aggregate(dataset.id, { ...query, limit: 1, cursor: null }, chartFields.map(field => field.id), 24)
      .then(response => { if (live) { setAggregate(response); setLoading(false) } })
      .catch(failure => { if (live) { setError(String(failure instanceof Error ? failure.message : failure)); setLoading(false) } })
    return () => { live = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dataset.id, signature, chartFields.map(field => field.id).join('|')])

  const coverage = dataset.coverage ?? {}
  const sheet = records.slice(0, 12)
  const analyses = artifacts.filter(artifact => artifact.snapshot_ids.includes(dataset.snapshot_id ?? ''))

  return (
    <div className="work-scroll">
      <div className="ov">
        <div className="ov-card">
          <header><h3>At a glance</h3></header>
          <div className="ov-stats">
            <div className="ov-stat"><span className="v">{compact(coverage.preview_count ?? 0)}</span><span className="k">{coverage.unit ?? 'example'} preview</span></div>
            <div className="ov-stat"><span className="v">{coverage.total_count ? compact(coverage.total_count) : '—'}</span><span className="k">reported release size</span></div>
            <div className="ov-stat"><span className="v">{(dataset.labels ?? []).length || '—'}</span><span className="k">listed labels</span></div>
          </div>
          <p className="hint">
            Preview counts are measured on the prepared local snapshot. A reported release size comes from the source or a paper and is not a measurement of what is browsable here.
          </p>
          <div className="row" style={{ gap: 6, flexWrap: 'wrap' }}>
            <Tag tone={coverage.access === 'public' ? 'ok' : 'warn'}>{titleCase(coverage.access ?? 'access unverified')}</Tag>
            <Tag>{titleCase(coverage.complete_data ?? 'complete data unimplemented')}</Tag>
            <Tag>{titleCase(coverage.publication ?? 'publication not reviewed')}</Tag>
          </div>
          <button type="button" className="btn sm" style={{ justifySelf: 'start' }} onClick={onOpenAbout}><Icon.Info size={13} />About this dataset</button>
        </div>

        <div className="ov-card">
          <header>
            <h3>Sample preview</h3>
            <button type="button" className="linkish" style={{ marginLeft: 'auto', fontSize: 'var(--fs-sm)' }} onClick={onBrowse}>Browse samples →</button>
          </header>
          {sheet.length ? (
            <div className="contact-sheet">
              {sheet.map(record => {
                const asset = primaryAsset(record)
                const url = asset ? assetUrl(asset) : null
                return (
                  <button type="button" key={record.id} onClick={() => onOpenRecord(record.id)} title={record.question ?? record.text ?? record.id} aria-label={`Inspect ${record.id}`}>
                    {url && asset?.modality === 'image'
                      ? <img src={url} alt="" loading="lazy" onError={event => { event.currentTarget.style.visibility = 'hidden' }} />
                      : <span className="tph clamp-3">{record.question ?? record.text ?? record.id}</span>}
                  </button>
                )
              })}
            </div>
          ) : <p className="hint">No records are loaded for the current scope and filters.</p>}
        </div>

        {error && <div className="ov-card wide"><Notice tone="warn">Distributions unavailable: {error}</Notice></div>}
        {loading && !aggregate && <div className="ov-card"><Spinner label="Computing distributions over the matched population…" /></div>}

        {aggregate?.results.map(result => {
          const field = chartFields.find(item => item.id === result.field_id)
          if (!field || result.kind === 'unsupported') return null
          if (result.kind === 'categorical' && !result.counts.length) return null
          return (
            <div className="ov-card" key={result.field_id}>
              <header>
                <h3 className="truncate" title={field.id}>{field.name}</h3>
                <Tag>{fieldOrigin(field)}</Tag>
              </header>
              {result.kind === 'categorical' ? <Bars result={result} /> : <Numeric result={result} name={field.name} />}
            </div>
          )
        })}

        {aggregate && (
          <div className="ov-card">
            <header><h3>Population described</h3></header>
            <p className="hint">{scopeLabel}</p>
            <dl className="dl">
              <div><dt>Records counted</dt><dd>{aggregate.denominator.toLocaleString()} {aggregate.unit}</dd></div>
              <div><dt>Count status</dt><dd>{aggregate.count_status}</dd></div>
              <div><dt>Scope</dt><dd>{aggregate.population_scope}</dd></div>
            </dl>
            {aggregate.warnings.map((warning, index) => <p key={index} className="hint">{warning}</p>)}
          </div>
        )}

        <div className="ov-card">
          <header><h3>Computed analyses</h3></header>
          {analyses.length ? (
            <div className="col" style={{ gap: 6 }}>
              {analyses.map(artifact => (
                <div className="row" key={artifact.id} style={{ gap: 8, fontSize: 'var(--fs-md)' }}>
                  <Tag tone="accent">{artifact.kind.split('.')[0]}</Tag>
                  <span className="truncate" title={artifact.id}>{runLabel(artifact)}</span>
                  <span className="spacer" />
                  <small>{artifact.ids.length.toLocaleString()} {artifact.unit}</small>
                </div>
              ))}
              <p className="hint">These results are available in the column picker, filters, inspector, and map colour selector.</p>
            </div>
          ) : (
            <Empty title="No analysis attached yet">
              {provider.mode === 'workbench'
                ? 'Select samples and run a detector, embedding, or projection; the outputs appear in the same browsing views.'
                : 'This published pack carries no computed results. Analysis runs in the local workbench.'}
            </Empty>
          )}
          {provider.mode === 'workbench' && (
            <button type="button" className="btn sm" style={{ justifySelf: 'start' }} onClick={onOpenAnalyze}><Icon.Sparkle size={13} />Open analysis</button>
          )}
        </div>

        <div className="ov-card wide">
          <header><h3>Notes</h3><small style={{ marginLeft: 'auto' }}>Stored in this browser only</small></header>
          <textarea
            className="textarea" rows={3} value={draft} onChange={event => setDraft(event.target.value)}
            placeholder={`Notes about ${dataset.name}…`} aria-label={`Notes about ${dataset.name}`}
          />
          <div className="row">
            <button type="button" className="btn sm" disabled={draft === (notes[dataset.id] ?? '')} onClick={() => setNotes(current => ({ ...current, [dataset.id]: draft }))}>Save note</button>
            {notes[dataset.id] && <button type="button" className="btn sm ghost" onClick={() => { setNotes(current => { const next = { ...current }; delete next[dataset.id]; return next }); setDraft('') }}>Clear</button>}
          </div>
        </div>
      </div>
    </div>
  )
}
