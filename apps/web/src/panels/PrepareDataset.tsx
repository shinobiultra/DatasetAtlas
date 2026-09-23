import { createPortal } from 'react-dom'
import { useEffect, useRef, useState } from 'react'
import { preparationApi } from '../provider'
import { Notice } from '../ui/primitives'
import { formatBytes } from '../lib/format'

type Plan = { id: string; ready: boolean; scope: string; source_identity: string; media_access?: string; source_total_bytes?: number; download_is_upper_bound?: boolean; expected_download_bytes: number; available_bytes: number; required_free_bytes: number; requirements: string[]; files: { source_name: string; bytes: number }[] }
type Status = { id: string; status: string; stage?: string; error?: string; indexed_count?: number; expected_count?: number; downloaded_bytes?: number; current_file?: string }
const bytes = formatBytes

export function PrepareDataset({ datasetId }: { datasetId: string }) {
  const [open, setOpen] = useState(false)
  const dialog = useRef<HTMLDialogElement>(null)
  useEffect(() => { if (open) dialog.current?.showModal(); else dialog.current?.close() }, [open])
  const [download, setDownload] = useState('10')
  const [output, setOutput] = useState('2')
  const [selective, setSelective] = useState(false)
  const [plan, setPlan] = useState<Plan | null>(null)
  const [status, setStatus] = useState<Status | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [jobId, setJobId] = useState(() => localStorage.getItem(`atlas.preparation.${datasetId}`) ?? '')
  useEffect(() => {
    let live = true
    void preparationApi.list<Status[]>(datasetId).then(rows => { if (live && rows.length) setJobId(rows[0].id) }).catch(e => { if (live) setError(String(e)) })
    return () => { live = false }
  }, [datasetId])
  useEffect(() => {
    if (!jobId) return
    let live = true
    const poll = () => preparationApi.status<Status>(jobId).then(value => { if (live) setStatus(value) }).catch(e => { if (live) setError(String(e)) })
    void poll()
    const timer = !status || ['queued', 'running'].includes(status.status) ? window.setInterval(() => void poll(), 2000) : undefined
    return () => { live = false; if (timer !== undefined) window.clearInterval(timer) }
  }, [jobId, status?.status])
  async function makePlan() {
    setBusy(true); setError(''); setPlan(null)
    try { setPlan(await preparationApi.plan<Plan>(datasetId, Math.round(Number(download) * 1e9), Math.round(Number(output) * 1e9), selective ? 'selective' : 'download')) }
    catch (e) { setError(String(e)) }
    finally { setBusy(false) }
  }
  async function start(id: string) {
    setBusy(true); setError('')
    try {
      setStatus(await preparationApi.start<Status>(id)); setJobId(id)
      localStorage.setItem(`atlas.preparation.${datasetId}`, id)
    } catch (e) { setError(String(e)) }
    finally { setBusy(false) }
  }
  const running = status && ['queued', 'running'].includes(status.status)
  return <div>
    <button className="btn" onClick={() => setOpen(!open)} aria-expanded={open}>Prepare full data</button>
    {createPortal(<dialog ref={dialog} className="preparation-dialog" aria-label="Dataset preparation" onCancel={() => setOpen(false)}><section className="card-pad" aria-label="Prepare full dataset">
      <div className="row"><h3>Prepare on request</h3><span className="spacer" /><button className="btn" onClick={() => setOpen(false)}>Close preparation</button></div>
      <p className="hint">Review the source and storage plan before downloading. Existing prepared versions are retained. Public sharing is a separate decision.</p>
      <label className="hint"><input type="checkbox" checked={selective} onChange={e => { setSelective(e.target.checked); setPlan(null) }} /> Keep Parquet images remote; index annotations only</label>
      <div className="row wrap">
        <label>Download limit (GB)<input aria-label="Download limit (GB)" type="number" min="0.01" max="10000" step="0.1" value={download} onChange={e => { setDownload(e.target.value); setPlan(null) }} /></label>
        <label>Prepared data limit (GB)<input aria-label="Prepared data limit (GB)" type="number" min="0.01" max="10000" step="0.1" value={output} onChange={e => { setOutput(e.target.value); setPlan(null) }} /></label>
        <button className="btn" disabled={busy || !!running} onClick={() => void makePlan()}>Review preparation plan</button>
      </div>
      {error && <Notice tone="warn">{error}</Notice>}
      {plan && <div>
        <p>{plan.scope}</p><p className="hint">{plan.source_identity}</p>
        {plan.media_access && <p className="hint">{plan.media_access}</p>}
        <p>{plan.download_is_upper_bound ? 'Up to ' : ''}{bytes(plan.expected_download_bytes)} download · {bytes(plan.required_free_bytes)} reserved · {bytes(plan.available_bytes)} free</p>
        {plan.source_total_bytes !== undefined && <p className="hint">{bytes(plan.source_total_bytes)} source population; image columns remain remote.</p>}
        {plan.files.length > 0 && <details><summary>{plan.files.length} pinned source files</summary><ul>{plan.files.map(f => <li key={f.source_name}>{f.source_name} ({bytes(f.bytes)})</li>)}</ul></details>}
        {plan.requirements.map(message => <Notice key={message} tone="warn">{message}</Notice>)}
        <button className="btn primary" disabled={!plan.ready || busy || !!running} onClick={() => void start(plan.id)}>Download and prepare</button>
      </div>}
      {status && <div role="status">
        <p>{status.status} {status.stage && `· ${status.stage}`} {status.indexed_count !== undefined && `· ${status.indexed_count.toLocaleString()} / ${status.expected_count?.toLocaleString()} records`}</p>
        {status.downloaded_bytes !== undefined && <p className="hint">{bytes(status.downloaded_bytes)} acquired{plan ? ` / ${bytes(plan.expected_download_bytes)}` : ''}{status.current_file ? ` · ${status.current_file}` : ''}</p>}
        {status.error && <Notice tone="warn">{status.error}</Notice>}
        {running && <button className="btn" onClick={() => void preparationApi.cancel<Status>(status.id).then(setStatus).catch(e => setError(String(e)))}>Cancel preparation</button>}
        {['failed', 'cancelled', 'interrupted'].includes(status.status) && <button className="btn" onClick={() => void start(status.id)}>Retry preparation</button>}
        {status.status === 'completed' && <button className="btn primary" onClick={() => window.location.reload()}>Open prepared data</button>}
      </div>}
    </section></dialog>, document.body)}
  </div>
}
