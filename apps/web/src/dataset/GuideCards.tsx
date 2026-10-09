import { useEffect, useState } from 'react'
import type { Dataset } from '../generated'
import { provider, type GuideEntry, type GuideField } from '../provider'
import { safeUrl, titleCase } from '../lib/format'
import { repositoryUrl } from '../lib/repository'
import { CopyButton, Tag } from '../ui/primitives'

const TONES: Record<string, 'ok' | 'warn' | 'default'> = {
  in_site: 'ok', fetch_with_atlas: 'ok', fetch_after_terms: 'warn', accept_terms: 'warn', request_from_authors: 'warn',
  prepared_by_maintainers_only: 'default', public_no_adapter: 'default', unreleased: 'default', source_unverified: 'default',
}
const LABELS: Record<string, string> = {
  in_site: 'Examples on this site', fetch_with_atlas: 'Fetch with Dataset Atlas', fetch_after_terms: 'Accept terms, then fetch',
  prepared_by_maintainers_only: 'Maintainer preview, no public recipe', accept_terms: 'Gated at the source', request_from_authors: 'Request from the authors',
  public_no_adapter: 'Public source, no Atlas recipe yet', unreleased: 'Not released', source_unverified: 'No verified public source',
}

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
  const method = typeof schema.sampling?.method === 'string' ? schema.sampling.method : null
  return (
    <div className="card card-pad" style={{ marginTop: 12 }}>
      <h3 style={{ marginBottom: 6 }}>What a record holds</h3>
      <p className="hint" style={{ marginTop: 0 }}>
        Field names and declared categories of the maintainers' {(schema.preview_count ?? 0).toLocaleString()}-{schema.unit} preview
        {schema.total_count ? ` of ${schema.total_count.toLocaleString()}` : ''}{method ? `, sampled by ${method.replaceAll('_', ' ')}` : ''}.
        No record values are published here.
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

export function PapersCard({ guide }: { guide: GuideEntry }) {
  if (!guide.papers.length) return null
  return (
    <div className="card card-pad" style={{ marginTop: 12 }}>
      <h3 style={{ marginBottom: 6 }}>Named in {guide.papers.length} corpus paper{guide.papers.length === 1 ? '' : 's'}</h3>
      <p className="hint" style={{ marginTop: 0 }}>A mention does not establish which release or subset the paper used.</p>
      <ul style={{ margin: 0, paddingLeft: 18, fontSize: 'var(--fs-md)', lineHeight: 1.55 }}>
        {guide.papers.map(paper => {
          const link = safeUrl(paper.url) ?? (paper.doi ? safeUrl(`https://doi.org/${paper.doi}`) : null)
          const label = `${paper.title ?? paper.paper_id}${paper.year ? ` (${paper.year})` : ''}`
          return <li key={paper.paper_id}>{link ? <a href={link} target="_blank" rel="noopener noreferrer">{label}</a> : label}</li>
        })}
      </ul>
    </div>
  )
}

/** The public build's account of a dataset it holds no examples of; renders nothing in a workbench or before the guide arrives. */
export function NoPreviewGuide({ dataset }: { dataset: Dataset }) {
  const guide = useGuide(dataset.id)
  if (!guide) return null
  return (
    <>
      <GetItCard dataset={dataset} guide={guide} />
      <SchemaCard guide={guide} />
      <PapersCard guide={guide} />
    </>
  )
}
