import { displayUrl } from '../lib/display'
import { useCallback, useEffect, useMemo, useState } from 'react'
import type { Dataset, FieldDescriptor, Record as AtlasRecord, Selection } from '../generated'
import { provider } from '../provider'
import { relativeTime, recordHeadline, shortId, titleCase } from '../lib/format'
import { useStoredState } from '../lib/hooks'
import { assetUrl, primaryAsset } from '../ui/MediaView'
import { Empty, Notice, Spinner, Tag } from '../ui/primitives'
import { SampleInspector } from '../panels/SampleInspector'
import * as Icon from '../ui/Icons'

/** A collection is a saved dataset list or a saved set of examples. No cloud, no sharing infrastructure. */
export function CollectionsPage({ openId, onOpenCollection, onOpenDataset, onToast, refreshKey }: {
  openId: string | null
  onOpenCollection: (id: string | null) => void
  onOpenDataset: (id: string) => void
  onToast: (message: string) => void
  refreshKey: number
}) {
  const [selections, setSelections] = useState<Selection[] | null>(null)
  const [error, setError] = useState('')
  const [starred, setStarred] = useStoredState<string[]>('atlas.starred', [])
  const [datasets, setDatasets] = useState<Dataset[]>([])

  const load = useCallback(() => {
    provider.selections().then(setSelections).catch(failure => setError(String(failure instanceof Error ? failure.message : failure)))
  }, [])
  useEffect(() => { load(); provider.datasets().then(setDatasets).catch(() => {}) }, [load, refreshKey])

  const open = selections?.find(item => item.id === openId) ?? null
  if (openId && open) {
    return <CollectionDetail selection={open} onBack={() => onOpenCollection(null)} onToast={onToast} />
  }

  return (
    <div className="work">
      <div className="work-scroll">
        <div className="page">
          <header>
            <div>
              <h1>Collections</h1>
              <p>Saved selections freeze the exact record IDs, their unit, snapshot and sampling method. Saved datasets are your own shortlist.</p>
            </div>
            {provider.mode === 'workbench' && (
              <label className="btn" style={{ marginLeft: 'auto', cursor: 'pointer' }}>
                <Icon.Download size={14} />Import exchange
                <input
                  type="file" accept="application/json,.json" style={{ display: 'none' }}
                  onChange={async event => {
                    const file = event.target.files?.[0]
                    event.target.value = ''
                    if (!file) return
                    try {
                      if (file.size > 64 * 1024 * 1024) throw new Error('Selection exchange exceeds 64 MiB.')
                      const imported = await provider.importSelection(JSON.parse(await file.text()))
                      load()
                      onToast(`Imported ${imported.ids.length.toLocaleString()} frozen ${imported.unit} IDs, resolved against local records.`)
                    } catch (failure) { setError(String(failure instanceof Error ? failure.message : failure)) }
                  }}
                />
              </label>
            )}
          </header>
          {error && <Notice tone="error">{error}</Notice>}

          {starred.length > 0 && (
            <section>
              <h3 style={{ marginBottom: 8 }}>Saved datasets ({starred.length})</h3>
              <div className="listcard">
                {starred.map(id => {
                  const dataset = datasets.find(item => item.id === id)
                  return (
                    <div className="listrow" key={id} style={{ gridTemplateColumns: '1fr auto auto' }}>
                      <button type="button" className="linkish truncate" onClick={() => onOpenDataset(id)}>{dataset?.name ?? id}</button>
                      <small>{dataset ? `${(dataset.coverage?.preview_count ?? 0).toLocaleString()} ${dataset.coverage?.unit ?? 'example'} preview` : 'Not in this catalogue'}</small>
                      <button type="button" className="btn sm ghost" onClick={() => setStarred(current => current.filter(item => item !== id))} aria-label={`Remove ${dataset?.name ?? id}`}><Icon.Close size={13} /></button>
                    </div>
                  )
                })}
              </div>
            </section>
          )}

          <section>
            <h3 style={{ marginBottom: 8 }}>Saved selections</h3>
            {selections === null && !error && <Spinner label="Loading selections…" />}
            {selections?.length === 0 && (
              <Empty title="No saved selections">Select records in a dataset and use Save in the selection bar. The IDs are frozen, so the same selection reopens exactly.</Empty>
            )}
            {!!selections?.length && (
              <div className="listcard">
                {selections.map(selection => (
                  <div className="listrow" key={selection.id} style={{ gridTemplateColumns: 'minmax(0,1.6fr) minmax(0,1fr) minmax(0,1fr) auto' }}>
                    <span className="stack">
                      <button type="button" className="linkish truncate" onClick={() => onOpenCollection(selection.id)}>{selection.name || 'Untitled selection'}</button>
                      <small>{relativeTime(selection.created_at)}</small>
                    </span>
                    <span><Tag tone="accent">{selection.ids.length.toLocaleString()} {selection.unit}</Tag></span>
                    <span className="truncate" title={selection.dataset_ids.join(', ')}>
                      <small>{selection.dataset_ids.join(', ')} · {titleCase(selection.method ?? 'manual')}{selection.seed === null || selection.seed === undefined ? '' : ` · seed ${selection.seed}`}</small>
                    </span>
                    <span className="row" style={{ gap: 6 }}>
                      <button type="button" className="btn sm" onClick={() => provider.exportSelection(selection).catch(failure => setError(String(failure)))}><Icon.Download size={13} />Export</button>
                      <button type="button" className="btn sm" onClick={() => onOpenCollection(selection.id)}>Open</button>
                    </span>
                  </div>
                ))}
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  )
}

function CollectionDetail({ selection, onBack, onToast }: { selection: Selection; onBack: () => void; onToast: (message: string) => void }) {
  const [records, setRecords] = useState<AtlasRecord[] | null>(null)
  const [fields, setFields] = useState<FieldDescriptor[]>([])
  const [error, setError] = useState('')
  const [inspected, setInspected] = useState<string | null>(null)
  const [search, setSearch] = useState('')

  useEffect(() => {
    let live = true
    setRecords(null); setError('')
    provider.records(selection.ids, selection.snapshot_ids).then(async rows => {
      const versions = [...new Map(rows.map(record => [`${record.dataset_id}\0${record.snapshot_id}`, record])).values()]
      const descriptors = await Promise.all(versions.map(record => provider.fields(record.dataset_id, 'preview', record.snapshot_id)))
      if (!live) return
      setRecords(rows)
      setFields(descriptors.flat())
    }).catch(failure => { if (live) setError(String(failure instanceof Error ? failure.message : failure)) })
    return () => { live = false }
  }, [selection.id, selection.ids, selection.dataset_ids, selection.snapshot_ids])

  const shown = useMemo(() => {
    const rows = records ?? []
    if (!search) return rows
    const needle = search.toLowerCase()
    return rows.filter(record => recordHeadline(record).toLowerCase().includes(needle) || record.id.toLowerCase().includes(needle))
  }, [records, search])
  const record = shown.find(item => item.id === inspected)

  return (
    <>
      <div className="work">
        <div className="toolbar">
          <button type="button" className="btn" onClick={onBack}><Icon.ChevronLeft size={14} />Collections</button>
          <h2 className="truncate" style={{ fontSize: 'var(--fs-base)' }}>{selection.name || 'Untitled selection'}</h2>
          <label className="search" style={{ maxWidth: 300 }}>
            <Icon.Search />
            <span className="sr-only">Search within this collection</span>
            <input className="input" value={search} onChange={event => setSearch(event.target.value)} placeholder="Search saved records…" />
          </label>
          <span className="spacer" />
          <button type="button" className="btn" onClick={() => provider.exportSelection(selection).then(() => onToast('Exported the frozen IDs and their records.')).catch(failure => setError(String(failure)))}>
            <Icon.Download size={14} />Export
          </button>
        </div>
        <div className="scopeline">
          <strong>{selection.ids.length.toLocaleString()} frozen {selection.unit} IDs</strong>
          <span className="sep">·</span>
          <span>{titleCase(selection.method ?? 'manual')}{selection.seed === null || selection.seed === undefined ? '' : ` · seed ${selection.seed}`}</span>
          <span className="sep">·</span>
          <span className="truncate" title={selection.snapshot_ids.join(', ')}>snapshot {shortId(selection.snapshot_ids[0] ?? '', 22)}</span>
          <span className="sep">·</span>
          <span>{records ? `${records.length.toLocaleString()} resolved` : 'resolving…'}</span>
        </div>
        <div className="work-scroll">
          {error && <div style={{ padding: 16 }}><Notice tone="error">{error}</Notice></div>}
          {records === null && !error && <div style={{ padding: 20 }}><Spinner label="Resolving frozen IDs against local records…" /></div>}
          {records && records.length < selection.ids.length && (
            <div style={{ padding: '12px 16px 0' }}>
              <Notice tone="warn">{(selection.ids.length - records.length).toLocaleString()} saved IDs did not resolve in this deployment. They are still recorded in the selection.</Notice>
            </div>
          )}
          <div className="sample-grid">
            <div className="sample-grid-inner" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(210px, 1fr))' }}>
              {shown.map(item => {
                const asset = primaryAsset(item)
                const url = asset ? assetUrl(asset) : null
                return (
                  <article className="sample-card" key={item.id} data-inspected={inspected === item.id}>
                    <button type="button" className="open" onClick={() => setInspected(item.id)}>
                      <div className="sample-media" style={{ height: 138 }}>
                        {url && asset?.modality === 'image'
                          ? <img src={displayUrl(url)} alt="" loading="lazy" />
                          : <div className="textprev clamp-3">{recordHeadline(item)}</div>}
                      </div>
                      <div className="sample-body"><div className="primary clamp-2">{recordHeadline(item)}</div></div>
                    </button>
                  </article>
                )
              })}
            </div>
          </div>
        </div>
      </div>
      {record && (
        <aside className="ctx" aria-label="Sample panel">
          <div className="ctx-head">
            <div style={{ minWidth: 0 }}>
              <div className="kicker">Sample</div>
              <h2 className="truncate">{recordHeadline(record).slice(0, 60)}</h2>
            </div>
            <span className="spacer" />
            <button type="button" className="btn ghost icon" aria-label="Close panel" onClick={() => setInspected(null)}><Icon.Close size={15} /></button>
          </div>
          <div className="ctx-scroll">
            <SampleInspector
              record={record} fields={fields} artifacts={[]} query={null}
              datasetId={record.dataset_id} onOpenRecord={setInspected} onFocus={() => {}}
            />
          </div>
        </aside>
      )}
    </>
  )
}
