import { useEffect, useMemo, useState } from 'react'
import type { Artifact, FieldDescriptor, Query, Record as AtlasRecord } from '../generated'
import { provider } from '../provider'
import { fieldValue } from '../query'
import { display, isMissing, shortId, titleCase } from '../lib/format'
import { AssetView, RepresentationTag, assetLabel, classColour, imageAssets, primaryAsset } from '../ui/MediaView'
import { detectorStates, runLabel, type RunState } from '../dataset/model'
import { CopyButton, Notice, Tabs, Tag } from '../ui/primitives'
import { Value } from '../ui/Value'
import * as Icon from '../ui/Icons'

export type InspectorTab = 'annotations' | 'outputs' | 'metadata'

const STATE_TONE: Record<RunState['state'], 'ok' | 'warn' | 'danger' | 'default'> = {
  completed: 'ok', completed_empty: 'default', partial: 'warn', failed: 'danger', not_computed: 'default', other: 'warn',
}

export function RunStateRow({ state }: { state: RunState }) {
  return (
    <div className="row" role="status" data-artifact-id={state.artifact.id} style={{ gap: 8, alignItems: 'flex-start', padding: '5px 0' }}>
      <Tag tone={STATE_TONE[state.state]}>{state.state === 'not_computed' ? 'Not computed' : titleCase(state.state)}</Tag>
      <div style={{ minWidth: 0, fontSize: 'var(--fs-sm)' }}>
        <div className="truncate" title={state.runLabel}>{state.runLabel}</div>
        <div style={{ color: 'var(--text-muted)' }}>{state.summary}</div>
        {state.detail && <div style={{ color: 'var(--danger)' }} className="wrap-any">{state.detail}</div>}
        {state.state !== 'not_computed' && <div className="origin-line">Extraction threshold {display(state.threshold)} — lowering a display threshold cannot reveal boxes this run never kept.</div>}
      </div>
    </div>
  )
}

/** Source annotations, computed outputs and metadata, in that order, for one record. */
export function SampleInspector({ record, fields, artifacts, query, datasetId, onOpenRecord, onFocus }: {
  record: AtlasRecord
  fields: FieldDescriptor[]
  artifacts: Artifact[]
  query: Query | null
  datasetId: string
  onOpenRecord: (id: string) => void
  onFocus: () => void
}) {
  const [tab, setTab] = useState<InspectorTab>('annotations')
  const asset = primaryAsset(record)
  const images = imageAssets(record)
  const runs = useMemo(() => detectorStates(artifacts, record.id), [artifacts, record.id])
  const overlays = useMemo(() => runs.flatMap(state => state.overlays), [runs])
  const sourceEntries = Object.entries(record.source ?? {})
  const predictionEntries = Object.entries(record.prediction ?? {})
  const descriptor = (id: string) => fields.find(field => field.id === id)

  return (
    <>
      <div className="insp-media">
        {asset ? <AssetView asset={asset} overlays={overlays} controls alt={`Primary asset of ${record.id}`} /> : <div className="fallback" style={{ padding: 22 }}>No media on this record</div>}
      </div>
      {runs.length > 0 && (
        <div className="insp-section" aria-label="Detector runs for this record">
          <div className="insp-kicker">Detector runs</div>
          {runs.map(state => <RunStateRow key={state.artifact.id} state={state} />)}
        </div>
      )}
      <div className="insp-section">
        <div className="row" style={{ flexWrap: 'wrap', gap: 6 }}>
          {asset && <RepresentationTag asset={asset} />}
          {asset && Boolean(asset.metadata?.condition || asset.metadata?.source_role) && <Tag>{assetLabel(asset)}</Tag>}
          {images.length > 1 && <Tag>{images.length} images</Tag>}
          {record.unit && <Tag>{titleCase(record.unit)}</Tag>}
          <button type="button" className="btn sm" style={{ marginLeft: 'auto' }} onClick={onFocus}><Icon.Expand size={13} />Open</button>
        </div>
        {record.question && <div><div className="insp-kicker">Question</div><p style={{ fontSize: 'var(--fs-base)', lineHeight: 1.5 }}>{record.question}</p></div>}
        {record.text && <div><div className="insp-kicker">Text</div><p className="wrap-any" style={{ fontSize: 'var(--fs-md)', lineHeight: 1.55, maxHeight: 220, overflow: 'auto' }}>{record.text}</p></div>}
        {!!record.choices?.length && (
          <div>
            <div className="insp-kicker">Choices</div>
            <ol style={{ margin: 0, paddingLeft: 20, fontSize: 'var(--fs-md)', lineHeight: 1.6 }}>{record.choices.map((choice, index) => <li key={index}>{display(choice)}</li>)}</ol>
          </div>
        )}
        {!!record.conversation?.length && (
          <div>
            <div className="insp-kicker">Conversation · {record.conversation.length} turns</div>
            {record.conversation.map((turn, index) => (
              <div key={index} style={{ padding: '6px 0', borderBottom: '1px solid var(--divider)' }}>
                <strong style={{ fontSize: 'var(--fs-sm)', color: 'var(--text-muted)' }}>{display(turn.role)}</strong>
                <p style={{ fontSize: 'var(--fs-md)' }} className="wrap-any">{display(turn.content)}</p>
              </div>
            ))}
          </div>
        )}
      </div>

      <div style={{ padding: '0 var(--s-4)' }}>
        <Tabs
          label="Record detail" value={tab} onChange={setTab}
          options={[
            { value: 'annotations', label: 'Annotations' },
            { value: 'outputs', label: 'Model outputs' },
            { value: 'metadata', label: 'Metadata' },
          ]}
        />
      </div>

      {tab === 'annotations' && (
        <div className="insp-section">
          <div className="insp-kicker">Source annotations</div>
          {sourceEntries.length ? (
            <dl className="dl">
              {sourceEntries.map(([key, value]) => {
                const field = descriptor(`source.${key}`)
                return (
                  <div key={key}>
                    <dt title={field?.description || `source.${key}`}>{field?.name ?? key}</dt>
                    <dd><Value value={value} /></dd>
                  </div>
                )
              })}
            </dl>
          ) : <p className="hint">This record carries no source annotation fields.</p>}
          {!!record.annotations?.length && (
            <details className="disclosure">
              <summary>Structured annotations ({record.annotations.length})</summary>
              <div className="body">
                {record.annotations.map(annotation => (
                  <div className="anno-row" key={annotation.id}>
                    <span className="dot" style={{ background: classColour(String(annotation.field_id)) }} />
                    <span className="truncate" title={annotation.field_id}>{annotation.field_id}</span>
                    <span className="score">{display(annotation.value)}</span>
                  </div>
                ))}
              </div>
            </details>
          )}
        </div>
      )}

      {tab === 'outputs' && (
        <div className="insp-section">
          <div className="insp-kicker">Computed results</div>
          {runs.length > 0 && <p className="hint">{runs.length} detector run{runs.length === 1 ? '' : 's'} are summarised under the media, with their extraction thresholds.</p>}
          {predictionEntries.length ? (
            <dl className="dl">
              {predictionEntries.map(([key, value]) => {
                const field = descriptor(`prediction.${key}`)
                return (
                  <div key={key}>
                    <dt title={field?.description || `prediction.${key}`}>{field?.name ?? key}</dt>
                    <dd><Value value={value} /></dd>
                  </div>
                )
              })}
            </dl>
          ) : !runs.length && <p className="hint">No run has produced a result for this record. That is different from a run finding nothing.</p>}
          <SimilarPanel record={record} artifacts={artifacts} query={query} datasetId={datasetId} onOpenRecord={onOpenRecord} />
        </div>
      )}

      {tab === 'metadata' && (
        <div className="insp-section">
          <dl className="dl">
            <div><dt>Record ID</dt><dd className="mono wrap-any">{record.id}</dd></div>
            <div><dt>Unit</dt><dd>{record.unit ?? 'example'}</dd></div>
            <div><dt>Dataset</dt><dd>{record.dataset_id}</dd></div>
            <div><dt>Release</dt><dd>{record.release_id}</dd></div>
            <div><dt>Snapshot</dt><dd className="mono wrap-any">{record.snapshot_id}</dd></div>
            <div><dt>Assets</dt><dd>{(record.assets ?? []).length}</dd></div>
          </dl>
          {(record.assets ?? []).map(asset => (
            <div key={asset.id} style={{ fontSize: 'var(--fs-sm)', color: 'var(--text-muted)', borderTop: '1px solid var(--divider)', paddingTop: 6 }}>
              <div className="row" style={{ gap: 6 }}><Tag>{asset.modality}</Tag><RepresentationTag asset={asset} /></div>
              <div className="mono wrap-any" style={{ marginTop: 3 }}>{asset.id}</div>
              {asset.sha256 && <div className="mono wrap-any">sha256 {shortId(asset.sha256, 16)}</div>}
            </div>
          ))}
          {!!record.relations?.length && (
            <details className="disclosure">
              <summary>Relations ({record.relations.length})</summary>
              <div className="body">
                {record.relations.map((relation, index) => (
                  <div key={index} className="row" style={{ gap: 6, fontSize: 'var(--fs-sm)', padding: '3px 0' }}>
                    <Tag tone="accent">{relation.type.replaceAll('_', ' ')}</Tag>
                    <button type="button" className="linkish mono truncate" onClick={() => onOpenRecord(relation.object_id)} title={relation.object_id}>{shortId(relation.object_id, 16)}</button>
                  </div>
                ))}
              </div>
            </details>
          )}
          <details className="disclosure">
            <summary>Raw record</summary>
            <div className="body"><pre className="raw">{JSON.stringify(record, null, 2)}</pre></div>
          </details>
          <div className="row"><CopyButton value={record.id} /></div>
        </div>
      )}
    </>
  )
}

function SimilarPanel({ record, artifacts, query, datasetId, onOpenRecord }: {
  record: AtlasRecord; artifacts: Artifact[]; query: Query | null; datasetId: string; onOpenRecord: (id: string) => void
}) {
  const spaces = artifacts.filter(artifact => artifact.kind.startsWith('embed.') && artifact.ids.includes(record.id))
  const [artifactId, setArtifactId] = useState('')
  const [text, setText] = useState('')
  const [useText, setUseText] = useState(false)
  const [results, setResults] = useState<Record<string, unknown> | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  useEffect(() => { setResults(null); setError('') }, [record.id])
  if (provider.mode !== 'workbench' || !spaces.length || !query) return null

  async function search() {
    setBusy(true); setError('')
    try {
      setResults(await provider.similarity(datasetId, {
        artifact_id: artifactId,
        ...(useText ? { text } : { record_id: record.id }),
        query, limit: 20,
      }))
    } catch (failure) { setError(String(failure instanceof Error ? failure.message : failure)); setResults(null) }
    finally { setBusy(false) }
  }

  const rows = (results?.results ?? []) as Array<{ id: string; distance: number }>
  return (
    <details className="disclosure">
      <summary>Similar samples</summary>
      <div className="body col" style={{ gap: 8 }}>
        <p className="hint">Similarity is computed in a named embedding space over the current population. It is not the same thing as the neighbouring examples in browsing order.</p>
        <select className="select" value={artifactId} onChange={event => { setArtifactId(event.target.value); setResults(null) }} aria-label="Embedding space">
          <option value="">Choose an embedding run</option>
          {spaces.map(artifact => <option key={artifact.id} value={artifact.id}>{runLabel(artifact)}</option>)}
        </select>
        <label className="facet-opt" style={{ margin: 0 }}>
          <input type="checkbox" checked={useText} onChange={event => { setUseText(event.target.checked); setResults(null) }} />
          <span>Query with new text instead of this record</span>
        </label>
        {useText && <input className="input" value={text} onChange={event => setText(event.target.value)} placeholder="Text query for a compatible encoder" />}
        <button type="button" className="btn" disabled={!artifactId || busy || (useText && !text.trim())} onClick={search}>
          {busy ? 'Searching…' : 'Find similar'}
        </button>
        {error && <Notice tone="error">{error}</Notice>}
        {results && (
          <>
            <p className="hint">{display(results.mode)} search over {display(results.eligible_count)} eligible records in {display(results.population_scope)}.</p>
            <ol style={{ margin: 0, paddingLeft: 18, fontSize: 'var(--fs-sm)' }}>
              {rows.map(row => (
                <li key={row.id} style={{ padding: '2px 0' }}>
                  <button type="button" className="linkish mono" onClick={() => onOpenRecord(row.id)} title={row.id}>{shortId(row.id, 14)}</button>
                  <span style={{ color: 'var(--text-muted)' }}> · {row.distance.toFixed(4)}</span>
                </li>
              ))}
            </ol>
          </>
        )}
      </div>
    </details>
  )
}

export function fieldSummary(record: AtlasRecord, field: FieldDescriptor): string {
  return display(fieldValue(record, field.id))
}
