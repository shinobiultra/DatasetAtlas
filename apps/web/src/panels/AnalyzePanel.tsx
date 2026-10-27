import { useEffect, useState } from 'react'
import type { Artifact, FieldDescriptor, Selection } from '../generated'
import { provider, type ProcessorDescriptor } from '../provider'
import { isEmbeddingArtifact, runLabel, type Unit } from '../dataset/model'
import { Field, Notice, Spinner } from '../ui/primitives'
import { compact } from '../lib/format'
import { resultCount } from '../lib/bulk'
import { OPTIONS, optionConfig } from './analysisOptions'
import * as Icon from '../ui/Icons'
import { ComparisonResults } from './ComparisonResults'
import { ModelRunResults } from './ModelRunResults'
import { ModelTaskForm } from './ModelTaskForm'
import { emptyModelParams, isLoopbackUrl, isModelProcessor, modelConfig, type ModelParams } from './modelTasks'

const NEEDS_EMBEDDING = ['project.', 'cluster.', 'outlier.']

const BACKEND_LABEL: Record<string, string> = { cuml: 'GPU · RAPIDS cuML', torch: 'GPU · PyTorch CUDA', cpu: 'CPU' }

function summarise(estimate: Record<string, unknown>): string {
  const limits = estimate.resource_limits as { max_wall_seconds?: number } | undefined
  const server = (estimate.processor_estimate as { provider?: { model?: string } } | undefined)?.provider?.model
  const parts = [
    typeof estimate.selected_count === 'number' ? `${estimate.selected_count.toLocaleString()} records` : '',
    typeof estimate.remote_calls === 'number' && estimate.remote_calls > 0 ? `${estimate.remote_calls.toLocaleString()} requests${server ? ` to ${server}` : ''}` : '',
    estimate.storage === 'arrays' ? 'stored as arrays' : 'stored as JSON items',
    estimate.resource_class === 'gpu' ? 'uses the GPU lane' : typeof estimate.resource_class === 'string' ? `${estimate.resource_class} lane` : '',
    limits?.max_wall_seconds ? `stops after ${Math.round(limits.max_wall_seconds / 60)} min` : '',
  ]
  return parts.filter(Boolean).join(' · ')
}

/** The exact text the first record sends, so the wording is checked before anything is sent. */
function examplePrompt(estimate: Record<string, unknown>) {
  const info = estimate.processor_estimate as { example_prompt?: Array<{ role: string; text: string }>; example_record?: string; images_per_request?: number } | undefined
  if (!info?.example_prompt?.length) return null
  return (
    <details className="disclosure" open>
      <summary>Exact prompt for the first record{info.images_per_request ? ' · with its image' : ''}</summary>
      <div className="body col" style={{ gap: 6 }}>
        {info.example_prompt.map((message, index) => <div key={index}><div className="insp-kicker">{message.role}</div><pre className="raw" style={{ whiteSpace: 'pre-wrap' }}>{message.text}</pre></div>)}
      </div>
    </details>
  )
}

const GROUP_LABEL: Record<string, string> = {
  detect: 'Detect objects or content',
  embed: 'Compute embeddings',
  vlm: 'Ask a model server',
  score: 'Score saved results',
  project: 'Project to 2D or 3D',
  cluster: 'Cluster',
  outlier: 'Score outliers',
  quality: 'Basic quality checks',
  import: 'Import external results',
  compare: 'Compare two fields',
}

/** One consistent form: analysis → input → recipe → output → estimate → run. */
export function AnalyzePanel({ selected, selectedCount, unit, saved, fields = [], artifacts = [], populationScope = 'preview', onSave, onRan, onSelectIds }: {
  selected: string[]
  /** Set when the selection is held on the server (a whole population) and `selected` is empty. */
  selectedCount?: number
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
  const [params, setParams] = useState<Record<string, string | number>>({})
  const [backend, setBackend] = useState('auto')
  const [storage, setStorage] = useState('auto')
  const [modelParams, setModelParams] = useState<ModelParams>(emptyModelParams)
  const [servers, setServers] = useState<Array<{ config: { id: string; model: string; base_url?: string } }>>([])

  const count = selectedCount ?? selected.length
  const needsEmbedding = NEEDS_EMBEDDING.some(prefix => processorId.startsWith(prefix))
  const processor = processors.find(item => item.id === processorId)
  const unitProblem = processor?.input_units && !processor.input_units.includes(unit)
    ? `This analysis needs ${processor.input_units.join(' or ')} records. Switch the browsing unit before estimating.` : ''
  const unavailable = processor?.available === false
  const blocked = !processor || unavailable || Boolean(unitProblem)
  const setupExtra = processorId.startsWith('detect.') ? 'vision' : processorId.startsWith('embed.') && processorId !== 'embed.api' ? 'embeddings' : needsEmbedding ? 'projection' : ''
  const modelRun = isModelProcessor(processorId)
  const model = modelRun ? modelConfig(processorId, modelParams, processor?.preset) : { config: {}, problems: [] as string[] }
  const loopbackServers = servers.filter(item => isLoopbackUrl(item.config.base_url))

  useEffect(() => {
    provider.processors().then(setProcessors).catch(failure => setMessage(String(failure)))
    provider.artifacts().then(items => setEmbeddings(items.filter(isEmbeddingArtifact))).catch(() => {})
    provider.providers().then(items => setServers(items as typeof servers)).catch(() => {})
  }, [])
  useEffect(() => { setParams({}); setBackend('auto'); setStorage('auto'); setModelParams(emptyModelParams()) }, [processorId])
  useEffect(() => { setEstimate(null) }, [processorId, embeddingId, config, params, modelParams, backend, storage, JSON.stringify(selected), saved?.id, leftField, rightField, comparisonKind, detectorId, displayThreshold])

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
    const chosen = optionConfig(processorId, params)
    if (processor?.backends && backend !== 'auto') chosen.backend = backend
    if (storage !== 'auto') chosen.storage = storage
    return { ...parsed, ...chosen, ...model.config, ...(needsEmbedding ? { embedding_artifact_id: embeddingId } : {}),
      ...(processorId === 'compare.fields' ? { left_field: leftField, right_field: rightField, kind: comparisonKind, population_scope: populationScope } : {}),
      ...(processorId === 'detect.view' ? { detector_artifact_id: detectorId, display_threshold: displayThreshold } : {}) }
  }

  async function runEstimate() {
    if (blocked) return
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
    if (blocked) return
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
          <strong>Analyze {compact(count)} {unit} records</strong>
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
        {(processor?.reason || unavailable) && <Notice tone="warn">{processor?.reason || 'This analysis is unavailable in the current workbench.'}</Notice>}
        {unitProblem && <Notice tone="warn">{unitProblem}</Notice>}
        {unavailable && setupExtra && <div className="col" style={{ gap: 6 }}>
          <p className="hint">In the Atlas checkout, install the optional libraries into the environment used by the workbench, then restart it. Existing extras are retained.</p>
          <pre className="raw"><code>{`uv sync --inexact --extra ${setupExtra}`}</code></pre>
        </div>}
        {unavailable && processor?.requires_local_model && <div className="col" style={{ gap: 6 }}>
          <p className="hint">Check the pinned local models, then preview the download plan:</p>
          <pre className="raw"><code>atlas models status</code></pre>
          <pre className="raw"><code>atlas models fetch</code></pre>
          <p className="hint">After reviewing the files and byte budget, run <code>atlas models fetch --execute</code> in your Atlas workspace to download, verify and configure them. Opening this panel downloads nothing.</p>
        </div>}
        {unavailable && isModelProcessor(processorId) && <p className="hint">Configure and probe a loopback OpenAI-compatible endpoint from Ask model, then select it below. Settings → Models lists your configured endpoints.</p>}
        {processor?.configured_recipe && <p className="hint">A tested local recipe is configured for this processor.</p>}
      </div>

      {processorId && (
        <div className="insp-section">
          <Field label="Input" hint={`Current selection · ${unit} unit · original representations`}>{id => (
            <input id={id} className="input" readOnly value={`${count.toLocaleString()} selected ${unit} records`} />
          )}</Field>
          {needsEmbedding && (
            <Field label="Embedding run" hint="A projection or cluster needs an existing embedding space over the same snapshot.">{id => (
              <select id={id} className="select" value={embeddingId} onChange={event => setEmbeddingId(event.target.value)}>
                <option value="">Choose an embedding artifact</option>
                {embeddings
                  .filter(artifact => !saved || artifact.snapshot_ids.some(snapshot => saved.snapshot_ids.includes(snapshot)))
                  .map(artifact => <option key={artifact.id} value={artifact.id}>{runLabel(artifact)} · {resultCount(artifact).toLocaleString()} {artifact.unit}{artifact.data?.bulk ? ' · arrays' : ''}</option>)}
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
          {modelRun && (
            <ModelTaskForm processorId={processorId} preset={processor?.preset} params={modelParams} onChange={setModelParams} fields={fields}
              servers={loopbackServers.map(item => ({ id: item.config.id, model: item.config.model }))} hiddenServers={servers.length - loopbackServers.length}
              artifacts={artifacts} unit={unit} snapshotIds={saved?.snapshot_ids} />
          )}
          {(OPTIONS[processorId] ?? []).map(option => (
            <Field key={option.key} label={option.label} hint={option.hint}>{id => option.kind === 'select' ? (
              <select id={id} className="select" value={String(params[option.key] ?? option.initial)} onChange={event => setParams(current => ({ ...current, [option.key]: event.target.value }))}>
                {option.choices.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select>
            ) : (
              <input id={id} className="input" type="number" min={option.min} max={option.max} step={option.step} value={params[option.key] ?? option.initial}
                onChange={event => setParams(current => ({ ...current, [option.key]: event.target.value }))} />
            )}</Field>
          ))}
          {processor?.backends && (
            <Field label="Compute" hint="Automatic uses a GPU when the work is big enough to repay starting one, and the CPU otherwise.">{id => (
              <select id={id} className="select" value={backend} onChange={event => setBackend(event.target.value)}>
                <option value="auto">Automatic</option>
                {processor.backends!.map(choice => <option key={choice.id} value={choice.id} disabled={!choice.installed}>{BACKEND_LABEL[choice.id] ?? choice.id}{choice.installed ? '' : ' (not installed)'}</option>)}
              </select>
            )}</Field>
          )}
          {!modelRun && (processorId.startsWith('embed.') || NEEDS_EMBEDDING.some(prefix => processorId.startsWith(prefix))) && (
            <Field label="Result storage" hint="Above 5,000 records results are stored as binary arrays; they are far smaller and faster. Copy a finished run from another workspace with `atlas runs import`.">{id => (
              <select id={id} className="select" value={storage} onChange={event => setStorage(event.target.value)}>
                <option value="auto">Automatic</option><option value="arrays">Arrays</option><option value="json">JSON items</option>
              </select>
            )}</Field>
          )}
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
        <button type="button" className="btn" disabled={blocked || !count || busy || model.problems.length > 0 || (needsEmbedding && !embeddingId) || (processorId === 'detect.view' && !detectorId) || (processorId === 'compare.fields' && (!leftField || !rightField))} onClick={runEstimate}>
          {busy && !estimate ? <Spinner label="Estimating…" /> : <>Estimate resources and coverage</>}
        </button>
        {model.problems.length > 0 && <ul className="hint" style={{ margin: 0, paddingLeft: 18 }}>{model.problems.map(problem => <li key={problem}>{problem}</li>)}</ul>}
        {estimate && (
          <details className="disclosure" open>
            <summary>Resource and coverage estimate</summary>
            <div className="body">
              <p className="hint" style={{ marginBottom: 8 }}>{summarise(estimate)}</p>
              {examplePrompt(estimate)}
              <pre className="raw">{JSON.stringify(estimate, null, 2)}</pre>
            </div>
          </details>
        )}
        <button type="button" className="btn primary" disabled={blocked || !estimate?.estimate_digest || busy} onClick={start}>
          <Icon.Play size={13} />Run analysis
        </button>
        <p className="hint">After the run finishes, choose Refresh results to add it to the column picker, filters, inspector, and map colour selector. Nothing runs until you approve the estimate.</p>
        {message && <Notice tone={message.startsWith('Run ') ? 'info' : 'warn'}>{message}</Notice>}
      </div>
      <ComparisonResults artifacts={artifacts.filter(artifact => artifact.unit === unit)} onSelectIds={onSelectIds} />
      <ModelRunResults artifacts={artifacts.filter(artifact => artifact.unit === unit)} />
    </>
  )
}
