import { useEffect, useState } from 'react'
import type { Capabilities, Dataset } from '../generated'
import { provider, type ProcessorDescriptor } from '../provider'
import { compact, titleCase } from '../lib/format'
import { useStoredState } from '../lib/hooks'
import { Empty, Notice, Spinner, Tabs, Tag } from '../ui/primitives'
import * as Icon from '../ui/Icons'

type Section = 'sources' | 'models' | 'storage' | 'appearance'

type ProviderEntry = { config: { id: string; model: string; base_url?: string }; capabilities?: Record<string, { status: string; checked_at?: string }> }

export function SettingsPage({ section, capabilities, onSection }: {
  section: string
  capabilities: Capabilities | null
  onSection: (section: Section) => void
}) {
  const active: Section = (['sources', 'models', 'storage', 'appearance'] as Section[]).includes(section as Section) ? section as Section : 'sources'
  return (
    <div className="work">
      <div className="work-scroll">
        <div className="page">
          <header>
            <div>
              <h1>Settings</h1>
              <p>Data sources, model endpoints, local storage and appearance. These live here, not in every dataset toolbar.</p>
            </div>
          </header>
          <Tabs
            label="Settings section" value={active} onChange={onSection}
            options={[
              { value: 'sources', label: 'Data sources' },
              { value: 'models', label: 'Models' },
              { value: 'storage', label: 'Storage' },
              { value: 'appearance', label: 'Appearance' },
            ]}
          />
          {active === 'sources' && <SourcesSection capabilities={capabilities} />}
          {active === 'models' && <ModelsSection />}
          {active === 'storage' && <StorageSection />}
          {active === 'appearance' && <AppearanceSection />}
        </div>
      </div>
    </div>
  )
}

function SourcesSection({ capabilities }: { capabilities: Capabilities | null }) {
  const [datasets, setDatasets] = useState<Dataset[] | null>(null)
  useEffect(() => { provider.datasets().then(setDatasets).catch(() => setDatasets([])) }, [])
  const all = datasets ?? []
  const withPreview = all.filter(dataset => (dataset.coverage?.preview_count ?? 0) > 0)
  const withComplete = all.filter(dataset => dataset.coverage?.complete_data === 'supported')
  const blocked = all.filter(dataset => (dataset.coverage?.blockers ?? []).length > 0)

  return (
    <>
      <div className="card card-pad">
        <h3 style={{ marginBottom: 10 }}>Deployment</h3>
        <dl className="dl">
          <div><dt>Mode</dt><dd>{provider.mode === 'workbench' ? 'Local workbench (loopback API)' : 'Public static build'}</dd></div>
          <div><dt>API version</dt><dd>{capabilities?.api_version ?? '—'}</dd></div>
          <div><dt>Operations</dt><dd>{(capabilities?.operations ?? []).map(titleCase).join(', ') || '—'}</dd></div>
          {capabilities?.limits && Object.entries(capabilities.limits).map(([key, value]) => (
            <div key={key}><dt>{titleCase(key)}</dt><dd>{value.toLocaleString()}</dd></div>
          ))}
        </dl>
        {provider.mode === 'static' && (
          <Notice tone="quiet">
            The public build reads published files only. It never connects to a local workbench, and it carries no credentials.
          </Notice>
        )}
      </div>

      <div className="card card-pad">
        <h3 style={{ marginBottom: 10 }}>Catalogue coverage</h3>
        {datasets === null ? <Spinner label="Loading…" /> : (
          <>
            <div className="ov-stats">
              <div className="ov-stat"><span className="v">{compact(all.length)}</span><span className="k">catalogue entries</span></div>
              <div className="ov-stat"><span className="v">{compact(withPreview.length)}</span><span className="k">with a local preview</span></div>
              <div className="ov-stat"><span className="v">{compact(withComplete.length)}</span><span className="k">with complete-data access</span></div>
              <div className="ov-stat"><span className="v">{compact(all.length - withPreview.length)}</span><span className="k">metadata only</span></div>
            </div>
            <p className="hint">
              A metadata-only entry is a resolved catalogue record with no prepared adapter. That is an implementation gap in Dataset Atlas,
              which is not the same thing as a source that refuses access — {blocked.length.toLocaleString()} entries carry an explicitly recorded blocker.
            </p>
          </>
        )}
      </div>

      <div className="card card-pad">
        <h3 style={{ marginBottom: 10 }}>Source roots</h3>
        <p className="hint">
          Filesystem roots, mounts and remote sources are configured for the workbench process, not from the browser. Media is served only from
          configured roots, and a dataset can never widen that set. Configure them where you run <code>atlas serve</code>.
        </p>
      </div>
    </>
  )
}

function ModelsSection() {
  const [providers, setProviders] = useState<ProviderEntry[] | null>(null)
  const [processors, setProcessors] = useState<ProcessorDescriptor[]>([])
  const [error, setError] = useState('')
  useEffect(() => {
    if (provider.mode !== 'workbench') { setProviders([]); return }
    provider.providers().then(items => setProviders(items as ProviderEntry[])).catch(failure => setError(String(failure)))
    provider.processors().then(setProcessors).catch(() => {})
  }, [])

  if (provider.mode === 'static') {
    return <Notice tone="quiet">Model endpoints are configured in the local workbench. The public build never contacts a model provider.</Notice>
  }

  return (
    <>
      {error && <Notice tone="error">{error}</Notice>}
      <div className="card card-pad">
        <h3 style={{ marginBottom: 10 }}>Configured endpoints</h3>
        {providers === null ? <Spinner label="Loading…" /> : providers.length === 0 ? (
          <Empty title="No endpoint configured">Add an OpenAI-compatible connection from Ask model inside a dataset. Keys stay in the workbench environment.</Empty>
        ) : (
          <div className="listcard">
            {providers.map(entry => (
              <div className="listrow" key={entry.config.id} style={{ gridTemplateColumns: 'minmax(0,1fr) minmax(0,1fr) minmax(0,1.4fr)' }}>
                <span className="stack"><strong className="truncate">{entry.config.id}</strong><small className="truncate">{entry.config.model}</small></span>
                <span className="truncate mono" style={{ fontSize: 'var(--fs-sm)' }}>{entry.config.base_url ?? '—'}</span>
                <span className="row" style={{ gap: 5, flexWrap: 'wrap' }}>
                  {Object.entries(entry.capabilities ?? {}).map(([name, value]) => (
                    <Tag key={name} tone={value.status === 'supported' ? 'ok' : value.status === 'unsupported' ? 'danger' : 'warn'} title={value.checked_at ? `Checked ${value.checked_at}` : undefined}>
                      {titleCase(name)}
                    </Tag>
                  ))}
                  {!Object.keys(entry.capabilities ?? {}).length && <Tag tone="warn">Not probed — every capability is unknown</Tag>}
                </span>
              </div>
            ))}
          </div>
        )}
        <p className="hint">An untested capability is unknown, not supported. Probe a connection before relying on image input or tool calls.</p>
      </div>

      <div className="card card-pad">
        <h3 style={{ marginBottom: 10 }}>Available processors</h3>
        {processors.length === 0 ? <p className="hint">No processors are registered in this installation.</p> : (
          <div className="listcard">
            {processors.map(item => (
              <div className="listrow" key={item.id} style={{ gridTemplateColumns: 'minmax(0,1fr) minmax(0,1.6fr) auto' }}>
                <span className="stack"><strong className="truncate">{item.name ?? item.id}</strong><small className="truncate mono">{item.id}</small></span>
                <span className="truncate"><small>{item.description ?? item.reason ?? '—'}</small></span>
                <Tag tone={item.available === false ? 'warn' : 'ok'}>{item.available === false ? 'Unavailable' : 'Available'}</Tag>
              </div>
            ))}
          </div>
        )}
        <p className="hint">Optional extras (vision, embeddings, projection) install separately; basic browsing needs none of them.</p>
      </div>
    </>
  )
}

function StorageSection() {
  const [cleared, setCleared] = useState('')
  const keys = ['atlas.view', 'atlas.dense', 'atlas.card', 'atlas.columns', 'atlas.rail', 'atlas.catalogue.facets', 'atlas.catalogue.layout', 'atlas.catalogue.sort', 'atlas.starred', 'atlas.notes', 'atlas.nav']
  let localBytes = 0
  try { for (const key of keys) localBytes += (localStorage.getItem(key) ?? '').length } catch { localBytes = -1 }

  return (
    <>
      <div className="card card-pad">
        <h3 style={{ marginBottom: 10 }}>This browser</h3>
        <p className="hint">
          View preferences, starred datasets and notes are stored in this browser only. They never reach the workbench, a provider or a published build.
          {localBytes >= 0 ? ` About ${localBytes.toLocaleString()} characters are stored.` : ' Browser storage is unavailable in this context.'}
        </p>
        <div className="row" style={{ gap: 8 }}>
          <button
            type="button" className="btn"
            onClick={() => { try { for (const key of keys) localStorage.removeItem(key); setCleared('Local preferences cleared. Reload to see defaults.') } catch { setCleared('Browser storage is unavailable.') } }}
          >
            <Icon.Reset size={14} />Clear local preferences
          </button>
        </div>
        {cleared && <Notice tone="quiet">{cleared}</Notice>}
      </div>

      <div className="card card-pad">
        <h3 style={{ marginBottom: 10 }}>Workbench storage</h3>
        <p className="hint">
          Original data, derived artifacts, the job database and the media cache live beside the workbench process under <code>work/</code>, not in this browser.
          Cache budgets, pinning and eviction are managed there. Source data is never modified.
        </p>
      </div>
    </>
  )
}

function AppearanceSection() {
  const safeView = localStorage.getItem('atlas.safe-view') === 'true'
  const [density, setDensity] = useStoredState<boolean>('atlas.dense', false)
  const [cardWidth, setCardWidth] = useStoredState<number>('atlas.card', 248)
  return (
    <div className="card card-pad">
      <h3 style={{ marginBottom: 10 }}>Appearance</h3>
      {provider.mode === 'workbench' ? (
        <>
          <label className="row"><input type="checkbox" checked={safeView} onChange={event => { localStorage.setItem('atlas.safe-view', String(event.target.checked)); window.location.reload() }} />Safe-view image display</label>
          <p className="hint">Pixelated display derivatives served by the local workbench; image URLs it cannot derive are hidden. Originals and analysis/model inputs remain unchanged, and detector boxes are not drawn over derivatives. This is a viewing aid, not a content classifier.</p>
        </>
      ) : (
        <p className="hint">Safe-view display derivatives are produced by the local workbench; the public build serves originals only.</p>
      )}
      <div className="col" style={{ gap: 14 }}>
        <label className="row" style={{ gap: 9 }}>
          <input type="checkbox" checked={density} onChange={event => setDensity(event.target.checked)} />
          <span>Dense table rows by default</span>
        </label>
        <label className="col" style={{ gap: 5 }}>
          <span className="label" style={{ fontSize: 'var(--fs-sm)', fontWeight: 600, color: 'var(--text-muted)' }}>Default grid card width: {cardWidth}px</span>
          <input type="range" min={170} max={380} step={2} value={cardWidth} onChange={event => setCardWidth(Number(event.target.value))} style={{ maxWidth: 320 }} />
        </label>
        <p className="hint">
          The interface follows your system light/dark and reduced-motion preferences. Colour is never the only carrier of state:
          detector outcomes, coverage and access all carry text labels too.
        </p>
      </div>
    </div>
  )
}
