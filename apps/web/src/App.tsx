import { useEffect, useMemo, useRef, useState } from 'react'
import type { Artifact, Capabilities, Dataset, FieldDescriptor, Query, QueryResult, Record as AtlasRecord, Run, Selection } from './generated'
import { provider, publicUrl, type CompleteScope, type ProcessorDescriptor } from './provider'
import { fieldValue } from './query'

type Drawer = 'about' | 'analysis' | 'jobs' | 'models' | 'compare' | 'saved' | null
type View = 'grid' | 'table' | 'map'
type Unit = 'asset' | 'example' | 'entity' | 'conversation'

function route(): string { return decodeURIComponent(window.location.hash.slice(1) || '/') }
function useRoute(): [string, (path: string) => void] {
  const [path, setPath] = useState(route)
  useEffect(() => { const update = () => setPath(route()); window.addEventListener('hashchange', update); return () => window.removeEventListener('hashchange', update) }, [])
  return [path, path => { window.location.hash = path; setPath(path) }]
}

function display(value: unknown): string {
  if (value === null || value === undefined || value === '') return 'Missing'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

type DetectionOverlay = { assetId: string; width: number; height: number; boxes: Array<{ box: [number, number, number, number]; class: string; score: number }>; run: string; threshold: unknown }
type DetectorAssetOutput = { asset_id: string; status?: string; width?: number; height?: number; detections?: DetectionOverlay['boxes']; error?: string }
type DetectorItem = { id?: string; status?: string; output?: { assets?: DetectorAssetOutput[] } | null; error?: string }

function Media({ record, large = false, overlays = [] }: { record: AtlasRecord; large?: boolean; overlays?: DetectionOverlay[] }) {
  const media = (record.assets ?? []).map(asset => ({ ...asset, resolved: asset.uri ? provider.mode === 'static' ? publicUrl(asset.uri) : asset.uri : null }))
  const [failed, setFailed] = useState<string[]>([])
  const [loaded, setLoaded] = useState<Record<string, { uri: string; width: number; height: number }>>({})
  if (!media.length) return <div className="media-placeholder">No media for this record</div>
  return <div className={`media-strip ${large ? 'large' : ''}`}>
    {media.map((asset, index) => {
      const expected = overlays.filter(overlay => overlay.assetId === asset.id && overlay.width > 0 && overlay.height > 0)
      const image = loaded[asset.id]
      const oriented = image?.uri === asset.resolved ? image : null
      const aligned = expected.filter(overlay => oriented?.width === overlay.width && oriented.height === overlay.height)
      return <div className="media-item" key={asset.id}>{asset.resolved && !failed.includes(asset.resolved) && asset.modality === 'image' ? <>
        <img src={asset.resolved} loading="lazy" alt={`Source asset ${index + 1} for ${record.id}`} onLoad={event => setLoaded(current => ({ ...current, [asset.id]: { uri: asset.resolved!, width: event.currentTarget.naturalWidth, height: event.currentTarget.naturalHeight } }))} onError={() => setFailed(items => [...items, asset.resolved!])} />
        {aligned.map(overlay => <svg key={overlay.run} className="box-overlay" viewBox={`0 0 ${overlay.width} ${overlay.height}`} preserveAspectRatio="xMidYMid meet" aria-label={`${overlay.boxes.length} detections from run ${overlay.run}, threshold ${display(overlay.threshold)}`} role="img">{overlay.boxes.map((detection, i) => <g key={i}><rect x={detection.box[0]} y={detection.box[1]} width={Math.max(0, detection.box[2] - detection.box[0])} height={Math.max(0, detection.box[3] - detection.box[1])} fill="none" stroke="#e9c45e" strokeWidth="2" /><text x={detection.box[0]} y={Math.max(12, detection.box[1] - 4)} fontSize="12" fill="#fff" stroke="#15221e" strokeWidth="2" paintOrder="stroke">{detection.class} {detection.score.toFixed(2)}</text></g>)}</svg>)}
        {oriented && aligned.length !== expected.length && <span className="media-geometry-warning">Overlay hidden: image size differs from detector input</span>}
      </> : asset.resolved && asset.modality === 'audio' ? <audio src={asset.resolved} controls={large} aria-label={`Audio asset ${index + 1}`} /> : asset.resolved && asset.modality === 'video' ? <video src={asset.resolved} controls={large} preload="metadata" aria-label={`Video asset ${index + 1}`} /> : asset.text ? <div className="media-text">{asset.text}</div> : <div className="media-placeholder">{failed.includes(asset.resolved ?? '') ? 'Media could not be loaded' : `${asset.modality} representation unavailable`}<br /><small>{asset.id}</small></div>}</div>
    })}
  </div>
}

function RecordPreview({ record }: { record: AtlasRecord }) {
  const simpleSource = Object.entries(record.source ?? {}).filter(([, value]) => value !== null && ['string', 'number', 'boolean'].includes(typeof value)).slice(0, 2).map(([key, value]) => `${key}: ${display(value)}`).join(' · ')
  const text = record.question || record.text || (record.conversation?.length ? display(record.conversation[0]?.content) : '') || simpleSource
  return <><Media record={record} /><div className="card-body"><div className="record-title">{text || record.id}</div><div className="record-id" title={record.id}>{record.id}</div>{(record.assets?.length ?? 0) > 1 && <span className="tiny-tag">{record.assets?.length} assets</span>}{(record.conversation?.length ?? 0) > 0 && <span className="tiny-tag">Conversation</span>}</div></>
}

function catalogueMatch(dataset: Dataset, term: string): boolean {
  const haystack = [dataset.name, ...(dataset.aliases ?? []), dataset.description, ...(dataset.tasks ?? []), ...(dataset.labels ?? []), ...(dataset.paper_ids ?? []), dataset.coverage?.access].join(' ').toLocaleLowerCase()
  return haystack.includes(term.toLocaleLowerCase())
}

function canBrowse(dataset: Dataset): boolean {
  if (provider.mode === 'static') return dataset.coverage?.publication === 'approved' && (dataset.coverage.preview_count ?? 0) > 0
  return (dataset.coverage?.preview_count ?? 0) > 0 || dataset.coverage?.complete_data === 'supported'
}

function Catalogue({ navigate, openSaved }: { navigate: (path: string) => void; openSaved: () => void }) {
  const [items, setItems] = useState<Dataset[]>([])
  const [error, setError] = useState('')
  const [term, setTerm] = useState('')
  const [modality, setModality] = useState('')
  const [task, setTask] = useState('')
  const [access, setAccess] = useState('')
  const [paper, setPaper] = useState('')
  const [annotation, setAnnotation] = useState(false)
  useEffect(() => { provider.datasets().then(setItems).catch(err => setError(String(err))) }, [])
  const modalities = [...new Set(items.flatMap(item => item.modalities ?? []))].sort()
  const tasks = [...new Set(items.flatMap(item => item.tasks ?? []))].sort()
  const accessStates = [...new Set(items.map(item => item.coverage?.access ?? 'unavailable'))].sort()
  const shown = items.filter(item => catalogueMatch(item, term) && (!modality || item.modalities?.includes(modality)) && (!task || item.tasks?.includes(task)) && (!access || item.coverage?.access === access) && (!paper || item.paper_ids?.some(id => id.toLocaleLowerCase().includes(paper.toLocaleLowerCase()))) && (!annotation || (item.labels?.length ?? 0) > 0))
  return <main className="catalogue page-shell">
    <div className="page-heading"><div><p className="eyebrow">CATALOGUE</p><h1>Explore datasets</h1><p>Paper linked sources, examples, and their available evidence.</p></div><button className="subtle" onClick={openSaved}>Saved selections</button></div>
    <div className="catalogue-controls"><label className="search-box"><span className="sr-only">Search datasets</span><input autoFocus placeholder="Search datasets, labels, or papers" value={term} onChange={event => setTerm(event.target.value)} /></label><details className="filter-popover"><summary>Filters</summary><div className="filter-fields"><label>Modality<select value={modality} onChange={event => setModality(event.target.value)}><option value="">All</option>{modalities.map(value => <option key={value}>{value}</option>)}</select></label><label>Task<select value={task} onChange={event => setTask(event.target.value)}><option value="">All</option>{tasks.map(value => <option key={value}>{value}</option>)}</select></label><label>Access<select value={access} onChange={event => setAccess(event.target.value)}><option value="">All</option>{accessStates.map(value => <option key={value}>{value}</option>)}</select></label><label>Paper<input value={paper} onChange={event => setPaper(event.target.value)} placeholder="Paper ID" /></label><label className="checkline"><input type="checkbox" checked={annotation} onChange={event => setAnnotation(event.target.checked)} /> Has listed labels</label></div></details></div>
    {error && <div className="notice error" role="alert">Catalogue unavailable: {error}</div>}
    <p className="list-count">{shown.length} dataset{shown.length === 1 ? '' : 's'} in catalogue</p>
    <div className="dataset-list">{shown.map(item => <button className="dataset-row" key={item.id} onClick={() => navigate(`/dataset/${encodeURIComponent(item.id)}`)}><span className="dataset-primary"><strong>{item.name}</strong><span>{item.description || 'Description pending source review.'}</span><small>{(item.modalities ?? []).join(' · ') || 'Modality unknown'}{item.tasks?.length ? ` · ${item.tasks.join(', ')}` : ''}</small></span><span className="dataset-secondary"><span>{(item.labels ?? []).slice(0, 3).join(', ') || 'No listed labels'}</span><small>{item.coverage?.access ?? 'Access unknown'} · {canBrowse(item) ? `${item.coverage?.preview_count ?? 0} ${item.coverage?.unit ?? 'example'} preview` : 'metadata only'}</small></span><span className="row-arrow" aria-hidden>›</span></button>)}</div>
    {!error && !shown.length && <div className="empty">{items.length ? 'No datasets match these filters.' : 'No catalogue records have been published yet.'}</div>}
  </main>
}

type Evidence = Record<string, unknown>

function evidenceText(value: unknown): string { return typeof value === 'string' || typeof value === 'number' ? String(value) : '' }

function evidenceUrl(value: unknown): string | null {
  if (typeof value !== 'string') return null
  try { const url = new URL(value); return ['https:', 'http:'].includes(url.protocol) ? url.href : null } catch { return null }
}

function EvidenceReceipt({ item }: { item: Evidence }) {
  const kind = evidenceText(item.kind) || 'unspecified'
  const paper = evidenceText(item.paper_id)
  const page = evidenceText(item.page)
  const note = evidenceText(item.note) || evidenceText(item.excerpt)
  const checked = evidenceText(item.checked_on) || evidenceText(item.checked_at)
  const link = evidenceUrl(item.url) ?? evidenceUrl(item.source_url) ?? (Array.isArray(item.urls) ? item.urls.map(evidenceUrl).find(Boolean) ?? null : null)
  const scope = kind === 'corpus_mention' ? `Paper text check${item.review_scope ? ` · ${evidenceText(item.review_scope).replaceAll('_', ' ')}` : ''}` : kind.startsWith('source_audit_') ? `Agent source check${item.source_identity_status ? ` · ${evidenceText(item.source_identity_status).replaceAll('_', ' ')}` : ''}` : 'Source or release reference'
  return <article className="evidence-receipt"><strong>{kind.replaceAll('_', ' ')}</strong><small>{scope}</small>{paper && <p>Paper {paper}{page ? ` · p. ${page}` : ''}</p>}{link && <a href={link} target="_blank" rel="noopener noreferrer" title={link}>{link}</a>}{note && <p className="evidence-note" title={note}>{note}</p>}{checked && <small>Checked {checked}</small>}<details><summary>Full receipt</summary><pre>{JSON.stringify(item, null, 2)}</pre></details></article>
}

function EvidenceGroup({ title, items, shown }: { title: string; items: Evidence[]; shown: number }) {
  if (!items.length) return null
  return <div className="evidence-group"><h4>{title} <span>({items.length})</span></h4>{items.slice(0, shown).map((item, index) => <EvidenceReceipt item={item} key={`${evidenceText(item.evidence_id) || evidenceText(item.kind)}-${index}`} />)}{items.length > shown && <details><summary>Show {items.length - shown} more {title.toLowerCase()}</summary>{items.slice(shown).map((item, index) => <EvidenceReceipt item={item} key={`${evidenceText(item.evidence_id) || evidenceText(item.kind)}-${index + shown}`} />)}</details>}</div>
}

function EvidenceSection({ evidence }: { evidence: Evidence[] }) {
  const source = evidence.filter(item => item.kind !== 'corpus_mention').sort((a, b) => Number(evidenceText(b.kind).startsWith('source_audit_')) - Number(evidenceText(a.kind).startsWith('source_audit_')))
  const paper = evidence.filter(item => item.kind === 'corpus_mention')
  return <section className="evidence-section" aria-label="Dataset evidence"><h3>Evidence</h3><p>Source checks and paper mentions have separate review scopes. These receipts do not establish public reuse rights or review of the dataset candidate.</p>{evidence.length ? <><EvidenceGroup title="Source and release evidence" items={source} shown={3} /><EvidenceGroup title="Paper mentions" items={paper} shown={2} /></> : <p>No evidence receipts registered.</p>}</section>
}

function RelationshipSection({ relationships, navigate }: { relationships: Array<Record<string, unknown>>; navigate: (path: string) => void }) {
  const [catalogue, setCatalogue] = useState<Dataset[]>([])
  useEffect(() => { if (relationships.length) provider.datasets().then(setCatalogue).catch(() => {}) }, [relationships])
  if (!relationships.length) return null
  return <section className="relationship-section" aria-label="Related datasets"><h3>Related datasets</h3><p>Links describe source or annotation relationships. Each dataset has its own access, review, and preview status.</p>{relationships.map((item, index) => {
    const target = evidenceText(item.target) || evidenceText(item.alias_id)
    const related = catalogue.find(dataset => dataset.id === target)
    const status = evidenceText(item.status)
    const scope = evidenceText(item.scope)
    const source = evidenceUrl(item.source_url) ?? evidenceUrl(item.url)
    return <article className="relationship-receipt" key={`${target}-${index}`}><strong>{evidenceText(item.type).replaceAll('_', ' ') || 'Relationship'}</strong>{related ? <button className="text-link" onClick={() => navigate(`/dataset/${encodeURIComponent(related.id)}`)}>{related.name} <small>({related.id})</small> ↗</button> : <span>{target || 'Unresolved target'}</span>}{status && <small>Status: {status.replaceAll('_', ' ')}</small>}{scope && <small>Scope: {scope}</small>}{source && <a href={source} target="_blank" rel="noopener noreferrer">Source ↗</a>}{evidenceText(item.reason) && <p>{evidenceText(item.reason)}</p>}<details><summary>Relationship provenance</summary><pre>{JSON.stringify(item, null, 2)}</pre></details></article>
  })}</section>
}

function Inspector({ record, fields, artifacts, query, onOpen, close }: { record: AtlasRecord; fields: FieldDescriptor[]; artifacts: Artifact[]; query?: Query | null; onOpen?: (id: string) => void; close: () => void }) {
  const [copied, setCopied] = useState(false)
  const embeddingArtifacts = artifacts.filter(artifact => artifact.kind.startsWith('embed.') && artifact.ids.includes(record.id))
  const [embeddingId, setEmbeddingId] = useState('')
  const [useTextQuery, setUseTextQuery] = useState(false), [similarityText, setSimilarityText] = useState('')
  const [similarity, setSimilarity] = useState<Record<string, unknown> | null>(null)
  const [similarityError, setSimilarityError] = useState('')
  async function findSimilar() {
    if (!query) return
    try { setSimilarityError(''); setSimilarity(await provider.similarity(record.dataset_id, { artifact_id: embeddingId, ...(useTextQuery ? { text: similarityText } : { record_id: record.id }), query, limit: 20 })) } catch (err) { setSimilarityError(String(err)) }
  }
  const detections = artifacts.flatMap(artifact => {
    const items = (artifact.data?.items ?? []) as Array<{ id?: string; output?: unknown }>
    return items.filter(item => item.id === record.id).map(item => ({ artifact, output: item.output }))
  })
  const detectorStates = artifacts.filter(artifact => artifact.kind.startsWith('detect.')).map(artifact => {
    const item = ((artifact.data?.items ?? []) as DetectorItem[]).find(result => result.id === record.id)
    if (!item) return { artifact, summary: 'Not computed for this record', error: '' }
    if (item.status !== 'completed') return { artifact, summary: `${(item.status ?? 'unknown').replaceAll('_', ' ')} result`, error: item.error ?? item.output?.assets?.map(asset => asset.error).filter(Boolean).join('; ') ?? '' }
    const assets = item.output?.assets ?? []
    const completed = assets.filter(asset => asset.status === 'completed' && Array.isArray(asset.detections))
    const count = completed.reduce((total, asset) => total + (asset.detections?.length ?? 0), 0)
    if (!assets.length) return { artifact, summary: 'Completed without asset results', error: '' }
    if (completed.length !== assets.length) return { artifact, summary: `Partial result: ${count} detections; ${assets.length - completed.length} asset outputs unavailable`, error: assets.map(asset => asset.error).filter(Boolean).join('; ') }
    return { artifact, summary: `Completed: ${count} detections`, error: '' }
  })
  const overlays: DetectionOverlay[] = detections.filter(({ artifact }) => artifact.kind.startsWith('detect.')).flatMap(({ artifact, output }) => {
    const assets = (output as { assets?: DetectorAssetOutput[] } | null)?.assets ?? []
    const provenance = artifact.provenance?.processor_provenance as { extraction_threshold?: unknown } | undefined
    return assets.filter(asset => asset.status === 'completed' && Array.isArray(asset.detections)).map(asset => ({ assetId: asset.asset_id, width: asset.width ?? 0, height: asset.height ?? 0, boxes: asset.detections ?? [], run: artifact.run_id ?? artifact.id, threshold: provenance?.extraction_threshold ?? 'unknown' }))
  })
  return <aside className="inspector" aria-label="Sample inspector"><div className="panel-heading"><div><p className="eyebrow">SAMPLE INSPECTOR</p><h2>Record details</h2></div><button className="icon-btn" aria-label="Close inspector" onClick={close}>×</button></div><div className="inspector-scroll"><Media record={record} large overlays={overlays} />{detectorStates.map(({ artifact, summary, error }) => <p className="detector-state" role="status" key={artifact.id}><strong>{artifact.kind}</strong> · {summary}{error ? ` · ${error}` : ""}</p>)}{overlays.map(overlay => <p className="overlay-caption" key={overlay.run}>Boxes: run {overlay.run} · extraction threshold {display(overlay.threshold)} · {overlay.boxes.length} detections</p>)}<div className="inspect-section"><span className="eyebrow">ORIGINAL RECORD</span>{record.question && <><h3>Question</h3><p className="wrap">{record.question}</p></>}{record.text && <><h3>Text</h3><p className="wrap">{record.text}</p></>}{!!record.choices?.length && <><h3>Choices</h3><ol>{record.choices.map((choice, i) => <li key={i}>{display(choice)}</li>)}</ol></>}{!!record.conversation?.length && <><h3>Conversation</h3>{record.conversation.map((message, i) => <div className="conversation-turn" key={i}><strong>{display(message.role)}</strong><p>{display(message.content)}</p></div>)}</>}{!record.question && !record.text && !record.conversation?.length && <p>No text content is present.</p>}</div><details open className="inspect-section"><summary>Source fields</summary>{Object.entries(record.source ?? {}).length ? <dl className="field-list">{Object.entries(record.source ?? {}).map(([key, value]) => <div key={key}><dt title={fields.find(item => item.id === `source.${key}`)?.description}>{fields.find(item => item.id === `source.${key}`)?.name ?? key}</dt><dd>{display(value)}</dd></div>)}</dl> : <p>No source fields in this record.</p>}</details><details className="inspect-section"><summary>Computed results</summary><dl className="field-list">{Object.entries(record.prediction ?? {}).map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{display(value)}</dd></div>)}</dl>{detections.map(({ artifact, output }) => <div key={artifact.id}><p><strong>{artifact.kind}</strong> · {artifact.run_id ?? 'Published artifact'}</p><pre>{JSON.stringify(output, null, 2)}</pre></div>)}{!Object.keys(record.prediction ?? {}).length && !detections.length && <p>No computed result is attached to this record.</p>}</details>{embeddingArtifacts.length > 0 && provider.mode === 'workbench' && query && <details className="inspect-section"><summary>Similar records</summary><label>Embedding run<select value={embeddingId} onChange={event => { setEmbeddingId(event.target.value); setSimilarity(null) }}><option value="">Choose run</option>{embeddingArtifacts.map(artifact => <option value={artifact.id} key={artifact.id}>{artifact.kind} · {artifact.id.slice(-8)}</option>)}</select></label><label className="checkline"><input type="checkbox" checked={useTextQuery} onChange={event => { setUseTextQuery(event.target.checked); setSimilarity(null) }} /> Use a new text query</label>{useTextQuery && <label>Text query<input value={similarityText} onChange={event => setSimilarityText(event.target.value)} placeholder="Search in a compatible embedding space" /></label>}<button disabled={!embeddingId || (useTextQuery && !similarityText.trim())} onClick={findSimilar}>Find similar</button>{similarityError && <p role="alert">{similarityError}</p>}{similarity && <><p>{display(similarity.mode)} search · {display(similarity.eligible_count)} eligible {query.unit} records in {display(similarity.population_scope)}</p><ol>{((similarity.results ?? []) as Array<{ id: string; distance: number }>).map(item => <li key={item.id}><button className="text-link" onClick={() => onOpen?.(item.id)}>{item.id}</button> · distance {item.distance.toFixed(4)}</li>)}</ol></>}</details>}<details className="inspect-section"><summary>Annotations & relations</summary><pre>{JSON.stringify({ annotations: record.annotations ?? [], relations: record.relations ?? [] }, null, 2)}</pre></details><details className="inspect-section"><summary>Raw data</summary><pre>{JSON.stringify(record, null, 2)}</pre></details><div className="inspect-section"><button onClick={() => { navigator.clipboard.writeText(record.id).then(() => setCopied(true)) }}>{copied ? 'Copied ID' : 'Copy ID'}</button><p className="record-id wrap">{record.id}</p></div></div></aside>
}

function ProjectionMap({ records, artifact, colorField, onOpen, onSelect }: { records: AtlasRecord[]; artifact: Artifact; colorField: string; onOpen: (id: string) => void; onSelect: (ids: string[]) => void }) {
  const canvas = useRef<HTMLCanvasElement>(null)
  const drag = useRef<{ x: number; y: number; path: Array<{ x: number; y: number }>; pan: boolean } | null>(null)
  const [lasso, setLasso] = useState<Array<{ x: number; y: number }>>([])
  const [panMode, setPanMode] = useState(false)
  const [transform, setTransform] = useState({ scale: 1, dx: 0, dy: 0 })
  const points = useMemo(() => {
    const data = artifact.data ?? {}
    const raw = (data.points ?? data.items ?? []) as Array<{ id: string; x?: number; y?: number; status?: string; output?: { x?: number; y?: number } }>
    return raw.map(item => ({ id: item.id, x: item.x ?? item.output?.x, y: item.y ?? item.output?.y })).filter((item): item is { id: string; x: number; y: number } => Number.isFinite(item.x) && Number.isFinite(item.y))
  }, [artifact])
  const coords = useMemo(() => {
    if (!points.length) return []
    const xs = points.map(point => point.x), ys = points.map(point => point.y)
    const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys)
    const present = new Set(records.map(record => record.id))
    return points.filter(point => present.has(point.id)).map(point => ({ id: point.id, x: 24 + 752 * (point.x - minX) / (maxX - minX || 1), y: 24 + 452 * (1 - (point.y - minY) / (maxY - minY || 1)) }))
  }, [points, records])
  const colors = useMemo(() => {
    const lookup = new Map(records.map(record => [record.id, colorField ? fieldValue(record, colorField) : null]))
    const numeric = [...lookup.values()].filter((value): value is number => typeof value === 'number' && Number.isFinite(value))
    const min = Math.min(...numeric), max = Math.max(...numeric)
    return new Map(coords.map(point => {
      const value = lookup.get(point.id)
      if (!colorField) return [point.id, '#2f7567']
      if (value === null || value === undefined) return [point.id, '#a9b5ad']
      if (typeof value === 'number') {
        const fraction = (value - min) / (max - min || 1)
        return [point.id, `hsl(${170 - 145 * fraction} 48% 42%)`]
      }
      const palette = ['#2f7567', '#bd7a45', '#6867a5', '#a64b6e', '#6d8141', '#3a78aa']
      const index = Math.abs([...String(value)].reduce((hash, char) => Math.imul(hash, 31) + char.charCodeAt(0) | 0, 0)) % palette.length
      return [point.id, palette[index]]
    }))
  }, [coords, records, colorField])
  useEffect(() => {
    const context = canvas.current?.getContext('2d')
    if (!context) return
    context.clearRect(0, 0, 800, 500)
    context.fillStyle = '#e8ece9'; context.fillRect(0, 0, 800, 500)
    for (const point of coords) { context.fillStyle = colors.get(point.id) ?? '#a9b5ad'; context.beginPath(); context.arc(point.x * transform.scale + transform.dx, point.y * transform.scale + transform.dy, Math.max(2, 3.4 * Math.sqrt(transform.scale)), 0, Math.PI * 2); context.fill() }
  }, [coords, colors, transform])
  function position(event: React.PointerEvent<HTMLCanvasElement>) {
    const bounds = event.currentTarget.getBoundingClientRect()
    return { x: (event.clientX - bounds.left) * 800 / bounds.width, y: (event.clientY - bounds.top) * 500 / bounds.height }
  }
  function end(event: React.PointerEvent<HTMLCanvasElement>) {
    const pos = position(event), start = drag.current
    if (!start) return
    if (start.pan) { drag.current = null; setLasso([]); return }
    if (start.path.length > 4 && start.path.some(point => Math.hypot(start.path[0].x - point.x, start.path[0].y - point.y) > 7)) {
      const polygon = [...start.path, pos]
      const inside = (x: number, y: number) => { let hit = false; for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) { const a = polygon[i], b = polygon[j]; if ((a.y > y) !== (b.y > y) && x < (b.x - a.x) * (y - a.y) / (b.y - a.y) + a.x) hit = !hit } return hit }
      onSelect(coords.filter(point => inside(point.x * transform.scale + transform.dx, point.y * transform.scale + transform.dy)).map(point => point.id))
    } else {
      const nearest = coords.reduce<{ id: string; d: number } | null>((best, point) => { const d = Math.hypot(point.x * transform.scale + transform.dx - pos.x, point.y * transform.scale + transform.dy - pos.y); return !best || d < best.d ? { id: point.id, d } : best }, null)
      if (nearest && nearest.d < 12) onOpen(nearest.id)
    }
    drag.current = null; setLasso([])
  }
  function zoom(factor: number) {
    setTransform(current => { const scale = Math.min(8, Math.max(0.5, current.scale * factor)), ratio = scale / current.scale; return { scale, dx: 400 - (400 - current.dx) * ratio, dy: 250 - (250 - current.dy) * ratio } })
  }
  return <div className="map-wrap"><div className="map-tools"><button className={!panMode ? 'active' : ''} onClick={() => setPanMode(false)}>Lasso</button><button className={panMode ? 'active' : ''} onClick={() => setPanMode(true)}>Pan</button><button aria-label="Zoom in" onClick={() => zoom(1.4)}>＋</button><button aria-label="Zoom out" onClick={() => zoom(1 / 1.4)}>－</button><button onClick={() => setTransform({ scale: 1, dx: 0, dy: 0 })}>Reset view</button></div><div className="map-canvas"><canvas width={800} height={500} ref={canvas} role="img" aria-label={`Projection with ${coords.length} visible records. ${panMode ? 'Drag to pan' : 'Draw a lasso to select'}; click a point to inspect.`} onPointerDown={event => { const p = position(event); drag.current = { ...p, path: [p], pan: panMode || event.shiftKey }; event.currentTarget.setPointerCapture(event.pointerId) }} onPointerMove={event => { const current = drag.current; if (!current) return; const p = position(event); if (current.pan) { setTransform(view => ({ ...view, dx: view.dx + p.x - current.x, dy: view.dy + p.y - current.y })); current.x = p.x; current.y = p.y } else { current.path.push(p); setLasso([...current.path]) } }} onPointerUp={end} onPointerCancel={() => { drag.current = null; setLasso([]) }} />{lasso.length > 1 && <svg className="lasso-overlay" viewBox="0 0 800 500" preserveAspectRatio="none" aria-hidden><polyline points={lasso.map(point => `${point.x},${point.y}`).join(' ')} fill="none" stroke="#2c6c5c" strokeWidth="2" /></svg>}</div><p>{coords.length} plotted of {records.length} loaded records · {artifact.kind} · {artifact.run_id ?? 'published'} · {panMode ? 'drag to pan' : 'draw to select; Shift-drag to pan'}</p><p>Projection population: {artifact.ids.length} {artifact.unit} IDs. Coordinates are fixed by this artifact.{colorField ? ' Gray means missing colour field.' : ''}</p></div>
}

function Workspace({ id, navigate, caps }: { id: string; navigate: (path: string) => void; caps: Capabilities | null }) {
  const [dataset, setDataset] = useState<Dataset | null>(null)
  const [populationScope, setPopulationScope] = useState<'preview' | 'complete'>('preview')
  const [completeInfo, setCompleteInfo] = useState<CompleteScope | null>(null)
  const [fields, setFields] = useState<FieldDescriptor[]>([])
  const [result, setResult] = useState<QueryResult | null>(null)
  const [records, setRecords] = useState<AtlasRecord[]>([])
  const [pageCursors, setPageCursors] = useState<Array<string | null>>([null])
  const [pageIndex, setPageIndex] = useState(0)
  const [artifacts, setArtifacts] = useState<Artifact[]>([])
  const [error, setError] = useState('')
  const [search, setSearch] = useState('')
  const [filterField, setFilterField] = useState('')
  const [filterOp, setFilterOp] = useState('eq')
  const [filterValue, setFilterValue] = useState('')
  const [filterValueType, setFilterValueType] = useState<'number' | 'boolean' | 'string'>('string')
  const [unit, setUnit] = useState<Unit>('example')
  const [sampleMethod, setSampleMethod] = useState('')
  const [sampleSize, setSampleSize] = useState(100)
  const [seed, setSeed] = useState(0)
  const [sortField, setSortField] = useState('')
  const [sortDirection, setSortDirection] = useState('asc')
  const [view, setView] = useState<View>(() => (localStorage.getItem('atlas.view') as View) || 'grid')
  const [cardSize, setCardSize] = useState(() => Number(localStorage.getItem('atlas.card-size')) || 220)
  const [inspected, setInspected] = useState<string | null>(null)
  const [extraRecord, setExtraRecord] = useState<AtlasRecord | null>(null)
  const [selected, setSelected] = useState<string[]>([])
  const [drawer, setDrawer] = useState<Drawer>(null)
  const [projectionId, setProjectionId] = useState('')
  const [colorField, setColorField] = useState('')
  const [selectionName, setSelectionName] = useState('')
  const [saved, setSaved] = useState<Selection | null>(null)
  const [toast, setToast] = useState('')
  const [loading, setLoading] = useState(false)
  const request = useRef(0)
  useEffect(() => { setDataset(null); setPopulationScope('preview'); setCompleteInfo(null); setResult(null); setRecords([]); setFields([]); setArtifacts([]); setError(''); setSearch(''); setFilterField(''); setFilterOp('eq'); setFilterValue(''); setSortField(''); setSampleMethod(''); setSelected([]); setInspected(null); setExtraRecord(null); setDrawer(null); setProjectionId(''); setColorField(''); provider.dataset(id).then(async item => { setDataset(item); setUnit(item.coverage?.unit ?? 'example'); if (canBrowse(item)) { const [loadedFields, loadedArtifacts] = await Promise.all([provider.fields(id), provider.artifacts(id)]); setFields(loadedFields); setArtifacts(loadedArtifacts.filter(artifact => artifact.snapshot_ids.includes(item.snapshot_id ?? ''))) } }).catch(err => setError(String(err))) }, [id])
  async function changeScope(scope: 'preview' | 'complete') {
    if (scope === populationScope) return
    setError('')
    if (scope === 'complete') {
      try { const [info, available] = await Promise.all([provider.completeInfo(id), provider.artifacts(id)]); setCompleteInfo(info); setFields(info.fields); setUnit(info.unit); setFilterField(''); setSortField(''); setSelected([]); setArtifacts(available.filter(item => item.unit === info.unit && item.snapshot_ids.includes(info.snapshot_id) && info.fields.some(field => field.id.startsWith(`prediction.${item.id}.`)))); setPopulationScope('complete') } catch (err) { setError(String(err)) }
    } else if (dataset) {
      try { const [nextFields, nextArtifacts] = await Promise.all([provider.fields(id), provider.artifacts(id)]); setFields(nextFields); setArtifacts(nextArtifacts.filter(item => item.snapshot_ids.includes(dataset.snapshot_id ?? ''))); setUnit(dataset.coverage?.unit ?? 'example'); setFilterField(''); setSortField(''); setSelected([]); setPopulationScope('preview') } catch (err) { setError(String(err)) }
    }
  }
  useEffect(() => { localStorage.setItem('atlas.view', view) }, [view])
  useEffect(() => { localStorage.setItem('atlas.card-size', String(cardSize)) }, [cardSize])
  useEffect(() => { setSaved(null) }, [selected])
  async function refreshResults() {
    if (!dataset) return
    try {
      const [nextFields, nextArtifacts] = await Promise.all([provider.fields(id, populationScope), provider.artifacts(id)])
      setFields(nextFields)
      setArtifacts(nextArtifacts.filter(item => item.snapshot_ids.includes((populationScope === 'complete' ? completeInfo?.snapshot_id : dataset.snapshot_id) ?? '') && (populationScope === 'preview' || nextFields.some(field => field.id.startsWith(`prediction.${item.id}.`)))))
    } catch (err) { setError(String(err)) }
  }
  useEffect(() => { if (view === 'map' && dataset) void refreshResults() }, [view, dataset, id, populationScope, completeInfo])
  const query = useMemo<Query | null>(() => {
    if (!dataset) return null
    const field = fields.find(item => item.id === filterField)
    const parse = (raw: string): unknown => {
      if (field?.dtype === 'category' && field.values?.length && filterOp !== 'in') return field.values[Number(raw)]
      if (field?.dtype === 'category' && field.values?.length && filterOp === 'in') return field.values.find(value => String(value) === raw) ?? raw
      if (filterValueType === 'number') return raw === '' ? null : Number(raw)
      if (filterValueType === 'boolean') return raw === 'true'
      return raw
    }
    let value: unknown = filterOp === 'is_null' ? filterValue !== 'false' : filterOp === 'in' ? filterValue.split(',').map(part => parse(part.trim())) : parse(filterValue)
    const filterReady = filterField && (filterOp === 'is_null' || filterValue.trim() !== '')
    return { snapshot_id: populationScope === 'complete' ? completeInfo?.snapshot_id ?? '' : dataset.snapshot_id ?? '', population_scope: populationScope, result_snapshot_ids: artifacts.filter(item => item.unit === unit).map(item => item.id).sort(), unit, search, filter: filterReady ? { field_id: filterField, op: filterOp, value } : null, sort: sortField ? [{ field_id: sortField, direction: sortDirection }] : [], limit: view === 'map' ? 1000 : 48, sample: sampleMethod ? { method: sampleMethod, size: sampleSize, seed, ...(sampleMethod === 'stratified' ? { field_id: filterField } : {}) } : null }
  }, [dataset, completeInfo, populationScope, artifacts, fields, filterValueType, unit, search, filterField, filterOp, filterValue, sortField, sortDirection, sampleMethod, sampleSize, seed, view])
  useEffect(() => {
    if (!query || !dataset || !canBrowse(dataset)) return
    const current = ++request.current
    setLoading(true); setError(''); setPageCursors([null]); setPageIndex(0)
    const timer = setTimeout(() => provider.query(id, query).then(page => { if (current === request.current) { setResult(page); setRecords(page.records); setLoading(false) } }).catch(err => { if (current === request.current) { setError(String(err)); setLoading(false) } }), 180)
    return () => clearTimeout(timer)
  }, [id, query, dataset])
  async function more() {
    if (!query || !result?.cursor || (view === 'map' && records.length >= 10000)) return
    setLoading(true)
    try { const page = await provider.query(id, { ...query, cursor: result.cursor }); setRecords(rows => view === 'map' ? [...rows, ...page.records] : page.records); setResult(page); if (view !== 'map') { setPageCursors(cursors => [...cursors.slice(0, pageIndex + 1), result.cursor ?? null]); setPageIndex(index => index + 1) } } catch (err) { setError(String(err)) } finally { setLoading(false) }
  }
  async function previous() {
    if (!query || pageIndex < 1) return
    setLoading(true)
    try { const cursor = pageCursors[pageIndex - 1]; const page = await provider.query(id, { ...query, cursor }); setRecords(page.records); setResult(page); setPageIndex(index => index - 1) } catch (err) { setError(String(err)) } finally { setLoading(false) }
  }
  const record = records.find(item => item.id === inspected) ?? (extraRecord?.id === inspected ? extraRecord : undefined)
  async function openRecord(recordId: string) {
    const loaded = records.find(item => item.id === recordId)
    if (loaded) { setExtraRecord(null); setInspected(recordId); return }
    try { const [fetched] = await provider.records([recordId]); setExtraRecord(fetched); setInspected(recordId) } catch (err) { setError(String(err)) }
  }
  const unitFields = fields.filter(field => (field.unit ?? 'example') === unit)
  const projection = artifacts.find(item => item.id === projectionId && item.unit === unit) ?? artifacts.find(item => item.unit === unit && ['projection', 'pca', 'umap'].some(kind => item.kind.toLowerCase().includes(kind)))
  const selectedRecords = records.filter(item => selected.includes(item.id))
  async function save(): Promise<Selection | null> {
    if (!dataset || !selected.length) return null
    const selection: Selection = { id: '', name: selectionName.trim() || `${dataset.name} selection`, ids: selected, unit, snapshot_ids: [query?.snapshot_id ?? ''], dataset_ids: [id], method: sampleMethod || 'manual', seed: sampleMethod ? seed : null, query: query ?? {}, created_at: new Date().toISOString() }
    try { const result = await provider.saveSelection(selection); setSaved(result); setToast(`Saved ${result.ids.length} ${result.unit} IDs.`); return result } catch (err) { setError(String(err)); return null }
  }
  async function exportNow() { if (!saved) { setToast('Save the selection first to export its frozen IDs.'); return } try { await provider.exportSelection(saved) } catch (err) { setError(String(err)) } }
  return <main className="workspace"><header className="workspace-head"><div><button className="text-link" onClick={() => navigate('/')}>← Catalogue</button><h1>{dataset?.name ?? 'Loading dataset…'}</h1></div><div className="head-actions"><span className="mode-badge">{provider.mode === 'static' ? dataset && canBrowse(dataset) ? 'Public preview' : 'Metadata only' : 'Workbench'}</span><button onClick={() => setDrawer('about')}>About</button><button disabled={!caps?.operations.includes('jobs')} title={!caps?.operations.includes('jobs') ? 'Jobs require the local workbench' : undefined} onClick={() => setDrawer('jobs')}>Jobs</button></div></header>
    {error && <div className="notice error" role="alert">{error}</div>}{toast && <div className="notice" role="status">{toast}<button className="icon-btn" aria-label="Dismiss" onClick={() => setToast('')}>×</button></div>}
    {dataset && !canBrowse(dataset) ? <div className="metadata-only"><p className="eyebrow">CATALOGUE RECORD</p><h2>Examples are not available here yet</h2><p>{dataset.description}</p><dl className="field-list"><div><dt>Access</dt><dd>{dataset.coverage?.access ?? 'Unknown'}</dd></div><div><dt>Adapter</dt><dd>{dataset.coverage?.adapter ?? 'Not started'}</dd></div><div><dt>Publication</dt><dd>{dataset.coverage?.publication ?? 'Not reviewed'}</dd></div><div><dt>Complete data</dt><dd>{dataset.coverage?.complete_data ?? 'Unimplemented'}</dd></div></dl>{!!dataset.coverage?.blockers?.length && <><h3>Current blockers</h3><ul>{dataset.coverage.blockers.map((blocker, i) => <li key={i}>{blocker}</li>)}</ul></>}{evidenceUrl(dataset.source_url) && <a href={evidenceUrl(dataset.source_url)!} target="_blank" rel="noopener noreferrer">Original source ↗</a>}</div> : dataset && <><div className="workspace-controls"><label className="search-box"><span className="sr-only">Search records</span><input placeholder="Search records in available population" value={search} onChange={event => setSearch(event.target.value)} /></label><details className="filter-popover"><summary>Filters</summary><div className="filter-fields"><label>Field<select value={filterField} onChange={event => { const chosen = event.target.value; const descriptor = unitFields.find(item => item.id === chosen); const examples = records.map(record => fieldValue(record, chosen)).filter(value => value !== null && value !== undefined); setFilterValueType(descriptor?.dtype === 'number' || (descriptor?.dtype === 'category' && examples.length > 0 && examples.every(value => typeof value === 'number')) ? 'number' : descriptor?.dtype === 'boolean' ? 'boolean' : 'string'); setFilterField(chosen); setFilterOp('eq'); setFilterValue('') }}><option value="">No field filter</option>{unitFields.map(field => <option value={field.id} key={field.id}>{field.name} · {field.namespace}</option>)}</select></label>{filterField && <><label>Operation<select value={filterOp} onChange={event => setFilterOp(event.target.value)}>{(unitFields.find(field => field.id === filterField)?.query_ops ?? ['eq']).map(op => <option key={op}>{op}</option>)}</select></label><label>Value{filterOp !== 'in' && filterOp !== 'is_null' && unitFields.find(item => item.id === filterField)?.dtype === 'category' && unitFields.find(item => item.id === filterField)?.values?.length ? <select aria-label="Filter value" value={filterValue} onChange={event => setFilterValue(event.target.value)}><option value="">Choose a value</option>{unitFields.find(item => item.id === filterField)?.values?.map((value, index) => <option value={String(index)} key={index}>{display(value)} ({typeof value})</option>)}</select> : filterOp === 'is_null' ? <select aria-label="Filter value" value={filterValue || 'true'} onChange={event => setFilterValue(event.target.value)}><option value="true">Is missing</option><option value="false">Is present</option></select> : <input aria-label="Filter value" type={filterValueType === 'number' && filterOp !== 'in' ? 'number' : 'text'} value={filterValue} onChange={event => setFilterValue(event.target.value)} placeholder={filterOp === 'in' ? 'Comma separated' : 'Value'} />}</label></>}</div></details><details className="filter-popover"><summary>Sample</summary><div className="filter-fields"><label>Method<select value={sampleMethod} onChange={event => setSampleMethod(event.target.value)}><option value="">No sample</option><option value="source">Source order</option><option value="random">Seeded random</option><option value="stratified">Stratified by filter field</option></select></label><label>Size<input type="number" min="1" max="10000" value={sampleSize} onChange={event => setSampleSize(Number(event.target.value))} /></label><label>Seed<input type="number" value={seed} onChange={event => setSeed(Number(event.target.value))} /></label><p>Sampling covers {provider.mode === 'static' ? 'this published preview' : 'the queried population'} and saves actual IDs.</p></div></details>{provider.mode === 'workbench' && ['supported', 'requires_preparation'].includes(dataset.coverage?.complete_data ?? '') && <label className="compact-label">Population<select aria-label="Population scope" value={populationScope} onChange={event => void changeScope(event.target.value as 'preview' | 'complete')}><option value="preview">Preview</option><option value="complete">Complete index</option></select></label>}<label className="compact-label">Unit<select aria-label="Unit" value={unit} disabled={populationScope === 'complete'} title={populationScope === 'complete' ? 'The prepared complete index supports this unit only.' : undefined} onChange={event => { setUnit(event.target.value as Unit); setFilterField(''); setSortField(''); setSelected([]) }}>{(populationScope === 'complete' && completeInfo ? [completeInfo.unit] : ['asset', 'example', 'entity', 'conversation'] as Unit[]).map(value => <option key={value}>{value}</option>)}</select></label><div className="segmented" role="group" aria-label="View">{(['grid', 'table', 'map'] as View[]).map(value => <button className={view === value ? 'active' : ''} key={value} onClick={() => setView(value)}>{value[0].toUpperCase() + value.slice(1)}</button>)}</div></div><div className="scope-line"><span><strong>Scope:</strong> {result?.population_scope ?? (provider.mode === 'static' ? 'published preview' : 'dataset')} · {populationScope === 'complete' ? `${completeInfo?.record_count ?? '?'} ${completeInfo?.unit ?? unit} complete index` : `${dataset.coverage?.preview_count ?? 0} ${dataset.coverage?.unit ?? 'example'} preview`} · release {dataset.release ?? 'unresolved'}</span><span>{result?.matched_count ?? '—'} match{result?.matched_count === 1 ? '' : 'es'} · {result?.count_status ?? 'unknown'} count · {records.length} loaded</span></div>{result?.warnings?.map((warning, i) => <div className="notice scope-warning" key={i}>{warning}</div>)}
    <div className="workspace-body"><section className="results" aria-label="Dataset records"><div className="result-toolbar"><span>{loading ? 'Loading…' : `${records.length} loaded`}</span><div>{view === 'grid' && <label className="compact-label">Card size<input aria-label="Card size" type="range" min="170" max="360" value={cardSize} onChange={event => setCardSize(Number(event.target.value))} /></label>}{view === 'table' && <><label className="compact-label">Sort<select value={sortField} onChange={event => setSortField(event.target.value)}><option value="">Source order</option>{unitFields.map(field => <option value={field.id} key={field.id}>{field.name}</option>)}</select></label><button onClick={() => setSortDirection(value => value === 'asc' ? 'desc' : 'asc')} aria-label={`Sort ${sortDirection === 'asc' ? 'descending' : 'ascending'}`}>{sortDirection === 'asc' ? '↑' : '↓'}</button></>}</div></div>
    {view === 'grid' && <div className="record-grid" style={{ gridTemplateColumns: `repeat(auto-fill, minmax(${cardSize}px, 1fr))` }}>{records.map(item => <article className={`record-card ${selected.includes(item.id) ? 'selected' : ''}`} key={item.id}><button className="card-open" onClick={() => setInspected(item.id)} aria-label={`Inspect record ${item.id}`}><RecordPreview record={item} /></button><label className="card-select"><input aria-label={`Select record ${item.id}`} type="checkbox" checked={selected.includes(item.id)} onChange={event => setSelected(ids => event.target.checked ? [...ids, item.id] : ids.filter(id => id !== item.id))} /> Select</label></article>)}</div>}
    {view === 'table' && <div className="table-scroll"><table><thead><tr><th><span className="sr-only">Select</span></th><th>Record</th><th>Question / text</th>{unitFields.slice(0, 5).map(field => <th key={field.id} title={field.description}>{field.name}</th>)}</tr></thead><tbody>{records.map(item => <tr key={item.id}><td><input aria-label={`Select record ${item.id}`} type="checkbox" checked={selected.includes(item.id)} onChange={event => setSelected(ids => event.target.checked ? [...ids, item.id] : ids.filter(id => id !== item.id))} /></td><td><button className="text-link" onClick={() => setInspected(item.id)}>{item.id.slice(-12)}</button></td><td className="table-text">{item.question ?? item.text ?? '—'}</td>{unitFields.slice(0, 5).map(field => <td key={field.id}>{display(fieldValue(item, field.id))}</td>)}</tr>)}</tbody></table></div>}
    {view === 'map' && <><div className="map-controls"><label>Projection<select value={projection?.id ?? ''} onChange={event => setProjectionId(event.target.value)}>{artifacts.filter(item => item.unit === unit && ['projection', 'pca', 'umap'].some(kind => item.kind.toLowerCase().includes(kind))).map(item => <option key={item.id} value={item.id}>{item.kind} · {item.id.slice(-8)}</option>)}</select></label><label>Colour by<select value={colorField} onChange={event => setColorField(event.target.value)}><option value="">One colour</option>{unitFields.map(field => <option value={field.id} key={`${field.unit}:${field.id}`}>{field.name} · {field.namespace}</option>)}</select></label><button onClick={() => void refreshResults()}>Refresh artifacts</button></div>{projection ? <ProjectionMap records={records} artifact={projection} colorField={colorField} onOpen={openRecord} onSelect={ids => { setSelected(current => [...new Set([...current, ...ids])]); setToast(`${ids.length} points added to selection.`) }} /> : <div className="empty"><h2>No projection is available</h2><p>{provider.mode === 'workbench' ? 'Create a projection from an embedding run in Analysis, then return here.' : 'This published pack has no projection artifact.'}</p></div>}</>}
    {!records.length && !loading && <div className="empty">No records match in the available population.</div>}{(pageIndex > 0 || result?.cursor) && <div className="load-more">{view !== 'map' && pageIndex > 0 && <button disabled={loading} onClick={previous}>Previous page</button>}{result?.cursor && (view !== 'map' || records.length < 10000) && <button disabled={loading} onClick={more}>{view === 'map' ? 'Load more points' : 'Next page'}</button>}{view === 'map' && records.length >= 10000 && result?.cursor && <span>Map is limited to 10,000 loaded records; narrow the query to inspect more.</span>}{view !== 'map' && <span>Page {pageIndex + 1}</span>}</div>}</section>{record && <Inspector record={record} fields={fields} artifacts={artifacts} query={query} onOpen={openRecord} close={() => setInspected(null)} />}</div>
    {!!selected.length && <div className="selection-bar"><strong>{selected.length} selected</strong><input aria-label="Selection name" placeholder="Selection name" value={selectionName} onChange={event => setSelectionName(event.target.value)} /><button className="primary" onClick={save}>Save</button><button disabled={!caps?.operations.includes('analysis')} title={!caps?.operations.includes('analysis') ? 'Analysis requires the local workbench' : undefined} onClick={() => setDrawer('analysis')}>Analyze</button><button disabled={!caps?.operations.includes('conversations')} title={!caps?.operations.includes('conversations') ? 'Model connections require the local workbench' : undefined} onClick={() => setDrawer('models')}>Ask model</button><button onClick={() => setDrawer('compare')}>Compare</button><button onClick={exportNow}>Export</button><button onClick={() => setSelected([])}>Clear</button></div>}</>}
    {drawer && <div className="drawer-backdrop" onMouseDown={event => { if (event.target === event.currentTarget) setDrawer(null) }}><aside className="drawer" role="dialog" aria-modal="true" aria-label={`${drawer} drawer`}><div className="panel-heading"><h2>{drawer[0].toUpperCase() + drawer.slice(1)}</h2><button className="icon-btn" aria-label="Close drawer" onClick={() => setDrawer(null)}>×</button></div>{drawer === 'about' && dataset && <div className="drawer-content"><p>{dataset.description}</p><dl className="field-list"><div><dt>Release</dt><dd>{dataset.release ?? 'Unresolved'}</dd></div><div><dt>Snapshot</dt><dd>{dataset.snapshot_id ?? 'Unknown'}</dd></div><div><dt>Access</dt><dd>{dataset.coverage?.access}</dd></div><div><dt>Preview</dt><dd>{dataset.coverage?.preview ?? 'none'} · {dataset.coverage?.preview_count ?? 0} {dataset.coverage?.unit ?? 'example'}s</dd></div><div><dt>Complete data</dt><dd>{dataset.coverage?.complete_data}</dd></div><div><dt>Rights</dt><dd>{display(dataset.rights ?? {})}</dd></div><div><dt>Papers</dt><dd>{(dataset.paper_ids ?? []).join(', ') || 'None linked'}</dd></div></dl>{dataset.coverage?.blockers?.map((blocker, i) => <p className="notice" key={i}>{blocker}</p>)}{evidenceUrl(dataset.source_url) && <a href={evidenceUrl(dataset.source_url)!} target="_blank" rel="noopener noreferrer">Original source ↗</a>}<RelationshipSection relationships={dataset.relationships ?? []} navigate={navigate} /><EvidenceSection evidence={dataset.evidence ?? []} /></div>}{drawer === 'analysis' && <AnalysisDrawer selected={selected} saved={saved} unit={unit} setSaved={setSaved} save={save} />}{drawer === 'jobs' && <JobsDrawer />}{drawer === 'models' && <ModelDrawer selected={selected} recordCount={selectedRecords.length} />}{drawer === 'compare' && <CompareDrawer ids={selected} initialRecords={selectedRecords} fields={unitFields} scope={result?.population_scope ?? 'unknown'} unit={unit} />}{drawer === 'saved' && <SavedDrawer navigate={navigate} />}</aside></div>}
  </main>
}

function AnalysisDrawer({ selected, saved, unit, save }: { selected: string[]; saved: Selection | null; unit: Unit; setSaved: (selection: Selection) => void; save: () => Promise<Selection | null> }) {
  const [processors, setProcessors] = useState<ProcessorDescriptor[]>([])
  const [embeddingArtifacts, setEmbeddingArtifacts] = useState<Artifact[]>([])
  const [processorId, setProcessorId] = useState('')
  const [embeddingId, setEmbeddingId] = useState('')
  const [config, setConfig] = useState('{}')
  const [message, setMessage] = useState('')
  const [estimate, setEstimate] = useState<Record<string, unknown> | null>(null)
  const needsEmbedding = ['project.', 'cluster.', 'outlier.'].some(prefix => processorId.startsWith(prefix))
  const selectedProcessor = processors.find(item => item.id === processorId)
  useEffect(() => { provider.processors().then(setProcessors).catch(err => setMessage(String(err))); provider.artifacts().then(items => setEmbeddingArtifacts(items.filter(item => item.kind.startsWith('embed.')))).catch(err => setMessage(String(err))) }, [])
  useEffect(() => { setEstimate(null) }, [processorId, embeddingId, config, selected, saved])
  function effectiveConfig(): Record<string, unknown> { return { ...JSON.parse(config), ...(needsEmbedding ? { embedding_artifact_id: embeddingId } : {}) } }
  async function previewEstimate() {
    try {
      const frozen = saved ?? await save()
      if (!frozen) throw new Error('The selection could not be saved.')
      const result = await provider.estimateRun(frozen.id, processorId, effectiveConfig())
      setEstimate(result)
      setMessage('Estimate ready. Review the budget, then run this unchanged configuration.')
    } catch (err) { setMessage(String(err)) }
  }
  async function run() {
    try {
      if (!estimate?.estimate_digest || typeof estimate.estimate_digest !== 'string') throw new Error('Preview the run estimate first.')
      const frozen = saved ?? await save()
      if (!frozen) throw new Error('The selection could not be saved.')
      const result = await provider.startRun(frozen.id, processorId, effectiveConfig(), estimate.estimate_digest); setMessage(`Run ${result.id}: ${result.status ?? 'queued'}`)
      setEstimate(null)
    } catch (err) { setMessage(String(err)) }
  }
  return <div className="drawer-content"><p>Input: {selected.length} selected {unit} IDs{saved ? ` · saved as ${saved.name}` : ' · save before running'}</p>{provider.mode === 'static' ? <div className="notice">Computation requires the local workbench. Published artifacts remain available in Grid, Table, and Map.</div> : <><label>Analysis type<select value={processorId} onChange={event => setProcessorId(event.target.value)}><option value="">Choose a processor</option>{processors.map(item => <option disabled={item.available === false || (item.input_units && !item.input_units.includes(unit))} key={item.id} value={item.id}>{item.name ?? item.id}{item.available === false ? ' · unavailable' : item.input_units && !item.input_units.includes(unit) ? ` · requires ${item.input_units.join('/')} unit` : ''}</option>)}</select></label>{selectedProcessor?.reason && <p>{selectedProcessor.reason}</p>}{selectedProcessor?.configured_recipe && <p>Tested local recipe configured for this processor.</p>}{needsEmbedding && <label>Embedding run<select value={embeddingId} onChange={event => setEmbeddingId(event.target.value)}><option value="">Choose an embedding artifact</option>{embeddingArtifacts.filter(item => !saved || item.snapshot_ids.some(snapshot => saved.snapshot_ids.includes(snapshot))).map(item => <option key={item.id} value={item.id}>{item.kind} · {item.id.slice(-8)} · {item.ids.length} {item.unit} IDs</option>)}</select></label>}<details><summary>Advanced configuration</summary><label>Configuration JSON<textarea rows={6} value={config} onChange={event => setConfig(event.target.value)} /></label></details><button disabled={!processorId || !selected.length || (needsEmbedding && !embeddingId)} onClick={previewEstimate}>Estimate resources</button>{estimate && <details open><summary>Resource and coverage estimate</summary><pre>{JSON.stringify(estimate, null, 2)}</pre></details>}<button className="primary" disabled={!estimate?.estimate_digest} onClick={run}>Run analysis</button></>}{message && <div className="notice" role="status">{message}</div>}</div>
}

function JobsDrawer() {
  const [runs, setRuns] = useState<Run[]>([]), [error, setError] = useState('')
  const refresh = () => provider.runs().then(setRuns).catch(err => setError(String(err)))
  useEffect(() => { void refresh() }, [])
  return <div className="drawer-content">{provider.mode === 'static' ? <p>Jobs are available in the local workbench.</p> : <><button onClick={refresh}>Refresh</button>{error && <div className="notice error">{error}</div>}{runs.map(run => <div className="job" key={run.id}><strong>{run.processor_id}</strong><span>{run.status ?? 'queued'}</span><small>{run.id}</small><p>{display(run.progress ?? {})}</p>{['queued', 'running'].includes(run.status ?? '') && <button onClick={() => provider.cancelRun(run.id).then(refresh).catch(err => setError(String(err)))}>Cancel</button>}{!!run.errors?.length && <pre>{JSON.stringify(run.errors, null, 2)}</pre>}</div>)}</>}</div>
}

function ModelDrawer({ selected, recordCount }: { selected: string[]; recordCount: number }) {
  const [providers, setProviders] = useState<Array<{ config: { id: string; model: string; max_images?: number }; capabilities?: Record<string, { status: string }> }>>([])
  const [providerId, setProviderId] = useState(''), [mode, setMode] = useState<'exploration' | 'evaluation'>('exploration')
  const [prompt, setPrompt] = useState(''), [context, setContext] = useState<Record<string, unknown> | null>(null), [response, setResponse] = useState<Record<string, unknown> | null>(null), [error, setError] = useState('')
  const [imageAssets, setImageAssets] = useState<Array<{ id: string; recordId: string; uri: string }>>([]), [imageAssetIds, setImageAssetIds] = useState<string[]>([])
  const [independent, setIndependent] = useState(false), [batchBudget, setBatchBudget] = useState(8192)
  const [history, setHistory] = useState<Record<string, unknown>[]>([]), [savedConversation, setSavedConversation] = useState<Record<string, unknown> | null>(null)
  const [configOpen, setConfigOpen] = useState(false), [configId, setConfigId] = useState(''), [baseUrl, setBaseUrl] = useState('http://127.0.0.1:1234/v1'), [model, setModel] = useState(''), [apiKeyEnv, setApiKeyEnv] = useState(''), [configMessage, setConfigMessage] = useState('')
  const refresh = () => provider.providers().then(items => setProviders(items as typeof providers)).catch(err => setError(String(err)))
  useEffect(() => { void refresh(); provider.conversations().then(setHistory).catch(() => {}) }, [])
  useEffect(() => {
    let active = true
    setImageAssets([]); setImageAssetIds([]); setContext(null)
    if (selected.length) provider.records(selected).then(rows => {
      if (active) setImageAssets(rows.flatMap(row => (row.assets ?? []).filter(asset => asset.modality === 'image' && asset.uri).map(asset => ({ id: asset.id, recordId: row.id, uri: asset.uri! }))))
    }).catch(err => { if (active) setError(String(err)) })
    return () => { active = false }
  }, [selected.join('\u0000')])
  const selectedProvider = providers.find(item => item.config.id === providerId)
  const maxImages = Math.min(8, selectedProvider?.config.max_images ?? 8)
  const requestBody = { provider_id: providerId, record_ids: selected, mode, image_asset_ids: imageAssetIds, independent_records: mode === 'evaluation' && independent }
  const previewDisplay = context ? JSON.stringify(context, (key, value: unknown) => key === 'url' && typeof value === 'string' && value.startsWith('data:image/') ? `[image data URL hidden in display: ${value.length} characters; see SHA-256 and byte count below]` : value, 2) : ''
  async function preview() { try { setError(''); setContext(await provider.previewContext(requestBody)); setResponse(null) } catch (err) { setError(String(err)) } }
  async function send() { try { if (!context?.context_digest) throw new Error('Preview the exact outgoing context first.'); setError(''); setResponse(await provider.converse({ context: requestBody, context_digest: context.context_digest, approved_provider_id: providerId, approved_record_ids: selected, prompt, ...(requestBody.independent_records ? { max_batch_completion_tokens: batchBudget } : {}) })); provider.conversations().then(setHistory).catch(() => {}) } catch (err) { setError(String(err)) } }
  async function add() { try { setConfigMessage(''); await provider.addProvider({ id: configId, base_url: baseUrl, model, ...(apiKeyEnv ? { api_key_env: apiKeyEnv } : {}) }); await refresh(); setProviderId(configId); setConfigMessage('Provider saved. Run the capability probe before using it.'); setConfigOpen(false) } catch (err) { setConfigMessage(String(err)) } }
  async function probe() { try { const result = await provider.probeProvider(providerId); setConfigMessage(`Probe completed: ${JSON.stringify(result)}`); await refresh() } catch (err) { setConfigMessage(String(err)) } }
  return <div className="drawer-content">{provider.mode === 'static' ? <p>Model connections require the local workbench.</p> : <><p>{selected.length} selected IDs · {recordCount} currently loaded. Inspect the transmitted context before sending.</p><label>Provider<select value={providerId} onChange={event => { setProviderId(event.target.value); setContext(null); setImageAssetIds([]) }}><option value="">Choose a provider</option>{providers.map(item => <option key={item.config.id} value={item.config.id}>{item.config.model} · {item.config.id}</option>)}</select></label><div className="button-row"><button onClick={() => setConfigOpen(value => !value)}>{configOpen ? 'Hide configuration' : 'Configure provider'}</button><button disabled={!providerId} onClick={probe}>Probe capabilities</button></div>{configOpen && <div className="config-panel"><label>Connection ID<input value={configId} onChange={event => setConfigId(event.target.value)} placeholder="local-model" /></label><label>OpenAI-compatible base URL<input value={baseUrl} onChange={event => setBaseUrl(event.target.value)} /></label><label>Model<input value={model} onChange={event => setModel(event.target.value)} placeholder="Model identifier" /></label><label>API key environment variable<input value={apiKeyEnv} onChange={event => setApiKeyEnv(event.target.value)} placeholder="Optional variable name" /></label><p>Keep the key in the workbench environment. The capability probe uses synthetic input only.</p><button disabled={!configId || !model} onClick={add}>Save connection</button></div>}{configMessage && <div className="notice" role="status">{configMessage}</div>}<label>Mode<select value={mode} onChange={event => { setMode(event.target.value as typeof mode); setContext(null) }}><option value="exploration">Exploration</option><option value="evaluation">Evaluation</option></select></label>{mode === 'evaluation' && <><label className="checkline"><input type="checkbox" checked={independent} onChange={event => { setIndependent(event.target.checked); setContext(null); setResponse(null) }} /> Evaluate each record independently</label>{independent && <label>Batch completion-token budget<input type="number" min="1" max="100000" value={batchBudget} onChange={event => setBatchBudget(Number(event.target.value))} /></label>}</>}<p>Evaluation excludes gold labels and auxiliary predictions. Source fields are opt in through the context policy. {independent ? 'Each record gets a separate saved input and response.' : 'A joint request discusses the selected records together.'}</p>{imageAssets.length > 0 && <fieldset className="model-images"><legend>Images to send · {imageAssetIds.length} of {maxImages} allowed</legend><p>Images are included only when selected here. The provider's image capability must have passed its probe.</p>{imageAssets.slice(0, 100).map(asset => <label className="model-image-choice" key={asset.id}><input type="checkbox" aria-label={`Include image asset ${asset.id}`} checked={imageAssetIds.includes(asset.id)} disabled={!imageAssetIds.includes(asset.id) && imageAssetIds.length >= maxImages} onChange={event => { setImageAssetIds(ids => event.target.checked ? [...ids, asset.id] : ids.filter(id => id !== asset.id)); setContext(null); setResponse(null) }} /><img src={asset.uri} alt="" loading="lazy" /><span>{asset.recordId}<small>{asset.id}</small></span></label>)}</fieldset>}<button disabled={!providerId || !selected.length || (independent && selected.length > 100)} onClick={preview}>Preview input</button>{context && <details open><summary>Context preview · {display(context.context_digest)}</summary><p>Image data URLs are hidden in this display; the exact bytes are identified by the SHA-256 and byte count below.</p><pre>{previewDisplay}</pre></details>}{context?.external_send_allowed === false && <div className="notice error">{display(context.external_send_reason)}</div>}<label>Message<textarea value={prompt} onChange={event => setPrompt(event.target.value)} rows={5} placeholder="Ask about the selected records" /></label><button className="primary" disabled={!context || context.external_send_allowed !== true || !prompt.trim()} onClick={send}>Send to provider</button>{response && <details open><summary>{response.batch_id ? `Batch ${display(response.status)} · ${((response.completed_record_ids ?? []) as unknown[]).length} completed · ${((response.pending_record_ids ?? []) as unknown[]).length} pending` : 'Response and provenance'}</summary><pre>{JSON.stringify(response, (key, value: unknown) => key === 'url' && typeof value === 'string' && value.startsWith('data:image/') ? `[image data URL hidden in display: ${value.length} characters]` : value, 2)}</pre>{Boolean(response.batch_id) && response.status === 'partial' && <button onClick={send}>Resume pending records</button>}</details>}{history.length > 0 && <details><summary>Saved conversations ({history.length})</summary>{history.slice(0, 20).map(item => <div className="job" key={String(item.id)}><strong>{display(item.model)}</strong><small>{display(item.created_at)} · {display(item.mode)} · {((item.record_ids ?? []) as unknown[]).length} records</small><button onClick={() => provider.conversation(String(item.id)).then(setSavedConversation).catch(err => setError(String(err)))}>View saved input and response</button></div>)}{savedConversation && <details open><summary>Saved input sent and response</summary><pre>{JSON.stringify(savedConversation, (key, value: unknown) => key === 'url' && typeof value === 'string' && value.startsWith('data:image/') ? `[image data URL hidden in display: ${value.length} characters]` : value, 2)}</pre></details>}</details>}{error && <div className="notice error">{error}</div>}</>}</div>
}

function CompareDrawer({ ids, initialRecords, fields, scope, unit }: { ids: string[]; initialRecords: AtlasRecord[]; fields: FieldDescriptor[]; scope: string; unit: Unit }) {
  const [first, setFirst] = useState(''), [second, setSecond] = useState('')
  const [fetched, setFetched] = useState<AtlasRecord[] | null>(null), [error, setError] = useState(''), [loading, setLoading] = useState(true)
  useEffect(() => { setLoading(true); provider.records(ids).then(rows => { setFetched(rows); setLoading(false) }).catch(err => { setError(String(err)); setLoading(false) }) }, [ids])
  const records = fetched ?? initialRecords
  const rows = records.map(item => [fieldValue(item, first), fieldValue(item, second)])
  const complete = rows.filter(([a, b]) => a !== null && a !== undefined && b !== null && b !== undefined)
  const categorical = new Map<string, number>()
  for (const [a, b] of complete) { const key = `${display(a)} × ${display(b)}`; categorical.set(key, (categorical.get(key) ?? 0) + 1) }
  const numeric = complete.filter(([a, b]) => typeof a === 'number' && typeof b === 'number') as number[][]
  const groups = new Map<string, number[]>()
  for (const [group, value] of complete) if (typeof value === 'number' && Number.isFinite(value)) { const key = display(group); groups.set(key, [...(groups.get(key) ?? []), value]) }
  let correlation: number | null = null
  if (numeric.length >= 2) { const ax = numeric.reduce((sum, row) => sum + row[0], 0) / numeric.length, ay = numeric.reduce((sum, row) => sum + row[1], 0) / numeric.length; const cov = numeric.reduce((sum, row) => sum + (row[0] - ax) * (row[1] - ay), 0), sx = Math.sqrt(numeric.reduce((sum, row) => sum + (row[0] - ax) ** 2, 0)), sy = Math.sqrt(numeric.reduce((sum, row) => sum + (row[1] - ay) ** 2, 0)); correlation = sx && sy ? cov / (sx * sy) : null }
  return <div className="drawer-content"><p>Comparing {records.length} of {ids.length} selected {unit} records from {scope}. Missing values are excluded from pairwise results.</p>{loading && <p role="status">Loading all selected records before computing comparisons…</p>}{error && <div className="notice error">Could not retrieve every selected ID: {error}. Results below cover {initialRecords.length} loaded records only.</div>}<label>First field<select value={first} onChange={event => setFirst(event.target.value)}><option value="">Choose field</option>{fields.map(item => <option value={item.id} key={item.id}>{item.name}</option>)}</select></label><label>Second field<select value={second} onChange={event => setSecond(event.target.value)}><option value="">Choose field</option>{fields.map(item => <option value={item.id} key={item.id}>{item.name}</option>)}</select></label>{first && second && !loading && <><p>{complete.length} complete pairs · {rows.length - complete.length} missing pairs.</p>{numeric.length === complete.length && <p>Pearson correlation: {correlation === null ? 'undefined (no variation or insufficient rows)' : correlation.toFixed(3)}</p>}<h3>Cross tabulation</h3><table><thead><tr><th>Pair</th><th>Count</th></tr></thead><tbody>{[...categorical].slice(0, 100).map(([key, count]) => <tr key={key}><td>{key}</td><td>{count}</td></tr>)}</tbody></table>{categorical.size > 100 && <p>Showing 100 of {categorical.size} pairs.</p>}{groups.size > 0 && <><h3>Grouped numeric summary</h3><p>{[...groups.values()].reduce((sum, values) => sum + values.length, 0)} numeric values with both fields present; {rows.length - [...groups.values()].reduce((sum, values) => sum + values.length, 0)} missing or nonnumeric values excluded.</p><table><thead><tr><th>{fields.find(item => item.id === first)?.name ?? 'Group'}</th><th>n</th><th>Mean</th><th>Min</th><th>Max</th></tr></thead><tbody>{[...groups].slice(0, 100).map(([key, values]) => <tr key={key}><td>{key}</td><td>{values.length}</td><td>{(values.reduce((sum, value) => sum + value, 0) / values.length).toFixed(3)}</td><td>{Math.min(...values).toFixed(3)}</td><td>{Math.max(...values).toFixed(3)}</td></tr>)}</tbody></table>{groups.size > 100 && <p>Showing 100 of {groups.size} groups.</p>}</>}</>}</div>
}

function SavedDrawer({ navigate }: { navigate: (path: string) => void }) {
  const [items, setItems] = useState<Selection[]>([])
  const [message, setMessage] = useState('')
  useEffect(() => { provider.selections().then(setItems).catch(err => setMessage(String(err))) }, [])
  async function importFile(file: File) {
    try {
      if (file.size > 64 * 1024 * 1024) throw new Error('Selection exchange exceeds 64 MiB.')
      const selection = await provider.importSelection(JSON.parse(await file.text()))
      setItems(await provider.selections())
      setMessage(`Imported ${selection.ids.length} frozen ${selection.unit} IDs from locally verified records.`)
    } catch (err) { setMessage(String(err)) }
  }
  return <div className="drawer-content">{provider.mode === 'workbench' && <label>Import selection exchange<input type="file" accept="application/json,.json" onChange={event => { const file = event.target.files?.[0]; if (file) void importFile(file); event.target.value = '' }} /><small>The workbench verifies its checksum and resolves IDs against local records.</small></label>}{message && <div className="notice" role="status">{message}</div>}{items.length ? items.map(item => <div className="job" key={item.id}><strong>{item.name}</strong><p>{item.ids.length} {item.unit} IDs · {item.method ?? 'manual'} · {item.dataset_ids.join(', ')}</p><small>{item.created_at}</small><div><button onClick={() => provider.exportSelection(item).catch(err => setMessage(String(err)))}>Export</button><button onClick={() => navigate(`/selection/${item.id}`)}>Open selection</button></div></div>) : <p>No selections saved yet.</p>}</div>
}

function SavedSelectionWorkspace({ id, navigate }: { id: string; navigate: (path: string) => void }) {
  const [selection, setSelection] = useState<Selection | null>(null)
  const [records, setRecords] = useState<AtlasRecord[]>([])
  const [fields, setFields] = useState<FieldDescriptor[]>([])
  const [error, setError] = useState('')
  const [search, setSearch] = useState('')
  const [inspected, setInspected] = useState<string | null>(null)
  const [view, setView] = useState<'grid' | 'table'>('grid')
  useEffect(() => { provider.selections().then(async items => {
    const found = items.find(item => item.id === id)
    if (!found) throw new Error('Saved selection not found.')
    setSelection(found)
    const [rows, descriptors] = await Promise.all([provider.records(found.ids), Promise.all(found.dataset_ids.map(async datasetId => { try { return await provider.fields(datasetId) } catch { return [] } }))])
    setRecords(rows)
    setFields(descriptors.flat())
  }).catch(err => setError(String(err))) }, [id])
  const shown = records.filter(record => [record.text, record.question, JSON.stringify(record.source ?? {})].some(value => String(value ?? '').toLowerCase().includes(search.toLowerCase())))
  return <main className="workspace"><header className="workspace-head"><div><button className="text-link" onClick={() => navigate('/')}>← Catalogue</button><h1>{selection?.name ?? 'Saved selection'}</h1></div><div className="head-actions"><span className="mode-badge">Frozen IDs</span><button disabled={!selection} onClick={() => selection && provider.exportSelection(selection).catch(err => setError(String(err)))}>Export</button></div></header>{error && <div className="notice error">{error}</div>}{selection && <><div className="scope-line"><span>{selection.ids.length} {selection.unit} IDs · {selection.dataset_ids.length} dataset{selection.dataset_ids.length === 1 ? '' : 's'} · {selection.method ?? 'manual'}{selection.seed === null || selection.seed === undefined ? '' : ` · seed ${selection.seed}`}</span><span>Snapshots: {selection.snapshot_ids.join(', ')}</span></div><div className="workspace-controls"><label className="search-box"><span className="sr-only">Search within saved selection</span><input value={search} onChange={event => setSearch(event.target.value)} placeholder="Search saved records" /></label><div className="segmented" role="group" aria-label="View"><button className={view === 'grid' ? 'active' : ''} onClick={() => setView('grid')}>Grid</button><button className={view === 'table' ? 'active' : ''} onClick={() => setView('table')}>Table</button></div></div><div className="workspace-body"><section className="results" aria-label="Saved records"><p className="list-count">{shown.length} shown from {records.length} retrieved IDs</p>{view === 'grid' ? <div className="record-grid">{shown.map(record => <article className="record-card" key={record.id}><button className="card-open" onClick={() => setInspected(record.id)}><RecordPreview record={record} /></button></article>)}</div> : <div className="table-scroll"><table><thead><tr><th>ID</th><th>Dataset</th><th>Text / question</th></tr></thead><tbody>{shown.map(record => <tr key={record.id}><td><button className="text-link" onClick={() => setInspected(record.id)}>{record.id}</button></td><td>{record.dataset_id}</td><td>{record.question ?? record.text ?? '—'}</td></tr>)}</tbody></table></div>}</section>{records.find(record => record.id === inspected) && <Inspector record={records.find(record => record.id === inspected)!} fields={fields} artifacts={[]} close={() => setInspected(null)} />}</div></>}</main>
}

export function App() {
  const [path, navigate] = useRoute()
  const [caps, setCaps] = useState<Capabilities | null>(null)
  const [capError, setCapError] = useState('')
  const [globalDrawer, setGlobalDrawer] = useState(false)
  useEffect(() => { provider.capabilities().then(setCaps).catch(err => setCapError(String(err))) }, [])
  const match = path.match(/^\/dataset\/([^/]+)$/), selectionMatch = path.match(/^\/selection\/([^/]+)$/)
  return <div className="app"><div className="topbar"><button className="brand" onClick={() => navigate('/')} aria-label="Dataset Atlas home"><span className="brand-mark">▦</span> Dataset Atlas</button><div className="topbar-right"><span className="mode-badge">{caps?.mode === 'workbench' ? 'Workbench' : 'Public'}</span><button className="subtle" onClick={() => setGlobalDrawer(true)}>Selections</button></div></div>{capError && <div className="notice error">Capabilities unavailable: {capError}</div>}{match ? <Workspace id={match[1]} navigate={navigate} caps={caps} /> : selectionMatch ? <SavedSelectionWorkspace id={selectionMatch[1]} navigate={navigate} /> : <Catalogue navigate={navigate} openSaved={() => setGlobalDrawer(true)} />}{globalDrawer && <div className="drawer-backdrop" onMouseDown={event => { if (event.target === event.currentTarget) setGlobalDrawer(false) }}><aside className="drawer" role="dialog" aria-modal="true" aria-label="Saved selections"><div className="panel-heading"><h2>Saved selections</h2><button className="icon-btn" aria-label="Close drawer" onClick={() => setGlobalDrawer(false)}>×</button></div><SavedDrawer navigate={path => { navigate(path); setGlobalDrawer(false) }} /></aside></div>}</div>
}
