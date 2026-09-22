import { useEffect, useMemo, useState } from 'react'
import type { Dataset } from '../generated'
import { provider, type ThumbEntry, type Thumbnails } from '../provider'
import { accessTone, coverageLine, coverageState, compact, titleCase, COVERAGE_STATE_LABEL, type CoverageState } from '../lib/format'
import { useStoredState } from '../lib/hooks'
import { Empty, Facet, FacetList, FacetOption, Notice, Segmented, Spinner, Tag } from '../ui/primitives'
import * as Icon from '../ui/Icons'

export type Facets = {
  modality: string[]
  task: string[]
  access: string[]
  coverage: string[]
  annotations: boolean
}

export const emptyFacets: Facets = { modality: [], task: [], access: [], coverage: [], annotations: false }

export function facetCount(facets: Facets): number {
  return facets.modality.length + facets.task.length + facets.access.length + facets.coverage.length + (facets.annotations ? 1 : 0)
}

export function matchesTerm(dataset: Dataset, term: string): boolean {
  if (!term) return true
  const haystack = [dataset.name, dataset.id, ...(dataset.aliases ?? []), dataset.description, ...(dataset.tasks ?? []), ...(dataset.labels ?? [])]
    .join(' ').toLocaleLowerCase()
  return term.toLocaleLowerCase().split(/\s+/).filter(Boolean).every(word => haystack.includes(word))
}

function coverageKey(dataset: Dataset): CoverageState {
  return coverageState(dataset, provider.mode)
}

export function passesFacets(dataset: Dataset, facets: Facets): boolean {
  const coverage = dataset.coverage ?? {}
  if (facets.modality.length && !facets.modality.some(value => dataset.modalities?.includes(value))) return false
  if (facets.task.length && !facets.task.some(value => dataset.tasks?.includes(value))) return false
  if (facets.access.length && !facets.access.includes(coverage.access ?? 'unverified')) return false
  if (facets.coverage.length && !facets.coverage.includes(coverageKey(dataset))) return false
  if (facets.annotations && !(dataset.labels?.length)) return false
  return true
}

function Tiles({ entry, name }: { entry: ThumbEntry | undefined; name: string }) {
  const tiles = entry?.tiles ?? []
  if (!tiles.length) {
    return (
      <div className="ds-thumbs">
        <div className="no-thumb"><Icon.Database size={18} /><span>No preview prepared</span></div>
      </div>
    )
  }
  const images = tiles.filter(tile => tile.kind === 'image')
  if (images.length) {
    return (
      <div className={`ds-thumbs n${Math.min(4, images.length)}`}>
        {images.slice(0, 4).map((tile, index) => (
          <img key={index} src={(tile as { uri: string }).uri} alt={index === 0 ? `Example image from ${name}` : ''} loading="lazy" decoding="async"
            onError={event => { event.currentTarget.style.visibility = 'hidden' }} />
        ))}
      </div>
    )
  }
  return (
    <div className={`ds-thumbs n${Math.min(2, tiles.length)}`}>
      {tiles.slice(0, 2).map((tile, index) => <div className="text-thumb" key={index}>{(tile as { text: string }).text}</div>)}
    </div>
  )
}

function DatasetCard({ dataset, thumbs, onOpen, starred, onStar }: {
  dataset: Dataset; thumbs: ThumbEntry | undefined; onOpen: () => void; starred: boolean; onStar: () => void
}) {
  const coverage = coverageLine(dataset, provider.mode)
  const access = dataset.coverage?.access ?? 'unverified'
  return (
    <div className="ds-card" data-dataset-id={dataset.id} style={{ position: 'relative' }}>
      <button
        type="button" className="star" aria-pressed={starred} onClick={onStar}
        aria-label={starred ? `Remove ${dataset.name} from saved datasets` : `Save ${dataset.name} to your datasets`}
      >
        <Icon.Star size={14} filled={starred} />
      </button>
      <button type="button" onClick={onOpen} style={{ all: 'unset', cursor: 'pointer', display: 'flex', flexDirection: 'column', flex: 1 }}>
        <Tiles entry={thumbs} name={dataset.name} />
        <div className="ds-card-body">
          <div className="ds-card-title"><strong>{dataset.name}</strong></div>
          <p className="clamp-2">{dataset.description || 'No description recorded for this source yet.'}</p>
          <div className="tags">
            {(dataset.modalities ?? []).slice(0, 2).map(value => <Tag key={value}>{titleCase(value)}</Tag>)}
            {(dataset.tasks ?? []).slice(0, 2).map(value => <Tag key={value} tone="accent">{titleCase(value)}</Tag>)}
          </div>
          <div className="coverage">
            <Tag tone={accessTone(access)}>{titleCase(access)}</Tag>
            <span className="truncate" title={coverage.text}>{coverage.text}</span>
          </div>
        </div>
      </button>
    </div>
  )
}

export function CataloguePage({ term, onOpen }: { term: string; onOpen: (id: string) => void }) {
  const [datasets, setDatasets] = useState<Dataset[] | null>(null)
  const [thumbs, setThumbs] = useState<Thumbnails>({})
  const [error, setError] = useState('')
  const [filtersOpen, setFiltersOpen] = useState(window.innerWidth > 1080)
  const [facets, setFacets] = useStoredState<Facets>('atlas.catalogue.facets', emptyFacets)
  const [layout, setLayout] = useStoredState<'cards' | 'list'>('atlas.catalogue.layout', 'cards')
  const [sort, setSort] = useStoredState<'relevance' | 'name' | 'coverage'>('atlas.catalogue.sort', 'coverage')
  const [starred, setStarred] = useStoredState<string[]>('atlas.starred', [])

  useEffect(() => {
    provider.datasets().then(setDatasets).catch(error => setError(String(error)))
    provider.thumbnails().then(setThumbs).catch(() => setThumbs({}))
  }, [])

  const all = datasets ?? []
  // Facet counts describe the datasets matching the *other* active facets, so the
  // numbers stay useful while narrowing.
  const searched = useMemo(() => all.filter(dataset => matchesTerm(dataset, term)), [all, term])
  const shown = useMemo(() => {
    const rows = searched.filter(dataset => passesFacets(dataset, facets))
    const order: Record<CoverageState, number> = { full: 0, preview: 1, elsewhere: 2, metadata: 3 }
    const byCoverage = (dataset: Dataset) => order[coverageState(dataset, provider.mode)]
    if (sort === 'name') return [...rows].sort((a, b) => a.name.localeCompare(b.name))
    if (sort === 'coverage') return [...rows].sort((a, b) => byCoverage(a) - byCoverage(b) || a.name.localeCompare(b.name))
    return rows
  }, [searched, facets, sort])

  const counts = useMemo(() => {
    const tally = (pick: (dataset: Dataset) => string[]) => {
      const map = new Map<string, number>()
      for (const dataset of searched) for (const value of pick(dataset)) map.set(value, (map.get(value) ?? 0) + 1)
      return [...map].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    }
    return {
      modality: tally(dataset => dataset.modalities ?? []),
      task: tally(dataset => dataset.tasks ?? []),
      access: tally(dataset => [dataset.coverage?.access ?? 'unverified']),
      coverage: tally(dataset => [coverageKey(dataset)]),
      annotated: searched.filter(dataset => dataset.labels?.length).length,
    }
  }, [searched])

  const toggle = (key: 'modality' | 'task' | 'access' | 'coverage', value: string) => {
    setFacets(current => ({
      ...current,
      [key]: current[key].includes(value) ? current[key].filter(item => item !== value) : [...current[key], value],
    }))
  }

  return (
    <>
      <aside className="rail" aria-label="Catalogue filters" hidden={!filtersOpen}>
        <div className="rail-head">
          <h3>Filters</h3><button type="button" className="btn ghost icon" aria-label="Close catalogue filters" onClick={() => setFiltersOpen(false)}><Icon.Close size={14} /></button>
          {facetCount(facets) > 0 && <button type="button" className="linkish" style={{ marginLeft: 'auto', fontSize: 'var(--fs-sm)' }} onClick={() => setFacets(emptyFacets)}>Reset</button>}
        </div>
        <div className="rail-scroll">
          <Facet title="Browsing coverage">
            {counts.coverage.map(([value, count]) => (
              <FacetOption key={value} checked={facets.coverage.includes(value)} onChange={() => toggle('coverage', value)}
                label={COVERAGE_STATE_LABEL[value as CoverageState] ?? value} count={count} />
            ))}
          </Facet>
          <Facet title="Modality">
            <FacetList items={counts.modality.map(([value]) => ({ key: value }))} render={item => {
              const count = counts.modality.find(entry => entry[0] === item.key)?.[1] ?? 0
              return <FacetOption key={item.key} checked={facets.modality.includes(item.key)} onChange={() => toggle('modality', item.key)} label={titleCase(item.key)} count={count} />
            }} />
          </Facet>
          <Facet title="Task">
            <FacetList items={counts.task.map(([value]) => ({ key: value }))} render={item => {
              const count = counts.task.find(entry => entry[0] === item.key)?.[1] ?? 0
              return <FacetOption key={item.key} checked={facets.task.includes(item.key)} onChange={() => toggle('task', item.key)} label={titleCase(item.key)} count={count} />
            }} />
          </Facet>
          <Facet title="Access" defaultOpen={false}>
            <FacetList items={counts.access.map(([value]) => ({ key: value }))} render={item => {
              const count = counts.access.find(entry => entry[0] === item.key)?.[1] ?? 0
              return <FacetOption key={item.key} checked={facets.access.includes(item.key)} onChange={() => toggle('access', item.key)} label={titleCase(item.key)} count={count} />
            }} />
          </Facet>
          <Facet title="Annotations" defaultOpen={false}>
            <FacetOption checked={facets.annotations} onChange={checked => setFacets(current => ({ ...current, annotations: checked }))}
              label="Has listed labels" count={counts.annotated} />
          </Facet>
        </div>
        <div className="rail-foot">{shown.length.toLocaleString()} of {all.length.toLocaleString()} datasets</div>
      </aside>

      <div className="work">
        <div className="cat-head">
          <div style={{ minWidth: 0 }}>
            <h1>Datasets</h1>
            <p className="sub">
              {datasets === null
                ? 'Loading catalogue…'
                : `${compact(all.length)} catalogue entries · ${compact(all.filter(dataset => ['full', 'preview'].includes(coverageState(dataset, provider.mode))).length)} browsable ${provider.mode === 'static' ? 'in this public build' : 'here'}`}
            </p>
          </div>
          <div className="row" style={{ marginLeft: 'auto' }}>
            <button type="button" className="btn" aria-expanded={filtersOpen} onClick={() => setFiltersOpen(!filtersOpen)}>Filters</button>
            <label className="row" style={{ gap: 6, fontSize: 'var(--fs-sm)', color: 'var(--text-muted)' }}>
              Sort
              <select className="select" style={{ width: 132 }} value={sort} onChange={event => setSort(event.target.value as typeof sort)} aria-label="Sort datasets">
                <option value="coverage">Browsable first</option>
                <option value="name">Name</option>
                <option value="relevance">Catalogue order</option>
              </select>
            </label>
            <Segmented
              label="Catalogue layout" value={layout} onChange={setLayout}
              options={[{ value: 'cards', label: 'Cards', icon: <Icon.Grid size={14} /> }, { value: 'list', label: 'List', icon: <Icon.Rows size={14} /> }]}
            />
          </div>
        </div>

        <div className="work-scroll">
          <div className="cat-body">
            {error && <Notice tone="error">Catalogue unavailable: {error}</Notice>}
            {datasets === null && !error && <Spinner label="Loading catalogue…" />}
            {datasets !== null && !shown.length && (
              <Empty title="No datasets match">
                {term ? `Nothing matches “${term}” with the current filters.` : 'No datasets match the current filters.'}
              </Empty>
            )}
            {layout === 'cards' ? (
              <div className="ds-grid">
                {shown.map(dataset => (
                  <DatasetCard
                    key={dataset.id} dataset={dataset} thumbs={thumbs[dataset.id]}
                    onOpen={() => onOpen(dataset.id)}
                    starred={starred.includes(dataset.id)}
                    onStar={() => setStarred(current => current.includes(dataset.id) ? current.filter(id => id !== dataset.id) : [...current, dataset.id])}
                  />
                ))}
              </div>
            ) : (
              <div className="ds-list">
                {shown.map(dataset => {
                  const tile = thumbs[dataset.id]?.tiles.find(item => item.kind === 'image') as { uri: string } | undefined
                  const coverage = coverageLine(dataset, provider.mode)
                  return (
                    <button type="button" className="ds-row" data-dataset-id={dataset.id} key={dataset.id} onClick={() => onOpen(dataset.id)}>
                      {tile ? <img className="rthumb" src={tile.uri} alt="" loading="lazy" /> : <span className="rthumb ph"><Icon.Database size={14} /></span>}
                      <span style={{ minWidth: 0 }}>
                        <strong className="truncate">{dataset.name}</strong>
                        <small className="truncate">{dataset.description || 'No description recorded.'}</small>
                      </span>
                      <span className="truncate"><small>{(dataset.modalities ?? []).join(' · ') || 'Modality unknown'}</small></span>
                      <span className="truncate"><small>{coverage.text}</small></span>
                      <Icon.ChevronRight size={14} />
                    </button>
                  )
                })}
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  )
}
