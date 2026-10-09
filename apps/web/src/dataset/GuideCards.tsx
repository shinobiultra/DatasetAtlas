import { useEffect, useState } from 'react'
import type { Dataset } from '../generated'
import { provider, type GuideEntry, type GuideField } from '../provider'
import { fetchRows, LiveBusyError, type HfPage, type LivePreviewSpec } from '../lib/hfRows'
import { safeUrl, titleCase } from '../lib/format'
import { GUIDE_LABELS as LABELS, GUIDE_TONES as TONES } from '../lib/guideLabels'
import { repositoryUrl } from '../lib/repository'
import { CopyButton, Notice, Spinner, Tag } from '../ui/primitives'

export function useGuide(id: string): GuideEntry | null | undefined {
  const [entry, setEntry] = useState<GuideEntry | null | undefined>(undefined)
  useEffect(() => {
    let live = true
    setEntry(undefined)
    provider.guide(id).then(value => { if (live) setEntry(value) }).catch(() => { if (live) setEntry(null) })
    return () => { live = false }
  }, [id])
  return entry
}

export function GetItCard({ dataset, guide }: { dataset: Dataset; guide: GuideEntry }) {
  const how = guide.how_to_get
  const source = safeUrl(dataset.source_url)
  const repo = repositoryUrl()
  return (
    <div className="card card-pad" style={{ marginTop: 12 }}>
      <div className="row" style={{ gap: 8, marginBottom: 8, flexWrap: 'wrap' }}>
        <h3 style={{ margin: 0 }}>How to get this dataset</h3>
        <Tag tone={TONES[how.state] ?? 'default'}>{LABELS[how.state] ?? titleCase(how.state)}</Tag>
      </div>
      <p style={{ margin: '0 0 10px' }}>{how.summary}</p>
      {source && <p style={{ margin: '0 0 10px' }}><a href={source} target="_blank" rel="noopener noreferrer">Original source</a></p>}
      {!!how.commands?.length && (
        <div className="col" style={{ gap: 8 }}>
          <p className="hint" style={{ margin: 0 }}>
            Install Dataset Atlas and create a workspace once ({repo ? <a href={`${repo}/blob/main/docs/getting-started.md`} target="_blank" rel="noopener noreferrer">getting started</a> : 'see Getting started in the repository'}),
            then run these inside it.
          </p>
          {how.commands.map((command, index) => (
            <div key={command} className="col" style={{ gap: 4 }}>
              <div className="row" style={{ gap: 8, alignItems: 'center' }}>
                <pre className="raw" style={{ margin: 0, flex: 1, overflowX: 'auto' }}><code>{command}</code></pre>
                <CopyButton value={command} label="Copy" />
              </div>
              {how.command_notes?.[index] && <span className="hint">{how.command_notes[index]}</span>}
            </div>
          ))}
        </div>
      )}
      {(how.state === 'fetch_after_terms' || how.state === 'accept_terms') && repo && (
        <p className="hint" style={{ marginTop: 10 }}>
          Access routes for gated releases are listed in the <a href={`${repo}/blob/main/docs/dataset-authorization.md`} target="_blank" rel="noopener noreferrer">authorization guide</a>.
          Dataset Atlas never accepts terms or applies for access on your behalf.
        </p>
      )}
    </div>
  )
}

function fieldValues(field: GuideField): string {
  return field.values?.length ? field.values.map(String).join(', ') : ''
}

export function SchemaCard({ guide }: { guide: GuideEntry }) {
  const schema = guide.schema
  if (!schema) return null
  return (
    <div className="card card-pad" style={{ marginTop: 12 }}>
      <h3 style={{ marginBottom: 6 }}>What a record holds</h3>
      <p className="hint" style={{ marginTop: 0 }}>
        The fields of one record, from a {(schema.preview_count ?? 0).toLocaleString()}-{schema.unit} sample{schema.total_count ? ` of ${schema.total_count.toLocaleString()}` : ''}. No record values are shown here.
      </p>
      <div style={{ overflowX: 'auto' }}>
        <table className="table" style={{ width: '100%', fontSize: 'var(--fs-sm)' }}>
          <thead><tr><th align="left">Field</th><th align="left">Type</th><th align="left">Meaning</th></tr></thead>
          <tbody>
            {schema.fields.map(field => (
              <tr key={field.id}>
                <td className="mono">{field.name}</td>
                <td>{field.dtype}</td>
                <td>{field.description ?? ''}{fieldValues(field) && <span className="hint"> Values: {fieldValues(field)}</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {schema.fields_truncated && <p className="hint">First {schema.fields.length} of {schema.field_count.toLocaleString()} fields shown.</p>}
    </div>
  )
}

const PAGE = 48

/** Rows of a public Hugging Face dataset, read live by the visitor's browser. Nothing here is copied or hosted by this site. */
export function LivePreview({ spec, name }: { spec: LivePreviewSpec; name: string }) {
  const [accepted, setAccepted] = useState(!spec.sensitive)
  const [page, setPage] = useState<HfPage | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const load = (offset: number) => {
    setLoading(true); setError('')
    fetchRows(spec, offset, PAGE)
      .then(next => setPage(current => ({ total: next.total, rows: offset === 0 || !current ? next.rows : [...current.rows, ...next.rows] })))
      .catch(failure => setError(failure instanceof LiveBusyError ? failure.message : failure instanceof Error ? failure.message : 'Could not reach Hugging Face.'))
      .finally(() => setLoading(false))
  }
  useEffect(() => { if (accepted) load(0) /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [accepted, spec.repo, spec.config, spec.split])
  const link = `https://huggingface.co/datasets/${spec.repo}`
  const shown = page?.rows.length ?? 0
  return (
    <div className="card card-pad live-preview">
      <div className="row" style={{ gap: 8, flexWrap: 'wrap', marginBottom: 6 }}>
        <h3 style={{ margin: 0 }}>Live preview</h3>
        <Tag tone="ok">loaded from Hugging Face</Tag>
        {spec.relation === 'public_mirror' && <Tag>public copy</Tag>}
      </div>
      <p className="hint" style={{ margin: '0 0 10px' }}>
        {spec.relation === 'author_release'
          ? <>The authors' own release, <a href={link} target="_blank" rel="noopener noreferrer">{spec.repo}</a>.</>
          : <>A public copy on Hugging Face, <a href={link} target="_blank" rel="noopener noreferrer">{spec.repo}</a>. It is not claimed to be byte-identical to the release a paper used.</>}
        {' '}Your browser fetches these rows from Hugging Face when you open this page; this site stores and serves none of them.
      </p>
      {!accepted ? (
        <div className="col" style={{ gap: 8 }}>
          <Notice tone="warn">This preview {spec.sensitive}. It loads only if you choose to.</Notice>
          <div><button type="button" className="btn primary" onClick={() => setAccepted(true)}>Load the live preview</button></div>
        </div>
      ) : (
        <>
          {error && <Notice tone="error">{error} <button type="button" className="linkish" onClick={() => load(shown)}>Retry</button></Notice>}
          {loading && !page && <Spinner label={`Loading ${name} from Hugging Face…`} />}
          {page && (
            <>
              <div className="live-grid">
                {page.rows.map(row => (
                  <article className="live-card" key={row.index}>
                    {row.media.length > 0 && (
                      <div className="live-media">
                        {row.media.slice(0, 1).map(item => item.kind === 'image'
                          ? <img key={item.src} src={item.src} alt={`Row ${row.index} of ${name}`} loading="lazy" decoding="async" referrerPolicy="no-referrer" />
                          : item.kind === 'audio'
                            ? <audio key={item.src} src={item.src} controls preload="none" />
                            : <video key={item.src} src={item.src} controls preload="none" muted playsInline />)}
                      </div>
                    )}
                    <dl className="live-fields">
                      {row.fields.map(field => <div key={field.name}><dt>{field.name}</dt><dd>{field.text}</dd></div>)}
                    </dl>
                  </article>
                ))}
              </div>
              <div className="row" style={{ gap: 10, marginTop: 12, flexWrap: 'wrap' }}>
                <span className="hint">Showing {shown.toLocaleString()} of {page.total.toLocaleString()} rows · {spec.config} / {spec.split}</span>
                {shown < page.total && <button type="button" className="btn" disabled={loading} onClick={() => load(shown)}>{loading ? 'Loading…' : `Load ${Math.min(PAGE, page.total - shown)} more`}</button>}
              </div>
            </>
          )}
        </>
      )}
    </div>
  )
}

/** What the public site shows for a dataset it hosts no examples of: a live preview when one exists, then how to get it. */
export function StaticUnpublished({ dataset }: { dataset: Dataset }) {
  const guide = useGuide(dataset.id)
  return (
    <>
      {guide?.live_preview
        ? <LivePreview spec={guide.live_preview} name={dataset.name} />
        : <Notice tone="warn"><strong>No examples are published here.</strong> This site hosts examples only for datasets whose licence was reviewed.</Notice>}
      {guide && <GetItCard dataset={dataset} guide={guide} />}
      {guide && !guide.live_preview && <SchemaCard guide={guide} />}
    </>
  )
}
