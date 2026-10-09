import { useEffect, useState } from 'react'
import type { Artifact, FieldDescriptor, Selection } from '../generated'
import { provider, type ProcessorDescriptor } from '../provider'
import { isEmbeddingArtifact, runLabel, type Unit } from '../dataset/model'
import { Field, Notice, Spinner } from '../ui/primitives'
import { compact } from '../lib/format'
import * as Icon from '../ui/Icons'
import { ComparisonResults } from './ComparisonResults'

const NEEDS_EMBEDDING = ['project.', 'cluster.', 'outlier.']

const GROUP_LABEL: Record<string, string> = {
  detect: 'Detect objects or content',
  embed: 'Compute embeddings',
  project: 'Project to 2D',
  cluster: 'Cluster',
  outlier: 'Score outliers',
  quality: 'Basic quality checks',
  import: 'Import external results',
  compare: 'Compare two fields',
}

/** One consistent form: analysis → input → recipe → output → estimate → run. */
export function AnalyzePanel({ selected, unit, saved, fields = [], artifacts = [], populationScope = 'preview', onSave, onRan, onSelectIds }: {
  selected: string[]
  unit: Unit
  saved: Selection | null
  fields?: FieldDescriptor[]
  artifacts?: Artifact[]
  populationScope?: string
  onSelectIds?: (ids: string[]) => void
  onSave: () => Promise<Selection | null>
  onRan: (message: string) => void
}) {
  const [processors, setProcessors] = useState<ProcessorDescriptor[]>([])
  const [embeddings, setEmbeddings] = useState<Artifact[]>([])
  const [processorId, setProcessorId] = useState('')
  const [embeddingId, setEmbeddingId] = useState('')
  const [config, setConfig] = useState('{}')
  const [configError, setConfigError] = useState('')
  const [estimate, setEstimate] = useState<Record<string, unknown> | null>(null)
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [leftField, setLeftField] = useState('')
  const [rightField, setRightField] = useState('')
  const [comparisonKind, setComparisonKind] = useState('correlation')
  const [detectorId, setDetectorId] = useState('')
  const [displayThreshold, setDisplayThreshold] = useState(0.5)

  const needsEmbedding = NEEDS_EMBEDDING.some(prefix => processorId.startsWith(prefix))
  const processor = processors.find(item => item.id === processorId)

  useEffect(() => {
    provider.processors().then(setProcessors).catch(failure => setMessage(String(failure)))
    provider.artifacts().then(items => setEmbeddings(items.filter(isEmbeddingArtifact))).catch(() => {})
  }, [])
  useEffect(() => { setEstimate(null) }, [processorId, embeddingId, config, JSON.stringify(selected), saved?.id, leftField, rightField, comparisonKind, detectorId, displayThreshold])

  if (provider.mode === 'static') {
    return (
      <div className="insp-section">
        <Notice tone="quiet">
          Computation runs in the local workbench. Published results stay browsable here in Grid, Table, Map and the inspector.
        </Notice>
      </div>
    )
  }

  function effectiveConfig(): Record<string, unknown> {
    const parsed = JSON.parse(config) as Record<string, unknown>
    return { ...parsed, ...(needsEmbedding ? { embedding_artifact_id: embeddingId } : {}),
      ...(processorId === 'compare.fields' ? { left_field: leftField, right_field: rightField, kind: comparisonKind, population_scope: populationScope } : {}),
      ...(processorId === 'detect.view' ? { detector_artifact_id: detectorId, display_threshold: displayThreshold } : {}) }
  }

  async function runEstimate() {
    setBusy(true); setMessage(''); setConfigError('')
    try {
      const frozen = saved ?? await onSave()
      if (!frozen) throw new Error('The selection could not be saved.')
      setEstimate(await provider.estimateRun(frozen.id, processorId, effectiveConfig()))
      setMessage('Review the budget below, then run this exact configuration.')
    } catch (failure) {
      const text = String(failure instanceof Error ? failure.message : failure)
      if (text.includes('JSON')) setConfigError(text); else setMessage(text)
    } finally { setBusy(false) }
  }

  async function start() {
    setBusy(true); setMessage('')
    try {
      const digest = estimate?.estimate_digest
      if (typeof digest !== 'string') throw new Error('Estimate the resources first.')
      const frozen = saved ?? await onSave()
      if (!frozen) throw new Error('The selection could not be saved.')
      const run = await provider.startRun(frozen.id, processorId, effectiveConfig(), digest)
      onRan(`Run ${run.id} ${run.status ?? 'queued'} · ${processor?.name ?? processorId}`)
      setEstimate(null)
    } catch (failure) { setMessage(String(failure instanceof Error ? failure.message : failure)) }
    finally { setBusy(false) }
  }

  const grouped = new Map<string, ProcessorDescriptor[]>()
  for (const item of processors) {
    const group = GROUP_LABEL[item.id.split('.')[0]] ?? 'Other'
    grouped.set(group, [...(grouped.get(group) ?? []), item])
  }

  return (
    <>
      <div className="insp-section">
        <p style={{ fontSize: 'var(--fs-md)' }}>
          <strong>Analyze {compact(selected.length)} {unit} records</strong>
          {saved ? <> · frozen as “{saved.name}”</> : <> · the selection is frozen when you estimate</>}
        </p>
      </div>

      <div className="insp-section">
        <Field label="Analysis">{id => (
          <select id={id} className="select" value={processorId} onChange={event => setProcessorId(event.target.value)}>
            <option value="">Choose an analysis</option>
            {[...grouped].map(([group, items]) => (
              <optgroup key={group} label={group}>
                {items.map(item => (
                  <option
                    key={item.id} value={item.id}
                    disabled={item.available === false || Boolean(item.input_units && !item.input_units.includes(unit))}
                  >
                    {item.name ?? item.id}
                    {item.available === false ? ' — unavailable' : item.input_units && !item.input_units.includes(unit) ? ` — needs ${item.input_units.join('/')} unit` : ''}
                  </option>
                ))}
              </optgroup>
            ))}
          </select>
        )}</Field>
        {processor?.description && <p className="hint">{processor.description}</p>}
        {processor?.reason && <Notice tone="warn">{processor.reason}</Notice>}
        {processor?.configured_recipe && <p className="hint">A tested local recipe is configured for this processor.</p>}
      </div>

      {processorId && (
        <div className="insp-section">
          <Field label="Input" hint={`Current selection · ${unit} unit · original representations`}>{id => (
            <input id={id} className="input" readOnly value={`${selected.length.toLocaleString()} selected ${unit} records`} />
          )}</Field>
          {needsEmbedding && (
            <Field label="Embedding run" hint="A projection or cluster needs an existing embedding space over the same snapshot.">{id => (
              <select id={id} className="select" value={embeddingId} onChange={event => setEmbeddingId(event.target.value)}>
                <option value="">Choose an embedding artifact</option>
                {embeddings
                  .filter(artifact => !saved || artifact.snapshot_ids.some(snapshot => saved.snapshot_ids.includes(snapshot)))
                  .map(artifact => <option key={artifact.id} value={artifact.id}>{runLabel(artifact)} · {artifact.ids.length.toLocaleString()} {artifact.unit}</option>)}
              </select>
            )}</Field>
          )}
          {processorId === 'compare.fields' && <>
            <Field label="Comparison">{id => <select id={id} className="select" value={comparisonKind} onChange={event => { setComparisonKind(event.target.value); setLeftField(''); setRightField('') }}>
              <option value="correlation">Numeric correlation</option><option value="crosstab">Categorical cross-tabulation</option><option value="grouped_numeric">Numeric values by category</option>
            </select>}</Field>
            <Field label="First field">{id => <select id={id} className="select" value={leftField} onChange={event => setLeftField(event.target.value)}>
              <option value="">Choose a field</option>{fields.filter(field => comparisonKind === 'correlation' ? field.dtype === 'number' : !['array', 'object'].includes(field.dtype ?? 'string')).map(field => <option key={field.id} value={field.id}>{field.name} · {field.namespace}</option>)}
            </select>}</Field>
            <Field label="Second field">{id => <select id={id} className="select" value={rightField} onChange={event => setRightField(event.target.value)}>
              <option value="">Choose a field</option>{fields.filter(field => comparisonKind === 'crosstab' ? !['array', 'object'].includes(field.dtype ?? 'string') : field.dtype === 'number').map(field => <option key={field.id} value={field.id}>{field.name} · {field.namespace}</option>)}
            </select>}</Field>
          </>}
          {processorId === 'detect.view' && <>
            <Field label="Retained detector run" hint="This creates a named view of existing detections without running a model.">{id => <select id={id} className="select" value={detectorId} onChange={event => {
              setDetectorId(event.target.value)
              const source = artifacts.find(artifact => artifact.id === event.target.value)
              const provenance = source?.provenance?.processor_provenance as { extraction_threshold?: number; display_threshold?: number } | undefined
              setDisplayThreshold(provenance?.display_threshold ?? provenance?.extraction_threshold ?? 0.5)
            }}>
              <option value="">Choose a detector artifact</option>{artifacts.filter(artifact => artifact.kind.startsWith('detect.') && artifact.unit === unit && (!saved || artifact.snapshot_ids.every(snapshot => saved.snapshot_ids.includes(snapshot)))).map(artifact => <option key={artifact.id} value={artifact.id}>{runLabel(artifact)}</option>)}
            </select>}</Field>
            <Field label="Display threshold" hint="Boxes and counts use this threshold; the extraction threshold stays recorded in the source run.">{id => <input id={id} className="input" type="number" min={0} max={1} step={0.01} value={displayThreshold} onChange={event => setDisplayThreshold(Number(event.target.value))} />}</Field>
          </>}
          <details className="disclosure">
            <summary>Advanced configuration</summary>
            <div className="body">
              <textarea className="textarea" rows={5} value={config} onChange={event => setConfig(event.target.value)} aria-label="Configuration JSON" spellCheck={false} />
              {configError && <Notice tone="error">{configError}</Notice>}
            </div>
          </details>
        </div>
      )}

      <div className="insp-section">
        <button type="button" className="btn" disabled={!processorId || !selected.length || busy || (needsEmbedding && !embeddingId) || (processorId === 'detect.view' && !detectorId) || (processorId === 'compare.fields' && (!leftField || !rightField))} onClick={runEstimate}>
          {busy && !estimate ? <Spinner label="Estimating…" /> : <>Estimate resources and coverage</>}
        </button>
        {estimate && (
          <details className="disclosure" open>
            <summary>Resource and coverage estimate</summary>
            <div className="body"><pre className="raw">{JSON.stringify(estimate, null, 2)}</pre></div>
          </details>
        )}
        <button type="button" className="btn primary" disabled={!estimate?.estimate_digest || busy} onClick={start}>
          <Icon.Play size={13} />Run analysis
        </button>
        <p className="hint">After the run finishes, choose Refresh results to add it to the column picker, filters, inspector, and map colour selector. Nothing runs until you approve the estimate.</p>
        {message && <Notice tone={message.startsWith('Run ') ? 'info' : 'warn'}>{message}</Notice>}
      </div>
      <ComparisonResults artifacts={artifacts.filter(artifact => artifact.unit === unit)} onSelectIds={onSelectIds} />
    </>
  )
}
