import { createPortal } from 'react-dom'
import { useEffect, useRef, useState } from 'react'
import { localDatasetApi, preparationApi, type SourceInspection, type SourceOptions } from '../provider'
import { Notice } from '../ui/primitives'
import { formatBytes } from '../lib/format'

type Status = { id: string; status: string; stage?: string; error?: string; indexed_count?: number; expected_count?: number; downloaded_bytes?: number }
type Plan = { id: string; ready: boolean; requirements: string[]; expected_download_bytes: number }

const KIND_LABEL: Record<SourceInspection['kind'], string> = {
  images: 'Folder or archive of images', table: 'Table', embedded_parquet: 'Parquet file with embedded images', huggingface: 'Hugging Face dataset',
}
const NONE = ''

/** Register your own folder, table or Hugging Face dataset, then build its preview the same way catalogue data is built. */
export function AddDataset() {
  const [open, setOpen] = useState(false)
  const dialog = useRef<HTMLDialogElement>(null)
  useEffect(() => { if (open) dialog.current?.showModal(); else dialog.current?.close() }, [open])
  const [source, setSource] = useState('')
  const [options, setOptions] = useState<SourceOptions>({})
  const [found, setFound] = useState<SourceInspection | null>(null)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [added, setAdded] = useState<{ id: string; name: string } | null>(null)
  const [plan, setPlan] = useState<Plan | null>(null)
  const [status, setStatus] = useState<Status | null>(null)

  async function inspect(next: SourceOptions = options, keepName = false) {
    setBusy(true); setError(''); if (!keepName) setFound(null)
    try {
      const result = await localDatasetApi.inspect(source.trim(), next)
      setFound(result)
      if (!keepName) setName(result.suggested.name ?? '')
    } catch (failure) { setError(String(failure instanceof Error ? failure.message : failure)) }
    finally { setBusy(false) }
  }
  const choose = (key: string, value: string) => {
    const next = { ...options, [key]: value === NONE ? null : value }
    setOptions(next)
    void inspect(next, true)
  }

  async function register() {
    setBusy(true); setError('')
    try {
      const { dataset } = await localDatasetApi.add({ source: source.trim(), name: name.trim(), description, options: Object.fromEntries(Object.entries(options).filter(([, value]) => value)) })
      setAdded({ id: dataset.id, name: dataset.name })
      // A local source downloads nothing; a Hugging Face source is held to a 2 GB preview budget.
      const planned = await preparationApi.plan<Plan>(dataset.id, 2_000_000_000, 1_000_000_000, 'auto')
      setPlan(planned)
      if (planned.ready) setStatus(await preparationApi.start<Status>(planned.id))
    } catch (failure) { setError(String(failure instanceof Error ? failure.message : failure)) }
    finally { setBusy(false) }
  }

  const running = !!status && ['queued', 'running'].includes(status.status)
  useEffect(() => {
    if (!status || !running) return
    let live = true
    const timer = window.setInterval(() => { void preparationApi.status<Status>(status.id).then(value => { if (live) setStatus(value) }).catch(failure => { if (live) setError(String(failure)) }) }, 1500)
    return () => { live = false; window.clearInterval(timer) }
  }, [status?.id, running])

  function close() {
    setOpen(false)
    // The catalogue list was fetched before this dataset existed.
    if (added) { window.location.hash = `#/dataset/${encodeURIComponent(added.id)}`; window.location.reload() }
  }

  const columns = found?.kind === 'table' ? found.columns.map(column => column.name) : []
  const select = (label: string, key: string, current: string | null | undefined) => (
    <label className="hint">{label}
      <select className="select" aria-label={label} value={options[key] ?? current ?? NONE} disabled={busy} onChange={event => choose(key, event.target.value)}>
        <option value={NONE}>None</option>
        {columns.map(column => <option key={column} value={column}>{column}</option>)}
      </select>
    </label>
  )
  return <>
    <button type="button" className="btn" onClick={() => setOpen(true)}>Add dataset</button>
    {createPortal(<dialog ref={dialog} className="preparation-dialog" aria-label="Add your own dataset" onCancel={close}><section className="card-pad" aria-label="Add dataset">
      <div className="row"><h3>Add your own dataset</h3><span className="spacer" /><button type="button" className="btn" onClick={close}>Close</button></div>
      <p className="hint">Point Atlas at a folder or archive of images, a .csv/.tsv/.jsonl/.json/.parquet table, or a Hugging Face dataset URL. Your files are read in place and never modified or uploaded. The dataset stays on this machine.</p>
      {!added && <>
        <form className="row wrap" onSubmit={event => { event.preventDefault(); if (source.trim()) void inspect({}) }}>
          <input className="input" style={{ flex: 1, minWidth: 260 }} aria-label="Folder, file or Hugging Face URL" placeholder="/absolute/path/to/folder-or-file  or  https://huggingface.co/datasets/owner/name"
            value={source} onChange={event => { setSource(event.target.value); setFound(null); setOptions({}) }} />
          <button type="submit" className="btn" disabled={busy || !source.trim()}>Inspect</button>
        </form>
        {error && <Notice tone="warn">{error}</Notice>}
        {found && <div role="region" aria-label="Inspection result">
          <p><strong>{KIND_LABEL[found.kind]}</strong> · {found.count === null ? 'row count known after indexing' : `${found.count.toLocaleString()} ${found.unit}`} · {formatBytes(found.bytes)}
            {found.kind === 'huggingface' && ` · ${found.parquet_shards ?? 0} Parquet shard${found.parquet_shards === 1 ? '' : 's'}`}
            {found.labels.length > 0 && ` · labels: ${found.labels.join(', ')}`}</p>
          {found.warnings.map(message => <Notice key={message} tone="warn">{message}</Notice>)}
          {found.kind === 'table' && <div className="row wrap">
            {select('Image column', 'media_column', found.suggested.media_column)}
            {select('Text column', 'text_column', found.suggested.text_column)}
            {select('Question column', 'question_column', null)}
            {select('Unique ID column', 'id_column', found.suggested.id_column)}
            {(options.media_column ?? found.suggested.media_column) && <label className="hint">Image folder
              <input className="input" aria-label="Image folder" defaultValue={found.suggested.media_root ?? ''} disabled={busy}
                onBlur={event => { if (event.target.value && event.target.value !== (options.media_root ?? found.suggested.media_root)) choose('media_root', event.target.value) }} /></label>}
          </div>}
          {found.kind === 'table' && <details><summary>{found.columns.length} columns</summary>
            <ul>{found.columns.map(column => <li key={column.name}><code>{column.name}</code> · {column.dtype}{column.role ? ` · ${column.role}` : ''}{column.missing ? ` · ${column.missing.toLocaleString()} missing` : ''}</li>)}</ul></details>}
          <div className="row wrap" style={{ marginTop: 10 }}>
            <label style={{ flex: 1, minWidth: 220 }}>Name<input className="input" aria-label="Dataset name" value={name} onChange={event => setName(event.target.value)} /></label>
          </div>
          <label className="hint">Description (optional)<input className="input" aria-label="Description" value={description} onChange={event => setDescription(event.target.value)} /></label>
          <div className="row" style={{ marginTop: 12 }}>
            <button type="button" className="btn primary" disabled={busy || !name.trim() || found.gated === true} onClick={() => void register()}>Add and build preview</button>
          </div>
        </div>}
      </>}
      {added && <div role="status" aria-label="Preparation">
        <p><strong>{added.name}</strong> was added.</p>
        {error && <Notice tone="warn">{error}</Notice>}
        {plan && !plan.ready && <>{plan.requirements.map(message => <Notice key={message} tone="warn">{message}</Notice>)}<p className="hint">The dataset is registered; its preview could not be built yet.</p></>}
        {status && <p>{status.status}{status.stage ? ` · ${status.stage}` : ''}{status.indexed_count !== undefined ? ` · ${status.indexed_count.toLocaleString()}${status.expected_count ? ` / ${status.expected_count.toLocaleString()}` : ''} records` : ''}
          {status.downloaded_bytes ? ` · ${formatBytes(status.downloaded_bytes)} fetched` : ''}</p>}
        {status?.error && <Notice tone="warn">{status.error}</Notice>}
        <div className="row">
          {running && <button type="button" className="btn" onClick={() => void preparationApi.cancel<Status>(status!.id).then(setStatus)}>Cancel</button>}
          {!running && <button type="button" className="btn primary" onClick={close}>{status?.status === 'completed' ? 'Open dataset' : 'Close'}</button>}
        </div>
      </div>}
    </section></dialog>, document.body)}
  </>
}
