import { displayUrl } from './lib/display'
import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import type { Capabilities, Dataset, Selection } from './generated'
import { provider, type Thumbnails } from './provider'
import { useRoute, type Route } from './lib/router'
import { inEditable, useKey, useStoredState } from './lib/hooks'
import { matchesTerm } from './catalogue/CataloguePage'
import { CataloguePage } from './catalogue/CataloguePage'
import { DatasetPage } from './dataset/DatasetPage'
import { CollectionsPage } from './pages/CollectionsPage'
import { RunsPage } from './pages/RunsPage'
import { SettingsPage } from './pages/SettingsPage'
import { coverageLine } from './lib/format'
import { Notice } from './ui/primitives'
import * as Icon from './ui/Icons'

type Toast = { id: number; message: string }

export function App() {
  const [route, navigate] = useRoute()
  const [capabilities, setCapabilities] = useState<Capabilities | null>(null)
  const [capabilityError, setCapabilityError] = useState('')
  const [datasets, setDatasets] = useState<Dataset[]>([])
  const [thumbs, setThumbs] = useState<Thumbnails>({})
  const [term, setTerm] = useState('')
  const [suggestOpen, setSuggestOpen] = useState(false)
  const [suggestIndex, setSuggestIndex] = useState(0)
  const [toasts, setToasts] = useState<Toast[]>([])
  const [navOpen, setNavOpen] = useStoredState<boolean>('atlas.nav', window.innerWidth > 900)
  const [selectionsKey, setSelectionsKey] = useState(0)
  const [recent, setRecent] = useStoredState<string[]>('atlas.recent', [])
  const searchRef = useRef<HTMLInputElement>(null)
  const toastId = useRef(0)
  // The status bar belongs to the app grid, not to the workspace flex row, so the
  // dataset workspace portals its selection bar into this host.
  const [barHost, setBarHost] = useState<HTMLDivElement | null>(null)

  useEffect(() => {
    provider.capabilities().then(setCapabilities).catch(failure => setCapabilityError(String(failure instanceof Error ? failure.message : failure)))
    provider.datasets().then(setDatasets).catch(() => {})
    provider.thumbnails().then(setThumbs).catch(() => {})
  }, [])

  useEffect(() => {
    if (route.name === 'dataset') setRecent(current => [route.id, ...current.filter(id => id !== route.id)].slice(0, 6))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [route.name === 'dataset' ? route.id : null])

  function toast(message: string) {
    const id = ++toastId.current
    setToasts(current => [...current.slice(-2), { id, message }])
    setTimeout(() => setToasts(current => current.filter(item => item.id !== id)), 6000)
  }

  const onCatalogue = route.name === 'catalogue'
  const suggestions = useMemo(() => {
    if (!term.trim() || onCatalogue) return []
    return datasets.filter(dataset => matchesTerm(dataset, term)).slice(0, 8)
  }, [term, datasets, onCatalogue])

  useKey(event => {
    const shortcut = (event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k'
    if (shortcut) { event.preventDefault(); searchRef.current?.focus(); searchRef.current?.select(); return }
    if (event.key === 'Escape' && suggestOpen) { setSuggestOpen(false); return }
    if (event.key === '/' && !inEditable(event.target) && onCatalogue) { event.preventDefault(); searchRef.current?.focus() }
  }, [suggestOpen, onCatalogue])

  const openDataset = (id: string) => navigate({ name: 'dataset', id, tab: 'samples' })
  const current = route.name === 'dataset' ? route.id : null
  const recentDatasets = recent.map(id => datasets.find(dataset => dataset.id === id)).filter((dataset): dataset is Dataset => Boolean(dataset))

  const navItem = (target: Route, label: string, icon: ReactNode, count?: number) => {
    const isCurrent =
      (target.name === 'catalogue' && (route.name === 'catalogue' || route.name === 'dataset')) ||
      (target.name === 'collections' && (route.name === 'collections' || route.name === 'collection')) ||
      target.name === route.name
    return (
      <button type="button" className="nav-item" aria-current={isCurrent ? 'page' : undefined} onClick={() => navigate(target)} title={label}>
        {icon}
        <span>{label}</span>
        {count !== undefined && <span className="count">{count.toLocaleString()}</span>}
      </button>
    )
  }

  return (
    <div className="app">
      <header className="topbar">
        <button type="button" className="btn ghost icon" onClick={() => setNavOpen(!navOpen)} aria-label={navOpen ? 'Collapse navigation' : 'Expand navigation'} aria-expanded={navOpen}>
          <Icon.Menu size={16} />
        </button>
        <button type="button" className="brand" onClick={() => navigate({ name: 'catalogue' })} aria-label="Dataset Atlas — catalogue">
          <span className="brand-mark"><Icon.Layers size={15} /></span>
          <span className="brand-name">Dataset Atlas</span>
        </button>
        <label className="search" style={{ position: 'relative' }}>
          <Icon.Search />
          <span className="sr-only">Search datasets</span>
          <input
            ref={searchRef} className="input" value={term}
            onChange={event => { setTerm(event.target.value); setSuggestOpen(true); setSuggestIndex(0) }}
            onFocus={() => setSuggestOpen(true)}
            onBlur={() => setTimeout(() => setSuggestOpen(false), 120)}
            onKeyDown={event => {
              if (!suggestions.length) {
                if (event.key === 'Enter' && term.trim()) navigate({ name: 'catalogue' })
                return
              }
              if (event.key === 'ArrowDown') { event.preventDefault(); setSuggestIndex(index => Math.min(suggestions.length - 1, index + 1)) }
              if (event.key === 'ArrowUp') { event.preventDefault(); setSuggestIndex(index => Math.max(0, index - 1)) }
              if (event.key === 'Enter') { event.preventDefault(); const chosen = suggestions[suggestIndex]; if (chosen) { openDataset(chosen.id); setSuggestOpen(false) } }
            }}
            placeholder="Search datasets…"
            aria-autocomplete="list" aria-expanded={suggestOpen && suggestions.length > 0} role="combobox" aria-controls="dataset-suggestions"
          />
          {!term && <span className="kbd-hint kbd">{navigator.platform.toLowerCase().includes('mac') ? '⌘K' : 'Ctrl K'}</span>}
          {suggestOpen && suggestions.length > 0 && (
            <div className="suggest" id="dataset-suggestions" role="listbox">
              {suggestions.map((dataset, index) => {
                const tile = thumbs[dataset.id]?.tiles.find(item => item.kind === 'image') as { uri: string } | undefined
                return (
                  <button
                    key={dataset.id} type="button" role="option" aria-selected={index === suggestIndex} data-active={index === suggestIndex}
                    onMouseDown={event => event.preventDefault()}
                    onClick={() => { openDataset(dataset.id); setSuggestOpen(false) }}
                  >
                    {tile ? <img className="thumb" src={displayUrl(tile.uri)} alt="" /> : <span className="thumb" style={{ display: 'grid', placeItems: 'center' }}><Icon.Database size={14} /></span>}
                    <span className="meta">
                      <strong className="truncate">{dataset.name}</strong>
                      <span className="truncate">{coverageLine(dataset, provider.mode).text}</span>
                    </span>
                  </button>
                )
              })}
            </div>
          )}
        </label>
        <div className="topbar-right">
          <span className={`mode-badge${provider.mode === 'workbench' ? ' workbench' : ''}`} title={provider.mode === 'workbench' ? 'A local workbench serves data, analysis and model connections.' : 'Published catalogue and approved previews; no backend.'}>
            <span className="dot" style={{ background: provider.mode === 'workbench' ? 'var(--ok)' : 'var(--n-400)' }} />
            {provider.mode === 'workbench' ? 'Workbench' : 'Public build'}
          </span>
        </div>
      </header>

      <nav className={`nav${navOpen ? '' : ' collapsed'}`} aria-label="Primary">
        <div className="nav-scroll">
          <div className="nav-group">
            {navItem({ name: 'catalogue' }, 'Datasets', <Icon.Database size={15} />, datasets.length || undefined)}
            {navItem({ name: 'collections' }, 'Collections', <Icon.Folder size={15} />)}
            {navItem({ name: 'runs' }, 'Runs', <Icon.Activity size={15} />)}
          </div>
          {recentDatasets.length > 0 && (
            <div className="nav-group">
              <div className="nav-title">Recent</div>
              {recentDatasets.map(dataset => (
                <button
                  key={dataset.id} type="button" className="nav-item" aria-current={current === dataset.id ? 'page' : undefined}
                  onClick={() => openDataset(dataset.id)} title={dataset.name}
                >
                  <Icon.Image size={14} />
                  <span className="truncate">{dataset.name}</span>
                </button>
              ))}
            </div>
          )}
        </div>
        <div className="nav-foot">
          {navItem({ name: 'settings', section: 'sources' }, 'Settings', <Icon.Gear size={15} />)}
        </div>
      </nav>

      <main className="main">
        {capabilityError && (
          <div style={{ padding: 16, width: '100%' }}>
            <Notice tone="error">Capabilities unavailable: {capabilityError}</Notice>
          </div>
        )}
        {route.name === 'catalogue' && <CataloguePage term={term} onOpen={openDataset} />}
        {route.name === 'dataset' && (
          <DatasetPage
            key={route.id} datasetId={route.id} tab={route.tab} thumbs={thumbs[route.id]}
            onTab={tab => navigate({ name: 'dataset', id: route.id, tab })}
            onOpenDataset={openDataset} onToast={toast} barHost={barHost}
            onSelectionSaved={(_selection: Selection) => setSelectionsKey(value => value + 1)}
          />
        )}
        {(route.name === 'collections' || route.name === 'collection') && (
          <CollectionsPage
            openId={route.name === 'collection' ? route.id : null}
            onOpenCollection={id => navigate(id ? { name: 'collection', id } : { name: 'collections' })}
            onOpenDataset={openDataset} onToast={toast} refreshKey={selectionsKey}
          />
        )}
        {route.name === 'runs' && <RunsPage onToast={toast} />}
        {route.name === 'settings' && (
          <SettingsPage section={route.section} capabilities={capabilities} onSection={section => navigate({ name: 'settings', section })} />
        )}
        {route.name === 'unknown' && (
          <div className="work"><div className="work-scroll"><div className="page">
            <Notice tone="warn">No screen matches <code>{route.path}</code>.</Notice>
            <button type="button" className="btn" style={{ justifySelf: 'start' }} onClick={() => navigate({ name: 'catalogue' })}>Go to the catalogue</button>
          </div></div></div>
        )}
      </main>

      <div className="statusbar-host" ref={setBarHost}>
        {route.name !== 'dataset' && (
          <div className="statusbar">
            <span>{provider.mode === 'workbench' ? 'Local workbench' : 'Public build'}</span>
            <span className="sep">·</span>
            <span>{datasets.length.toLocaleString()} catalogue entries</span>
            <span className="spacer" />
            <span style={{ fontSize: 'var(--fs-xs)' }}><span className="kbd">{navigator.platform.toLowerCase().includes('mac') ? '⌘K' : 'Ctrl K'}</span> search datasets</span>
          </div>
        )}
      </div>

      {toasts.length > 0 && (
        <div className="toasts" role="status" aria-live="polite">
          {toasts.map(item => (
            <div className="toast" key={item.id}>
              <span>{item.message}</span>
              <button type="button" onClick={() => setToasts(current => current.filter(entry => entry.id !== item.id))} aria-label="Dismiss"><Icon.Close size={13} /></button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
