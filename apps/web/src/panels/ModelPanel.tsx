import { displayUrl } from '../lib/display'
import { useEffect, useMemo, useState } from 'react'
import { provider } from '../provider'
import { display, shortId } from '../lib/format'
import { Field, Notice, Spinner, Tag } from '../ui/primitives'
import * as Icon from '../ui/Icons'
import type { FieldDescriptor } from '../generated'

type Capability = { status: string; checked_at?: string }
type ProviderEntry = { config: { id: string; model: string; base_url?: string; max_images?: number; timeout_seconds?: number }; capabilities?: Record<string, Capability> }

/** Image bytes are large and uninteresting in a review panel; the digest identifies them. */
function hideImageData(_key: string, value: unknown): unknown {
  return typeof value === 'string' && value.startsWith('data:image/')
    ? `[image data URL hidden in display: ${value.length} characters — identified by the SHA-256 and byte count in this context]`
    : value
}

export function ModelPanel({ selected, unit, snapshotIds, fields = [], resultSnapshotIds = [], onNotice }: { selected: string[]; unit: string; snapshotIds?: string[]; fields?: FieldDescriptor[]; resultSnapshotIds?: string[]; onNotice: (message: string) => void }) {
  const [providers, setProviders] = useState<ProviderEntry[]>([])
  const [providerId, setProviderId] = useState('')
  const [mode, setMode] = useState<'exploration' | 'evaluation'>('exploration')
  const [independent, setIndependent] = useState(false)
  const [batchBudget, setBatchBudget] = useState(8192)
  const [prompt, setPrompt] = useState('')
  const [context, setContext] = useState<Record<string, unknown> | null>(null)
  const [response, setResponse] = useState<Record<string, unknown> | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [imageAssets, setImageAssets] = useState<Array<{ id: string; recordId: string; uri: string }>>([])
  const [imageAssetIds, setImageAssetIds] = useState<string[]>([])
  const [history, setHistory] = useState<Record<string, unknown>[]>([])
  const [savedConversation, setSavedConversation] = useState<Record<string, unknown> | null>(null)
  const [configOpen, setConfigOpen] = useState(false)
  const [draft, setDraft] = useState({ id: '', baseUrl: 'http://127.0.0.1:1234/v1', model: '', apiKeyEnv: '' })
  const [configMessage, setConfigMessage] = useState('')
  const [contextFields, setContextFields] = useState<string[]>([])
  const [includeAnnotations, setIncludeAnnotations] = useState(false)
  const [useTools, setUseTools] = useState(false)
  const [toolCalls, setToolCalls] = useState(4)
  const [toolRows, setToolRows] = useState(100)
  const [activeJob, setActiveJob] = useState('')
  const [jobStatus, setJobStatus] = useState<Record<string, unknown> | null>(null)

  const refresh = () => provider.providers().then(items => setProviders(items as ProviderEntry[])).catch(failure => setError(String(failure)))
  useEffect(() => {
    if (provider.mode !== 'workbench') return
    void refresh()
    provider.conversations().then(setHistory).catch(() => {})
    provider.conversationJobs().then(jobs => {
      const running = jobs.find(job => ['running', 'cancelling'].includes(String(job.status)))
      if (running) { setActiveJob(String(running.id)); setBusy(true) }
    }).catch(() => {})
  }, [])

  useEffect(() => {
    if (!activeJob) return
    let live = true
    async function poll() {
      let failures = 0
      while (live) {
        try {
          const job = await provider.conversationJob(activeJob)
          if (!live) return
          failures = 0
          setJobStatus(job)
          if (!['running', 'cancelling'].includes(String(job.status))) {
            setResponse(job.result as Record<string, unknown> ?? null)
            if (job.error) setError(String(job.error))
            setActiveJob(''); setBusy(false)
            provider.conversations().then(setHistory).catch(() => {})
            onNotice(job.status === 'completed' ? 'Response saved with its context provenance.' : `Model request ${String(job.status)}; its available receipt is retained.`)
            return
          }
        } catch (failure) {
          failures += 1
          if (live) setError(`Request status temporarily unavailable; retrying. ${String(failure)}`)
        }
        await new Promise(resolve => setTimeout(resolve, Math.min(5000, 500 * 2 ** Math.min(failures, 4))))
      }
    }
    void poll()
    return () => { live = false }
  }, [activeJob])

  const key = JSON.stringify(selected)
  useEffect(() => {
    if (provider.mode !== 'workbench') return
    let live = true
    setImageAssets([]); setImageAssetIds([]); setContext(null); setResponse(null)
    if (!selected.length) return
    provider.records(selected, snapshotIds)
      .then(rows => { if (live) setImageAssets(rows.flatMap(row => (row.assets ?? []).filter(asset => asset.modality === 'image' && asset.uri).map(asset => ({ id: asset.id, recordId: row.id, uri: asset.uri! })))) })
      .catch(failure => { if (live) setError(String(failure instanceof Error ? failure.message : failure)) })
    return () => { live = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, JSON.stringify(snapshotIds)])

  const selectedProvider = providers.find(item => item.config.id === providerId)
  const imageCapability = selectedProvider?.capabilities?.['image_input']?.status ?? selectedProvider?.capabilities?.['single_image_input']?.status
  const imagesSupported = imageCapability === 'supported'
  const toolHost = selectedProvider?.config.base_url ? new URL(selectedProvider.config.base_url).hostname : ''
  const toolsSupported = selectedProvider?.capabilities?.tool_calls?.status === 'supported' && ['localhost', '127.0.0.1', '[::1]', '::1'].includes(toolHost)
  const availableFields = fields.filter(field => ['source', 'prediction', 'human'].includes(field.id.split('.')[0]))
  const maxImages = Math.min(8, selectedProvider?.config.max_images ?? 8)
  const request = useMemo(() => ({
    provider_id: providerId, record_ids: selected, mode,
    ...(snapshotIds?.length ? { snapshot_ids: snapshotIds } : {}),
    image_asset_ids: imageAssetIds, independent_records: mode === 'evaluation' && independent,
    fields: mode === 'exploration' ? contextFields.filter(id => availableFields.some(field => field.id === id)) : [],
    include_annotations: mode === 'exploration' && includeAnnotations,
    result_snapshot_ids: mode === 'exploration' && snapshotIds?.length ? resultSnapshotIds : [],
  }), [providerId, selected, mode, imageAssetIds, independent, snapshotIds, contextFields, includeAnnotations, JSON.stringify(fields), resultSnapshotIds])
  const requestKey = JSON.stringify(request)
  useEffect(() => { setContext(null); setResponse(null) }, [requestKey, useTools, toolCalls, toolRows])

  if (provider.mode === 'static') {
    return <div className="insp-section"><Notice tone="quiet">Model connections require the local workbench. Nothing on the public site talks to a model provider.</Notice></div>
  }

  async function preview() {
    setBusy(true); setError('')
    try { setContext(await provider.previewContext(request)); setResponse(null) }
    catch (failure) { setError(String(failure instanceof Error ? failure.message : failure)); setContext(null) }
    finally { setBusy(false) }
  }

  async function send() {
    setBusy(true); setError('')
    try {
      if (!context?.context_digest) throw new Error('Review the exact outgoing context first.')
      const job = await provider.startConversation({
        context: request, context_digest: context.context_digest,
        approved_provider_id: providerId, approved_record_ids: selected, prompt,
        deadline_seconds: Math.min(120, selectedProvider?.config.timeout_seconds ?? 60),
        use_tools: mode === 'exploration' && toolsSupported && useTools,
        max_iterations: 4, max_tool_calls: toolCalls, max_tool_rows: toolRows,
        ...(request.independent_records ? { max_batch_completion_tokens: batchBudget } : {}),
      })
      setActiveJob(String(job.id)); setJobStatus(job)
    } catch (failure) { setError(String(failure instanceof Error ? failure.message : failure)); setBusy(false) }
  }

  return (
    <>
      <div className="insp-section">
        <div className="row" style={{ flexWrap: 'wrap', gap: 6 }}>
          <Tag tone="accent">Attached: {selected.length.toLocaleString()} {unit} records</Tag>
          {providerId && <Tag tone={imagesSupported ? 'ok' : 'warn'}>{imagesSupported ? 'Image input supported' : imageCapability === undefined ? 'Image capability unknown' : 'No image input'}</Tag>}
        </div>
        <Field label="Provider">{id => (
          <select id={id} className="select" value={providerId} onChange={event => { setProviderId(event.target.value); setContext(null); setImageAssetIds([]) }}>
            <option value="">Choose a configured endpoint</option>
            {providers.map(item => <option key={item.config.id} value={item.config.id}>{item.config.model} · {item.config.id}</option>)}
          </select>
        )}</Field>
        <div className="row" style={{ gap: 6 }}>
          <button type="button" className="btn sm" onClick={() => setConfigOpen(value => !value)}>{configOpen ? 'Hide connection setup' : 'Add connection'}</button>
          <button type="button" className="btn sm" disabled={!providerId} onClick={async () => {
            try { const result = await provider.probeProvider(providerId); setConfigMessage(`Probe: ${JSON.stringify(result)}`); await refresh() }
            catch (failure) { setConfigMessage(String(failure instanceof Error ? failure.message : failure)) }
          }}>Probe capabilities</button>
        </div>
        {configOpen && (
          <div className="col" style={{ gap: 8, border: '1px solid var(--divider)', borderRadius: 'var(--radius-sm)', padding: 10, background: 'var(--surface-sunk)' }}>
            <Field label="Connection ID">{id => <input id={id} className="input" value={draft.id} onChange={event => setDraft({ ...draft, id: event.target.value })} placeholder="local-model" />}</Field>
            <Field label="OpenAI-compatible base URL">{id => <input id={id} className="input" value={draft.baseUrl} onChange={event => setDraft({ ...draft, baseUrl: event.target.value })} />}</Field>
            <Field label="Model">{id => <input id={id} className="input" value={draft.model} onChange={event => setDraft({ ...draft, model: event.target.value })} placeholder="Model identifier" />}</Field>
            <Field label="API key environment variable" hint="Keep the key in the workbench environment; it is never stored in the browser or a URL.">{id => (
              <input id={id} className="input" value={draft.apiKeyEnv} onChange={event => setDraft({ ...draft, apiKeyEnv: event.target.value })} placeholder="Optional variable name" />
            )}</Field>
            <button type="button" className="btn" disabled={!draft.id || !draft.model} onClick={async () => {
              try {
                await provider.addProvider({ id: draft.id, base_url: draft.baseUrl, model: draft.model, ...(draft.apiKeyEnv ? { api_key_env: draft.apiKeyEnv } : {}) })
                await refresh(); setProviderId(draft.id); setConfigOpen(false)
                setConfigMessage('Connection saved. Run the capability probe before relying on it.')
              } catch (failure) { setConfigMessage(String(failure instanceof Error ? failure.message : failure)) }
            }}>Save connection</button>
          </div>
        )}
        {configMessage && <Notice tone="quiet">{configMessage}</Notice>}
      </div>

      <div className="insp-section">
        <div className="insp-kicker">Mode</div>
        <div className="segmented" role="group" aria-label="Context mode">
          <button type="button" aria-pressed={mode === 'exploration'} onClick={() => { setMode('exploration'); setContext(null) }}>Explore</button>
          <button type="button" aria-pressed={mode === 'evaluation'} onClick={() => { setMode('evaluation'); setContext(null) }}>Evaluate</button>
        </div>
        <p className="hint">
          {mode === 'exploration'
            ? 'Exploration may include source annotations and other model outputs to help interpret examples.'
            : 'Evaluation sends only task-approved inputs. Gold labels, answer-bearing filenames and auxiliary predictions are excluded in code, not by prompt wording.'}
        </p>
        {mode === 'evaluation' && (
          <>
            <label className="facet-opt" style={{ margin: 0 }}>
              <input type="checkbox" checked={independent} onChange={event => { setIndependent(event.target.checked); setContext(null); setResponse(null) }} />
              <span>Evaluate each record independently</span>
            </label>
            <p className="hint">{independent ? 'Each record gets its own saved input and response.' : 'A joint request discusses the selected records together — that is one observation, not several.'}</p>
            {independent && (
              <Field label="Batch completion-token budget">{id => (
                <input id={id} className="input" type="number" min={1} max={100000} value={batchBudget} onChange={event => setBatchBudget(Number(event.target.value))} />
              )}</Field>
            )}
          </>
        )}
        {mode === 'exploration' && <>
          <div className="insp-kicker">Additional evidence to include</div>
          <p className="hint">Results selected for browsing are pinned to this context. Tick the fields to send their values.</p>
          <div style={{ maxHeight: 180, overflow: 'auto' }}>
            {availableFields.map(field => <label className="facet-opt" key={field.id}>
              <input type="checkbox" checked={contextFields.includes(field.id)} disabled={!contextFields.includes(field.id) && contextFields.length >= 64}
                onChange={event => setContextFields(ids => event.target.checked ? [...ids, field.id] : ids.filter(id => id !== field.id))} />
              <span>{field.name || field.id} · {field.namespace}</span>
            </label>)}
          </div>
          <label className="facet-opt"><input type="checkbox" checked={includeAnnotations} onChange={event => setIncludeAnnotations(event.target.checked)} /><span>Include source annotations</span></label>
          <label className="facet-opt"><input type="checkbox" checked={useTools && toolsSupported} disabled={!toolsSupported} onChange={event => setUseTools(event.target.checked)} /><span>Allow bounded read-only exploration tools</span></label>
          <p className="hint">Tools inspect only the approved records. A local provider must pass its tool-call probe first.</p>
          {useTools && toolsSupported && <div className="row" style={{ gap: 8 }}>
            <Field label="Tool-call limit">{id => <input id={id} className="input" type="number" min={1} max={16} value={toolCalls} onChange={event => setToolCalls(Math.max(1, Math.min(16, Number(event.target.value))))} />}</Field>
            <Field label="Total tool-row limit">{id => <input id={id} className="input" type="number" min={1} max={1000} value={toolRows} onChange={event => setToolRows(Math.max(1, Math.min(1000, Number(event.target.value))))} />}</Field>
          </div>}
        </>}
      </div>

      {imageAssets.length > 0 && (
        <div className="insp-section">
          <div className="insp-kicker">Images to send · {imageAssetIds.length} of {maxImages} allowed</div>
          <p className="hint">Images are transmitted only when ticked here, and only if the provider's image capability passed its probe.</p>
          <div style={{ maxHeight: 210, overflow: 'auto', border: '1px solid var(--divider)', borderRadius: 'var(--radius-sm)' }}>
            {imageAssets.slice(0, 100).map(asset => (
              <label key={asset.id} className="row" style={{ gap: 8, padding: '5px 8px', borderBottom: '1px solid var(--divider)', cursor: 'pointer' }}>
                <input
                  type="checkbox" checked={imageAssetIds.includes(asset.id)}
                  disabled={!imageAssetIds.includes(asset.id) && imageAssetIds.length >= maxImages}
                  onChange={event => { setImageAssetIds(ids => event.target.checked ? [...ids, asset.id] : ids.filter(id => id !== asset.id)); setContext(null); setResponse(null) }}
                  aria-label={`Include image asset ${asset.id}`}
                />
                <img src={displayUrl(asset.uri)} alt="" loading="lazy" style={{ width: 40, height: 30, objectFit: 'cover', borderRadius: 4, background: 'var(--n-150)' }} />
                <span className="truncate mono" style={{ fontSize: 'var(--fs-sm)' }} title={asset.recordId}>{shortId(asset.recordId, 18)}</span>
              </label>
            ))}
          </div>
        </div>
      )}

      <div className="insp-section">
        <button type="button" className="btn" disabled={!providerId || !selected.length || busy || (independent && selected.length > 100)} onClick={preview}>
          {busy && !context ? <Spinner label="Building context…" /> : <>Review what will be sent</>}
        </button>
        {context && (
          <details className="disclosure" open>
            <summary>Outgoing context · {display(context.context_digest)}</summary>
            <div className="body"><pre className="raw">{JSON.stringify(context, hideImageData, 2)}</pre></div>
          </details>
        )}
        {context?.external_send_allowed === false && <Notice tone="error">{display(context.external_send_reason)}</Notice>}
        {context && !imageAssetIds.length && imageAssets.length > 0 && (
          <Notice tone="warn">No image is attached. Anything the model says about the pictures is not based on seeing them.</Notice>
        )}
      </div>

      <div className="insp-section">
        <Field label="Message">{id => (
          <textarea id={id} className="textarea" rows={4} value={prompt} onChange={event => setPrompt(event.target.value)} placeholder="Ask about the selected records" />
        )}</Field>
        <button type="button" className="btn primary" disabled={!context || context.external_send_allowed !== true || !prompt.trim() || busy} onClick={send}>
          {busy && context ? <Spinner label="Sending…" /> : <><Icon.Chat size={13} />Send to provider</>}
        </button>
        {activeJob && <>
          <p className="hint" role="status">Request {String(jobStatus?.status ?? 'running')} · {String((jobStatus?.progress as { phase?: string } | undefined)?.phase ?? 'preparing_context').replaceAll('_', ' ')}</p>
          <button type="button" className="btn" disabled={jobStatus?.status === 'cancelling'} onClick={() => provider.cancelConversation(activeJob).then(setJobStatus).catch(failure => setError(String(failure)))}>Cancel model request</button>
        </>}
        {error && <Notice tone="error">{error}</Notice>}
      </div>

      {response && (
        <div className="insp-section">
          <details className="disclosure" open style={{ borderTop: 0 }}>
            <summary>
              {response.batch_id
                ? `Batch ${display(response.status)} · ${((response.completed_record_ids ?? []) as unknown[]).length} completed · ${((response.pending_record_ids ?? []) as unknown[]).length} pending`
                : 'Response and provenance'}
            </summary>
            <div className="body"><pre className="raw">{JSON.stringify(response, hideImageData, 2)}</pre></div>
          </details>
          {Boolean(response.batch_id) && response.status === 'partial' && <button type="button" className="btn sm" onClick={send}>Resume pending records</button>}
        </div>
      )}

      {history.length > 0 && (
        <div className="insp-section">
          <details className="disclosure" style={{ borderTop: 0 }}>
            <summary>Saved conversations ({history.length})</summary>
            <div className="body col" style={{ gap: 6 }}>
              {history.slice(0, 20).map(item => (
                <div key={String(item.id)} className="row" style={{ gap: 8, fontSize: 'var(--fs-sm)' }}>
                  <span className="truncate">{display(item.model)}</span>
                  <span className="spacer" />
                  <small>{display(item.mode)} · {((item.record_ids ?? []) as unknown[]).length} records</small>
                  <button type="button" className="btn sm" onClick={() => provider.conversation(String(item.id)).then(setSavedConversation).catch(failure => setError(String(failure)))}>Open</button>
                </div>
              ))}
              {savedConversation && <pre className="raw">{JSON.stringify(savedConversation, hideImageData, 2)}</pre>}
            </div>
          </details>
        </div>
      )}
    </>
  )
}
