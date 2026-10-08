import { displayUrl } from '../lib/display'
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import type { Artifact, Dataset, FieldDescriptor, Query, Record as AtlasRecord, Selection } from '../generated'
import { provider, type CompleteScope, type ThumbEntry } from '../provider'
import { recordHeadline, titleCase } from '../lib/format'
import { inEditable, useInfiniteSentinel, useKey, usePanelResize, useStoredState } from '../lib/hooks'
import { Chip, Empty, Notice, Popover, Segmented, Spinner, Tabs, Tag } from '../ui/primitives'
import * as Icon from '../ui/Icons'
import { GridView } from './GridView'
import { ColumnPicker, TableView, type Sort } from './TableView'
import { ColourPicker, MapUnavailable, MapView } from './MapView'
import { FocusedInspector } from './FocusedInspector'
import { CompareView } from './CompareView'
import { FilterRail } from './FilterRail'
import { OverviewTab } from './OverviewTab'
import { SampleInspector } from '../panels/SampleInspector'
import { PrepareDataset, PREPARE_EVENT } from '../panels/PrepareDataset'
import { AboutPanel } from '../panels/AboutPanel'
import { AnalyzePanel } from '../panels/AnalyzePanel'
import { ModelPanel } from '../panels/ModelPanel'
import {
  canBrowse, clauseFilter, defaultColumnFields, MAP_MAX_POINTS, MAP_PAGE_SIZE, PAGE_SIZE, projectionArtifacts,
  runLabel, scopeSummary, supportsComplete, useBrowse, type Clause, type PopulationScope, type Unit, type View,
} from './model'

type Panel = 'inspector' | 'about' | 'analyze' | 'model'
type Centre = 'browse' | 'focus' | 'compare'

const SELECT_ALL_LIMIT = 5000

export function DatasetPage({ datasetId, tab, thumbs, onTab, onOpenDataset, onToast, onSelectionSaved, barHost }: {
  datasetId: string
  tab: 'samples' | 'overview'
  thumbs: ThumbEntry | undefined
  onTab: (tab: 'samples' | 'overview') => void
  onOpenDataset: (id: string) => void
  onToast: (message: string) => void
  onSelectionSaved: (selection: Selection) => void
  barHost: HTMLElement | null
}) {
  /* ---------- dataset-level state ---------- */
  const [dataset, setDataset] = useState<Dataset | null>(null)
  const [loadError, setLoadError] = useState('')
  const [fields, setFields] = useState<FieldDescriptor[]>([])
  const [artifacts, setArtifacts] = useState<Artifact[]>([])
  const [selectedResultIds, setSelectedResultIds] = useState<string[]>([])
  const [scope, setScope] = useState<PopulationScope>('preview')
  const [complete, setComplete] = useState<CompleteScope | null>(null)
  const [unit, setUnit] = useState<Unit>('example')

  /* ---------- query state ---------- */
  const [search, setSearch] = useState('')
  const [clauses, setClauses] = useState<Clause[]>([])
  const [sort, setSort] = useState<Sort>(null)
  const [sample, setSample] = useState<{ method: string; size: number; seed: number } | null>(null)

  /* ---------- view state ---------- */
  const [view, setView] = useStoredState<View>('atlas.view', 'grid')
  const [dense, setDense] = useStoredState<boolean>('atlas.dense', false)
  const [cardWidth, setCardWidth] = useStoredState<number>('atlas.card', 248)
  const [columnIds, setColumnIds] = useStoredState<Record<string, string[]>>('atlas.columns', {})
  const [railOpen, setRailOpen] = useStoredState<boolean>('atlas.rail', window.innerWidth > 1080)
  const [centre, setCentre] = useState<Centre>('browse')
  const [focusIndex, setFocusIndex] = useState(0)
  const [comparePair, setComparePair] = useState<[string | null, string | null]>([null, null])

  /* ---------- selection and panels ---------- */
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [inspected, setInspected] = useState<string | null>(null)
  const [extraRecord, setExtraRecord] = useState<AtlasRecord | null>(null)
  const [panel, setPanel] = useState<Panel | null>(null)
  const [savedSelection, setSavedSelection] = useState<Selection | null>(null)
  const [selectionName, setSelectionName] = useState('')
  const [colourFieldId, setColourFieldId] = useState('')
  const [projectionId, setProjectionId] = useState('')
  const [busyMessage, setBusyMessage] = useState('')

  const panelResize = usePanelResize('atlas.panel-width', 372, 300, 720)
  const scrollRef = useRef<HTMLDivElement>(null)
  const searchRef = useRef<HTMLInputElement>(null)
  const scrollMemory = useRef<Record<string, number>>({})

  /* ---------- load dataset ---------- */
  useEffect(() => {
    let live = true
    setDataset(null); setLoadError(''); setFields([]); setArtifacts([]); setComplete(null); setScope('preview')
    setSearch(''); setClauses([]); setSort(null); setSample(null); setSelected(new Set()); setInspected(null)
    setExtraRecord(null); setPanel(null); setCentre('browse'); setComparePair([null, null]); setSavedSelection(null)
    setColourFieldId(''); setProjectionId('')
    setSelectedResultIds([])
    provider.dataset(datasetId).then(async item => {
      if (!live) return
      setDataset(item)
      setUnit((item.coverage?.unit as Unit) ?? 'example')
      if (!canBrowse(item)) return
      if (!(item.coverage?.preview_count ?? 0) && item.availability?.complete_data === 'local') {
        const [info, available] = await Promise.all([provider.completeInfo(datasetId), provider.artifacts(datasetId)])
        if (!live) return
        setComplete(info); setFields(info.fields); setUnit(info.unit as Unit)
        setArtifacts(available.filter(artifact => artifact.unit === info.unit && artifact.snapshot_ids.includes(info.snapshot_id)))
        setScope('complete')
        return
      }
      const [loadedFields, loadedArtifacts] = await Promise.all([provider.fields(datasetId), provider.artifacts(datasetId)])
      if (!live) return
      setFields(loadedFields)
      setArtifacts(loadedArtifacts.filter(artifact => artifact.snapshot_ids.includes(item.snapshot_id ?? '')))
    }).catch(failure => { if (live) setLoadError(String(failure instanceof Error ? failure.message : failure)) })
    return () => { live = false }
  }, [datasetId])

  /* ---------- scope switch ---------- */
  const changeScope = useCallback(async (next: PopulationScope) => {
    if (!dataset || next === scope) return
    setBusyMessage(next === 'complete' ? 'Opening the complete index…' : 'Returning to the preview…')
    try {
      if (next === 'complete') {
        const [info, available] = await Promise.all([provider.completeInfo(datasetId), provider.artifacts(datasetId)])
        setComplete(info); setFields(info.fields); setUnit(info.unit as Unit)
        setArtifacts(available.filter(item => item.unit === info.unit && item.snapshot_ids.includes(info.snapshot_id) && info.fields.some(field => field.id.startsWith(`prediction.${item.id}.`))))
      } else {
        const [nextFields, nextArtifacts] = await Promise.all([provider.fields(datasetId), provider.artifacts(datasetId)])
        setFields(nextFields)
        setArtifacts(nextArtifacts.filter(item => item.snapshot_ids.includes(dataset.snapshot_id ?? '')))
        setUnit((dataset.coverage?.unit as Unit) ?? 'example')
      }
      setClauses([]); setSort(null); setSelected(new Set()); setInspected(null); setCentre('browse')
      setSelectedResultIds([]); setColourFieldId('')
      setScope(next)
      setLoadError('')
    } catch (failure) {
      setLoadError(String(failure instanceof Error ? failure.message : failure))
    } finally { setBusyMessage('') }
  }, [dataset, datasetId, scope])

  async function refreshResults() {
    if (!dataset) return
    try {
      const [nextFields, available] = await Promise.all([
        scope === 'complete' ? provider.completeInfo(datasetId).then(info => { setComplete(info); return info.fields }) : provider.fields(datasetId),
        provider.artifacts(datasetId),
      ])
      setFields(nextFields)
      setArtifacts(available.filter(item => item.unit === unit && item.snapshot_ids.includes(snapshotId)))
      onToast('Results refreshed for this population.')
    } catch (failure) { onToast(String(failure instanceof Error ? failure.message : failure)) }
  }

  /* ---------- the query ---------- */
  const snapshotId = scope === 'complete' ? complete?.snapshot_id ?? '' : dataset?.snapshot_id ?? ''
  const resultSnapshotIds = useMemo(() => artifacts.filter(item => item.unit === unit && selectedResultIds.includes(item.id)).map(item => item.id).sort(), [artifacts, unit, selectedResultIds])

  // Attaching every historical run makes unrelated browsing grow without bound.
  // The picker preserves explicit query provenance and the API's 32-run limit;
  // direct inspection and projection selection still have access to every run.
  function toggleResult(id: string, enabled: boolean) {
    if (enabled) {
      if (resultSnapshotIds.length >= 32) return
      setSelectedResultIds(current => [...current, id])
    } else {
      setSelectedResultIds(current => current.filter(value => value !== id))
      setClauses(current => current.filter(clause => !clause.fieldId.startsWith(`prediction.${id}.`)))
      setSort(current => current?.field_id.startsWith(`prediction.${id}.`) ? null : current)
      setColourFieldId(current => current.startsWith(`prediction.${id}.`) ? '' : current)
    }
  }

  const query = useMemo<Query | null>(() => {
    if (!dataset || !snapshotId) return null
    return {
      snapshot_id: snapshotId,
      population_scope: scope,
      result_snapshot_ids: resultSnapshotIds,
      unit,
      search,
      filter: clauseFilter(clauses),
      sort: sort ? [sort] : [],
      limit: view === 'map' ? MAP_PAGE_SIZE : PAGE_SIZE,
      sample: sample ? { method: sample.method, size: sample.size, seed: sample.seed, ...(sample.method === 'stratified' && clauses[0] ? { field_id: clauses[0].fieldId } : {}) } : null,
    }
  }, [dataset, snapshotId, scope, resultSnapshotIds, unit, search, clauses, sort, sample, view])

  const browsable = dataset ? canBrowse(dataset) && (scope === 'complete' || (dataset.coverage?.preview_count ?? 0) > 0) : false
  const browse = useBrowse(datasetId, query, browsable, view === 'map' ? MAP_MAX_POINTS : Infinity)
  const { records, result, loading, loadingMore, hasMore, loadMore } = browse
  const sentinel = useInfiniteSentinel(loadMore, hasMore && !loading && !loadingMore && view !== 'map')

  // A projection is only meaningful over its whole population, so the map keeps
  // pulling pages up to its plotted-point ceiling instead of asking for clicks.
  useEffect(() => {
    if (view === 'map' && hasMore && !loading && !loadingMore) loadMore()
  }, [view, hasMore, loading, loadingMore, loadMore])

  /* ---------- selection helpers ---------- */
  useEffect(() => { setSavedSelection(null) }, [selected])

  const toggle = useCallback((id: string, checked: boolean) => {
    setSelected(current => {
      const next = new Set(current)
      if (checked) next.add(id); else next.delete(id)
      return next
    })
  }, [])

  const inspect = useCallback((id: string) => {
    setInspected(id)
    setPanel('inspector')
    setExtraRecord(current => (current?.id === id ? current : null))
  }, [])

  const openRecordById = useCallback(async (id: string) => {
    if (records.some(record => record.id === id)) { inspect(id); return }
    try {
      const [fetched] = await provider.records([id])
      setExtraRecord(fetched)
      setInspected(id)
      setPanel('inspector')
    } catch (failure) { onToast(String(failure instanceof Error ? failure.message : failure)) }
  }, [records, inspect, onToast])

  const focusRecord = useCallback((id: string) => {
    const index = records.findIndex(record => record.id === id)
    if (index < 0) { void openRecordById(id); return }
    scrollMemory.current[view] = scrollRef.current?.scrollTop ?? 0
    setFocusIndex(index)
    setInspected(id)
    setPanel('inspector')
    setCentre('focus')
  }, [records, view, openRecordById])

  const closeFocus = useCallback(() => {
    setCentre('browse')
    requestAnimationFrame(() => {
      if (scrollRef.current) scrollRef.current.scrollTop = scrollMemory.current[view] ?? 0
    })
  }, [view])

  async function selectAllMatching() {
    if (!query || !result) return
    const total = result.matched_count
    if (total === null) { onToast('The matching count is unknown for this population, so every match cannot be resolved.'); return }
    if (total > SELECT_ALL_LIMIT) { onToast(`${total.toLocaleString()} matches exceed the ${SELECT_ALL_LIMIT.toLocaleString()} selection limit. Narrow the filter or sample first.`); return }
    setBusyMessage(`Resolving ${total.toLocaleString()} matching IDs…`)
    try {
      const ids: string[] = []
      let cursor: string | null | undefined = null
      do {
        const page: { records: AtlasRecord[]; cursor?: string | null } = await provider.query(datasetId, { ...query, limit: 1000, cursor })
        ids.push(...page.records.map(record => record.id))
        cursor = page.cursor
      } while (cursor && ids.length < SELECT_ALL_LIMIT)
      setSelected(new Set(ids))
      onToast(`Selected all ${ids.length.toLocaleString()} matching ${unit} records.`)
    } catch (failure) { onToast(String(failure instanceof Error ? failure.message : failure)) }
    finally { setBusyMessage('') }
  }

  const saveSelection = useCallback(async (): Promise<Selection | null> => {
    if (!dataset || !selected.size) return null
    try {
      const saved = await provider.saveSelection({
        id: '', name: selectionName.trim() || `${dataset.name} — ${selected.size} ${unit}`,
        ids: [...selected], unit, snapshot_ids: [snapshotId], dataset_ids: [datasetId],
        method: sample?.method ?? 'manual', seed: sample ? sample.seed : null,
        query: (query ?? {}) as Record<string, unknown>, created_at: new Date().toISOString(),
      })
      setSavedSelection(saved)
      onSelectionSaved(saved)
      onToast(`Saved ${saved.ids.length.toLocaleString()} frozen ${saved.unit} IDs as “${saved.name}”.`)
      return saved
    } catch (failure) { onToast(String(failure instanceof Error ? failure.message : failure)); return null }
  }, [dataset, selected, selectionName, unit, snapshotId, datasetId, sample, query, onToast, onSelectionSaved])

  /* ---------- derived ---------- */
  const unitFields = useMemo(() => fields.filter(field => (field.unit ?? 'example') === unit && !artifacts.some(item => field.id.startsWith(`prediction.${item.id}.`) && !resultSnapshotIds.includes(item.id))), [fields, unit, artifacts, resultSnapshotIds])
  const chosenColumnIds = columnIds[`${datasetId}:${unit}`]
  const defaultColumns = useMemo(() => defaultColumnFields(unitFields, records).map(field => field.id), [unitFields, records])
  const activeColumnIds = chosenColumnIds ?? defaultColumns
  const columns = useMemo(() => activeColumnIds.map(id => unitFields.find(field => field.id === id)).filter((field): field is FieldDescriptor => Boolean(field)), [activeColumnIds, unitFields])
  const labelFields = useMemo(() => columns.slice(0, 3), [columns])
  const record = records.find(item => item.id === inspected) ?? (extraRecord?.id === inspected ? extraRecord : undefined)
  const projections = useMemo(() => projectionArtifacts(artifacts, unit), [artifacts, unit])
  const projection = projections.find(item => item.id === projectionId) ?? projections[0] ?? null
  const colourField = unitFields.find(field => field.id === colourFieldId) ?? null
  const summary = dataset ? scopeSummary(dataset, scope, complete, result) : null
  const hasImages = records.some(item => (item.assets ?? []).some(asset => asset.modality === 'image' && asset.uri))

  /* ---------- keyboard ---------- */
  useKey(event => {
    if (inEditable(event.target)) return
    if (event.key === '/') { event.preventDefault(); searchRef.current?.focus(); return }
    if (centre !== 'browse') return
    const index = records.findIndex(item => item.id === inspected)
    if (event.key === 'j' || event.key === 'ArrowDown') {
      if (!records.length) return
      event.preventDefault(); inspect(records[Math.min(records.length - 1, index + 1)].id)
    }
    if (event.key === 'k' || event.key === 'ArrowUp') {
      if (!records.length) return
      event.preventDefault(); inspect(records[Math.max(0, index - 1)].id)
    }
    if (event.key === 'Enter' && inspected) { event.preventDefault(); focusRecord(inspected) }
    if (event.key === 'x' && inspected) { event.preventDefault(); toggle(inspected, !selected.has(inspected)) }
    if (event.key === 'Escape') { if (panel) { event.preventDefault(); setPanel(null) } }
  }, [records, inspected, centre, panel, selected, inspect, focusRecord, toggle])

  /* ---------- render ---------- */
  if (loadError && !dataset) {
    return <div className="work"><div className="work-scroll"><div className="page"><Notice tone="error">{loadError}</Notice></div></div></div>
  }
  if (!dataset) {
    return <div className="work"><div className="work-scroll"><div className="page"><Spinner label="Loading dataset…" /></div></div></div>
  }

  const header = (
    <>
      <div className="ds-header">
        <div className="ds-mosaic" aria-hidden>
          {(thumbs?.tiles ?? []).filter(tile => tile.kind === 'image').slice(0, 4).map((tile, index) => (
            <img key={index} src={displayUrl((tile as { uri: string }).uri)} alt="" loading="lazy" onError={event => { event.currentTarget.style.visibility = 'hidden' }} />
          ))}
          {!(thumbs?.tiles ?? []).some(tile => tile.kind === 'image') && <div className="ph" style={{ gridColumn: '1 / -1', gridRow: '1 / -1' }}><Icon.Database size={20} /></div>}
        </div>
        <div className="ds-header-main">
          <h1>{dataset.name}</h1>
          <p className="summary clamp-2">{dataset.description || 'No description recorded for this source yet.'}</p>
          <div className="facts">
            <span>{(dataset.modalities ?? []).map(titleCase).join(' + ') || 'Modality unknown'}</span>
            <span className="sep">·</span>
            <span>{(dataset.tasks ?? []).map(titleCase).join(', ') || 'Task unrecorded'}</span>
            {summary && <><span className="sep">·</span><span>{summary.label}</span></>}
          </div>
        </div>
        <div className="ds-header-actions">
          {artifacts.some(item => item.unit === unit) && (
            <Popover label="Results for browsing" trigger={() => <>Results ({resultSnapshotIds.length})<Icon.ChevronDown size={12} /></>}>
              {() => <div style={{ maxWidth: 360 }}>
                <p className="hint">Choose up to 32 runs for filters, columns and map colours. The inspector and projection selector can access every run.</p>
                <div className="col" style={{ maxHeight: 320, overflow: 'auto', marginTop: 8 }}>
                  {artifacts.filter(item => item.unit === unit).map(item => <label className="facet-opt" key={item.id} title={item.id}>
                    <input type="checkbox" aria-label={`Use result ${item.id}`} checked={resultSnapshotIds.includes(item.id)} disabled={!resultSnapshotIds.includes(item.id) && resultSnapshotIds.length >= 32} onChange={event => toggleResult(item.id, event.target.checked)} />
                    <span>{runLabel(item)}</span>
                  </label>)}
                </div>
              </div>}
            </Popover>
          )}
          {browsable && provider.mode === 'workbench' && <button type="button" className="btn" onClick={() => void refreshResults()}>Refresh results</button>}
          {supportsComplete(dataset) && (
            <Segmented
              label="Population scope" value={scope} onChange={value => void changeScope(value)}
              options={[...((dataset.coverage?.preview_count ?? 0) > 0 || dataset.availability?.complete_data !== 'local' ? [{ value: 'preview' as const, label: 'Preview' }] : []), { value: 'complete', label: 'Complete index' }]}
            />
          )}
          <button type="button" className="btn" aria-pressed={panel === 'about'} onClick={() => setPanel(panel === 'about' ? 'inspector' : 'about')}>
            <Icon.Info size={14} />About dataset
          </button>
        </div>
      </div>
      <div className="ds-tabs">
        <Tabs label="Dataset view" value={tab} onChange={onTab} options={[{ value: 'samples', label: 'Samples' }, { value: 'overview', label: 'Overview' }]} />
        {provider.mode === 'workbench' && <PrepareDataset key={dataset.id} datasetId={dataset.id} onRequest={dataset.availability?.preview === 'on_request'} />}
      </div>
    </>
  )

  if (!browsable) {
    return (
      <>
      <div className="work">
        {header}
        <div className="work-scroll">
          <div className="page">
            {provider.mode === 'workbench' && dataset.availability?.preview === 'on_request' ? (
              <div className="card card-pad">
                <h3 style={{ marginBottom: 6 }}>Preview not fetched on this machine yet</h3>
                <p style={{ margin: '0 0 10px' }}>
                  A {(dataset.availability.upstream_preview_count ?? 0).toLocaleString()}-{dataset.coverage?.unit ?? 'example'} preview is recorded for this dataset.
                  Getting it downloads the records and media from the original source to this workbench; you see the size and the
                  source plan before anything is fetched.
                </p>
                <div className="row">
                  <button type="button" className="btn primary" onClick={() => window.dispatchEvent(new CustomEvent(PREPARE_EVENT, { detail: dataset.id }))}>Get preview</button>
                </div>
              </div>
            ) : (
              <Notice tone="warn">
                <strong>No inspectable examples here yet.</strong> This catalogue entry has no prepared preview
                {provider.mode === 'static' ? ' approved for the public build' : ' in this workbench'}.
              </Notice>
            )}
            <div className="card card-pad">
              <h3 style={{ marginBottom: 10 }}>Why, precisely</h3>
              <dl className="dl">
                <div><dt>Access</dt><dd>{titleCase(dataset.coverage?.access ?? 'unknown')}</dd></div>
                <div><dt>Adapter</dt><dd>{titleCase(dataset.coverage?.adapter ?? 'not started')}</dd></div>
                <div><dt>Complete data</dt><dd>{titleCase(dataset.coverage?.complete_data ?? 'unimplemented')}</dd></div>
                <div><dt>Publication</dt><dd>{titleCase(dataset.coverage?.publication ?? 'not reviewed')}</dd></div>
              </dl>
              {!!dataset.coverage?.blockers?.length && (
                <>
                  <h3 style={{ margin: '14px 0 6px' }}>Recorded blockers</h3>
                  <ul style={{ margin: 0, paddingLeft: 18, fontSize: 'var(--fs-md)', lineHeight: 1.55 }}>
                    {dataset.coverage.blockers.map((blocker, index) => <li key={index}>{blocker}</li>)}
                  </ul>
                </>
              )}
              <p className="hint" style={{ marginTop: 12 }}>
                An unimplemented adapter is an implementation gap in Dataset Atlas, not a restriction imposed by the source.
              </p>
              <div className="row" style={{ marginTop: 12 }}>
                <button type="button" className="btn" onClick={() => setPanel('about')}><Icon.Info size={13} />Open full record</button>
              </div>
            </div>
            <RelatedBrowsable dataset={dataset} onOpenDataset={onOpenDataset} />
          </div>
        </div>
      </div>
      {panel === 'about' && <aside className="ctx" aria-label="About dataset">
        <div className="ctx-head"><h2>{dataset.name}</h2><span className="spacer" /><button type="button" className="btn ghost icon" aria-label="Close panel" onClick={() => setPanel(null)}><Icon.Close size={15} /></button></div>
        <div className="ctx-scroll"><AboutPanel dataset={dataset} onOpenDataset={onOpenDataset} /></div>
      </aside>}
      </>
    )
  }

  const footer = (
    <>
      {hasMore && <div ref={sentinel} style={{ height: 1 }} aria-hidden />}
      <div className="row" style={{ justifyContent: 'center', padding: '16px 0 28px', gap: 10 }}>
        {(loading || loadingMore) && <Spinner label={loading ? 'Loading records…' : 'Loading more…'} />}
        {!loading && !loadingMore && hasMore && <button type="button" className="btn" onClick={loadMore}>Load more</button>}
        {!hasMore && records.length > 0 && (
          <small>
            All {records.length.toLocaleString()} matching {unit} records loaded
            {result?.count_status && result.count_status !== 'exact' ? ` (${result.count_status} count)` : ''}
          </small>
        )}
      </div>
    </>
  )

  const centreContent = () => {
    if (centre === 'focus') {
      return (
        <FocusedInspector
          records={records} index={Math.min(focusIndex, Math.max(0, records.length - 1))} artifacts={artifacts}
          onIndex={index => { setFocusIndex(index); const next = records[index]; if (next) setInspected(next.id) }}
          onClose={closeFocus} onInspect={inspect} matchedCount={result?.matched_count ?? null}
        />
      )
    }
    if (centre === 'compare') {
      return (
        <CompareView
          pair={comparePair} records={records} fields={unitFields} artifacts={artifacts}
          unit={unit} populationScope={result?.population_scope ?? scope}
          onPin={(side, id) => setComparePair(current => (side === 'a' ? [id, current[1]] : [current[0], id]))}
          onAskModel={() => { setSelected(new Set(comparePair.filter((id): id is string => Boolean(id)))); setPanel('model') }}
        />
      )
    }
    if (view === 'map') {
      return projection
        ? (
          <MapView
            artifact={projection} records={records} colourField={colourField} selected={selected}
            onInspect={inspect} onOpen={focusRecord}
            loadingMore={loadingMore || loading}
            matchedCount={result?.matched_count ?? null}
            capped={!hasMore ? false : records.length >= MAP_MAX_POINTS}
            onSelect={(ids, mode) => {
              setSelected(current => (mode === 'add' ? new Set([...current, ...ids]) : new Set(ids)))
              onToast(`${ids.length.toLocaleString()} points ${mode === 'add' ? 'added to' : 'selected in'} the selection.`)
            }}
          />
        )
        : <MapUnavailable workbench={provider.mode === 'workbench'} onOpenAnalyze={() => setPanel('analyze')} />
    }
    return (
      <div className="work-scroll" ref={scrollRef}>
        {browse.error && <div style={{ padding: 16 }}><Notice tone="error">{browse.error}</Notice></div>}
        {!records.length && !loading && !browse.error && (
          <Empty title="No records match" action={clauses.length || search ? <button type="button" className="btn" onClick={() => { setClauses([]); setSearch('') }}>Clear filters</button> : undefined}>
            Nothing in the {result?.population_scope ?? scope} population matches these filters.
          </Empty>
        )}
        {view === 'grid'
          ? <GridView
              records={records} cardWidth={cardWidth} labelFields={labelFields} selected={selected} inspected={inspected}
              onInspect={inspect} onToggle={toggle} onOpen={focusRecord} scrollRef={scrollRef} footer={footer}
            />
          : <TableView
              records={records} columns={columns} showThumbnail={hasImages} showText dense={dense}
              textHeader={records.some(item => item.question) ? 'Question' : 'Text'}
              selected={selected} inspected={inspected} sort={sort}
              onSort={field => setSort(current => (current?.field_id === field.id ? (current.direction === 'asc' ? { field_id: field.id, direction: 'desc' } : null) : { field_id: field.id, direction: 'asc' }))}
              onInspect={inspect} onToggle={toggle} onOpen={focusRecord} scrollRef={scrollRef} footer={footer}
              onToggleAllVisible={checked => setSelected(current => {
                const next = new Set(current)
                for (const item of records) { if (checked) next.add(item.id); else next.delete(item.id) }
                return next
              })}
            />}
      </div>
    )
  }

  const panelTitle: Record<Panel, string> = { inspector: 'Sample', about: 'Dataset', analyze: 'Analyze', model: 'Ask model' }
  const panelLabel: Record<Panel, string> = { inspector: 'Sample inspector', about: 'About dataset', analyze: 'Analysis', model: 'Ask model' }

  return (
    <>
      {railOpen && tab === 'samples' && centre !== 'compare' && (
        <aside className="rail" aria-label="Sample filters">
          <FilterRail
            datasetId={datasetId} fields={unitFields} clauses={clauses} baseQuery={query}
            matchedCount={result?.matched_count ?? null}
            onAdd={clause => setClauses(current => (current.some(item => item.key === clause.key) ? current : [...current, clause]))}
            onRemove={key => setClauses(current => current.filter(item => item.key !== key))}
            onClear={() => setClauses([])}
          />
        </aside>
      )}

      <div className="work">
        {header}

        {tab === 'overview' ? (
          <OverviewTab
            dataset={dataset} fields={unitFields} artifacts={artifacts} query={query} records={records}
            scopeLabel={summary?.label ?? ''} onOpenRecord={inspect} onOpenAbout={() => setPanel('about')}
            onOpenAnalyze={() => setPanel('analyze')} onBrowse={() => onTab('samples')}
          />
        ) : (
          <>
            <div className="toolbar">
              {tab === 'samples' && centre !== 'compare' && (
                <button type="button" className="btn icon" aria-pressed={railOpen} onClick={() => setRailOpen(!railOpen)} aria-label={railOpen ? 'Hide filters' : 'Show filters'}>
                  <Icon.Filter size={15} />
                </button>
              )}
              <label className="search">
                <Icon.Search />
                <span className="sr-only">Search records in this dataset</span>
                <input
                  ref={searchRef} className="input" value={search} onChange={event => setSearch(event.target.value)}
                  placeholder={`Search ${unit} records…`}
                />
                {!search && <span className="kbd-hint kbd">/</span>}
              </label>

              <Popover label="Sampling" align="left" trigger={() => <><Icon.Layers size={14} />{sample ? `${sample.method} ${sample.size}` : 'Sample'}<Icon.ChevronDown size={12} /></>}>
                {close => <SampleForm sample={sample} onApply={next => { setSample(next); close() }} />}
              </Popover>

              {view === 'table' && (
                <Popover label="Columns" trigger={() => <><Icon.Columns size={14} />Columns<Icon.ChevronDown size={12} /></>}>
                  {() => (
                    <ColumnPicker
                      fields={unitFields} chosen={activeColumnIds}
                      onChange={ids => setColumnIds(current => ({ ...current, [`${datasetId}:${unit}`]: ids }))}
                    />
                  )}
                </Popover>
              )}

              {view === 'map' && projections.length > 0 && (
                <>
                  <select className="select" style={{ width: 200 }} value={projection?.id ?? ''} onChange={event => setProjectionId(event.target.value)} aria-label="Projection">
                    {projections.map(item => <option key={item.id} value={item.id}>{item.kind}</option>)}
                  </select>
                  <ColourPicker fields={unitFields} value={colourFieldId} onChange={setColourFieldId} />
                </>
              )}

              <span className="spacer" />

              {view === 'grid' && centre === 'browse' && (
                <label className="row" style={{ gap: 6, fontSize: 'var(--fs-sm)', color: 'var(--text-muted)' }}>
                  Size
                  <input type="range" min={170} max={380} step={2} value={cardWidth} onChange={event => setCardWidth(Number(event.target.value))} aria-label="Card size" style={{ width: 84 }} />
                </label>
              )}
              {view === 'table' && (
                <label className="row" style={{ gap: 6, fontSize: 'var(--fs-sm)', color: 'var(--text-muted)' }}>
                  <input type="checkbox" checked={dense} onChange={event => setDense(event.target.checked)} />
                  Dense
                </label>
              )}

              <Segmented
                label="Workspace view" value={centre === 'compare' ? 'compare' : view}
                onChange={value => {
                  if (value === 'compare') { setCentre('compare'); return }
                  scrollMemory.current[view] = scrollRef.current?.scrollTop ?? 0
                  setCentre('browse'); setView(value as View)
                }}
                options={[
                  { value: 'grid', label: 'Grid', icon: <Icon.Grid size={14} /> },
                  { value: 'table', label: 'Table', icon: <Icon.Rows size={14} /> },
                  { value: 'map', label: 'Map', icon: <Icon.MapIcon size={14} /> },
                  { value: 'compare', label: 'Compare', icon: <Icon.Compare size={14} /> },
                ] as Array<{ value: string; label: string; icon: ReactNode }>}
              />
            </div>

            {(clauses.length > 0 || sample || search) && (
              <div className="chipbar">
                {search && <Chip onRemove={() => setSearch('')}>Text: {search}</Chip>}
                {clauses.map(clause => <Chip key={clause.key} title={clause.label} onRemove={() => setClauses(current => current.filter(item => item.key !== clause.key))}>{clause.label}</Chip>)}
                {sample && <Chip tone="neutral" onRemove={() => setSample(null)}>{titleCase(sample.method)} sample of {sample.size} · seed {sample.seed}</Chip>}
                {(clauses.length > 1 || (clauses.length && (search || sample))) && (
                  <button type="button" className="linkish" style={{ fontSize: 'var(--fs-sm)' }} onClick={() => { setClauses([]); setSearch(''); setSample(null) }}>Clear all</button>
                )}
              </div>
            )}

            <div className="scopeline">
              <strong>{summary?.label}</strong>
              <span className="sep">·</span>
              <span>
                {result?.matched_count === null || result?.matched_count === undefined ? 'count unknown' : `${result.matched_count.toLocaleString()} match${result.matched_count === 1 ? '' : 'es'}`}
                {result?.count_status && result.count_status !== 'exact' ? ` (${result.count_status})` : ''}
              </span>
              <span className="sep">·</span>
              <span>{records.length.toLocaleString()} loaded</span>
              {busyMessage && <><span className="sep">·</span><Spinner label={busyMessage} /></>}
              <Popover label="Scope detail" trigger={() => <><Icon.Info size={13} />Scope</>}>
                {() => (
                  <div style={{ maxWidth: 320, fontSize: 'var(--fs-md)', lineHeight: 1.5 }}>
                    <p>{summary?.detail}</p>
                    {result?.warnings?.map((warning, index) => <p key={index} className="hint" style={{ marginTop: 6 }}>{warning}</p>)}
                    <dl className="dl" style={{ marginTop: 8 }}>
                      <div><dt>Unit</dt><dd>{unit}</dd></div>
                      <div><dt>Snapshot</dt><dd className="mono wrap-any">{snapshotId}</dd></div>
                      <div><dt>Result snapshots</dt><dd>{resultSnapshotIds.length}</dd></div>
                    </dl>
                  </div>
                )}
              </Popover>
              {scope === 'preview' && supportsComplete(dataset) && (
                <button type="button" className="linkish" style={{ fontSize: 'var(--fs-sm)' }} onClick={() => void changeScope('complete')}>Browse the complete index →</button>
              )}
            </div>

            {centreContent()}
          </>
        )}
      </div>

      {panel && (
        <aside className="ctx" aria-label={panelLabel[panel]} style={{ width: panelResize.width }}>
          <div
            className="ctx-resize" role="separator" aria-orientation="vertical" tabIndex={0}
            aria-label="Resize the panel" aria-valuenow={panelResize.width} aria-valuemin={panelResize.min} aria-valuemax={panelResize.max}
            onPointerDown={panelResize.onPointerDown} onKeyDown={panelResize.onKeyDown}
          />
          <div className="ctx-head">
            <div style={{ minWidth: 0 }}>
              <div className="kicker">{panel === 'inspector' ? 'Sample' : panel === 'about' ? 'Dataset' : panel === 'analyze' ? 'Analysis' : 'Model'}</div>
              <h2 className="truncate">
                {panel === 'inspector' ? (record ? recordHeadline(record).slice(0, 60) : 'Nothing inspected') : panel === 'about' ? dataset.name : panelTitle[panel]}
              </h2>
            </div>
            <span className="spacer" />
            <button
              type="button" className="btn ghost icon" aria-label="Close panel"
              onClick={() => setPanel(panel === 'inspector' ? null : 'inspector')}
            >
              <Icon.Close size={15} />
            </button>
          </div>
          <div className="ctx-scroll">
            {panel === 'inspector' && (record
              ? <SampleInspector mediaControls={centre !== 'focus'} record={record} fields={fields} artifacts={artifacts} query={query} datasetId={datasetId} onOpenRecord={openRecordById} onFocus={() => focusRecord(record.id)} />
              : <div className="insp-section"><Empty title="Nothing inspected">Click a card or row to inspect it. Clicking never changes your selection.</Empty></div>)}
            {panel === 'about' && <AboutPanel dataset={dataset} onOpenDataset={onOpenDataset} />}
            {panel === 'analyze' && <AnalyzePanel selected={[...selected]} unit={unit} saved={savedSelection} fields={unitFields} artifacts={artifacts} populationScope={scope} onSave={saveSelection} onRan={onToast} onSelectIds={ids => { setSelected(new Set(ids)); setSavedSelection(null) }} />}
            {panel === 'model' && <ModelPanel selected={[...selected]} unit={unit} snapshotIds={snapshotId ? [snapshotId] : undefined} fields={unitFields} resultSnapshotIds={resultSnapshotIds} onNotice={onToast} />}
          </div>
        </aside>
      )}

      {barHost && createPortal(
        <div className={`statusbar${selected.size ? ' active' : ''}`}>
        {selected.size ? (
          <>
            <span className="count">{selected.size.toLocaleString()} selected</span>
            <input
              className="input" style={{ width: 190, height: 28 }} value={selectionName}
              onChange={event => setSelectionName(event.target.value)} placeholder="Selection name" aria-label="Selection name"
            />
            <button type="button" className="btn sm primary" onClick={() => void saveSelection()}><Icon.Bookmark size={13} />Save</button>
            <button
              type="button" className="btn sm" disabled={selected.size < 2}
              onClick={() => { const [a, b] = [...selected]; setComparePair([a, b]); setCentre('compare') }}
            >
              <Icon.Compare size={13} />Compare
            </button>
            <button type="button" className="btn sm" onClick={() => setPanel('analyze')}><Icon.Sparkle size={13} />Analyze</button>
            <button type="button" className="btn sm" onClick={() => setPanel('model')}><Icon.Chat size={13} />Ask model</button>
            <button
              type="button" className="btn sm"
              onClick={async () => {
                const frozen = savedSelection ?? await saveSelection()
                if (frozen) provider.exportSelection(frozen).catch(failure => onToast(String(failure)))
              }}
            >
              <Icon.Download size={13} />Export
            </button>
            <span className="spacer" />
            {result?.matched_count != null && result.matched_count > selected.size && (
              <button type="button" className="linkish" style={{ fontSize: 'var(--fs-sm)' }} onClick={selectAllMatching}>
                Select all {result.matched_count.toLocaleString()} matching
              </button>
            )}
            <button type="button" className="linkish" style={{ fontSize: 'var(--fs-sm)' }} onClick={() => setSelected(new Set())}>Clear</button>
          </>
        ) : (
          <>
            <span>{dataset.name}</span>
            <span className="sep">·</span>
            <span>{summary?.label}</span>
            <span className="spacer" />
            <span className="row" style={{ gap: 10, fontSize: 'var(--fs-xs)' }}>
              <span><span className="kbd">/</span> search</span>
              <span><span className="kbd">j</span>/<span className="kbd">k</span> move</span>
              <span><span className="kbd">Enter</span> open</span>
              <span><span className="kbd">x</span> select</span>
            </span>
          </>
        )}
        </div>,
        barHost,
      )}
    </>
  )
}

function SampleForm({ sample, onApply }: { sample: { method: string; size: number; seed: number } | null; onApply: (value: { method: string; size: number; seed: number } | null) => void }) {
  const [method, setMethod] = useState(sample?.method ?? 'random')
  const [size, setSize] = useState(sample?.size ?? 100)
  const [seed, setSeed] = useState(sample?.seed ?? 0)
  return (
    <div className="col" style={{ gap: 10, minWidth: 240 }}>
      <div className="field">
        <span className="label">Method</span>
        <select className="select" value={method} onChange={event => setMethod(event.target.value)} aria-label="Sampling method">
          <option value="source">Source order</option>
          <option value="random">Seeded random</option>
          <option value="stratified">Stratified by first filter field</option>
        </select>
      </div>
      <div className="row" style={{ gap: 8 }}>
        <div className="field" style={{ flex: 1 }}>
          <span className="label">Size</span>
          <input className="input" type="number" min={1} max={10000} value={size} onChange={event => setSize(Number(event.target.value))} aria-label="Sample size" />
        </div>
        <div className="field" style={{ flex: 1 }}>
          <span className="label">Seed</span>
          <input className="input" type="number" value={seed} onChange={event => setSeed(Number(event.target.value))} aria-label="Sampling seed" />
        </div>
      </div>
      <p className="hint">The method, size and seed are saved with the selection, and so are the actual chosen IDs. A stratified sample does not estimate population prevalence.</p>
      <div className="row" style={{ gap: 6 }}>
        <button type="button" className="btn primary" onClick={() => onApply({ method, size, seed })}>Apply sample</button>
        {sample && <button type="button" className="btn" onClick={() => onApply(null)}>Remove</button>}
      </div>
    </div>
  )
}

/** Related catalogue entries that do have inspectable examples here. A relation is not an identity claim. */
function RelatedBrowsable({ dataset, onOpenDataset }: { dataset: Dataset; onOpenDataset: (id: string) => void }) {
  const relations = useMemo(() => ((dataset.relationships ?? []) as Array<Record<string, unknown>>)
    .map(item => ({ target: String(item.target_id ?? item.target ?? ''), type: String(item.type ?? 'related').replaceAll('_', ' '), scope: typeof item.scope === 'string' ? item.scope : '' }))
    .filter(item => item.target), [dataset])
  const [catalogue, setCatalogue] = useState<Dataset[]>([])
  useEffect(() => {
    let live = true
    if (relations.length) provider.datasets().then(items => { if (live) setCatalogue(items) }).catch(() => {})
    return () => { live = false }
  }, [relations.length])
  const browsable = relations.flatMap(item => {
    const target = catalogue.find(entry => entry.id === item.target)
    return target && canBrowse(target) ? [{ ...item, target }] : []
  })
  if (!browsable.length) return null
  return (
    <div className="card card-pad" style={{ marginTop: 12 }}>
      <h3 style={{ marginBottom: 6 }}>Related entries you can browse</h3>
      <p className="hint" style={{ marginTop: 0 }}>
        These have real examples here. A family or source relation does not establish that they are the exact release or subset this entry names.
      </p>
      {browsable.map(item => (
        <div key={item.target.id} className="row" style={{ gap: 8, padding: '5px 0', flexWrap: 'wrap', fontSize: 'var(--fs-md)' }}>
          <Tag>{item.type}</Tag>
          <button type="button" className="linkish" onClick={() => onOpenDataset(item.target.id)}>{item.target.name}</button>
          <span className="hint">{(item.target.coverage?.preview_count ?? 0).toLocaleString()} {item.target.coverage?.unit ?? 'example'} preview records</span>
          {item.scope && <span className="hint" style={{ flexBasis: '100%', fontSize: 'var(--fs-sm)' }}>{item.scope}</span>}
        </div>
      ))}
    </div>
  )
}
