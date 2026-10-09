import { useEffect, useState } from 'react'
import type { Dataset } from '../generated'
import { provider } from '../provider'
import { display, evidenceText, safeUrl, titleCase } from '../lib/format'
import { Tag } from '../ui/primitives'
import * as Icon from '../ui/Icons'

type Evidence = Record<string, unknown>

function Receipt({ item }: { item: Evidence }) {
  const kind = evidenceText(item.kind) || 'unspecified'
  const paper = evidenceText(item.paper_id)
  const page = evidenceText(item.page)
  const note = evidenceText(item.note) || evidenceText(item.excerpt)
  const checked = evidenceText(item.checked_on) || evidenceText(item.checked_at)
  const link = safeUrl(item.url) ?? safeUrl(item.source_url) ?? (Array.isArray(item.urls) ? item.urls.map(safeUrl).find(Boolean) ?? null : null)
  return (
    <article style={{ border: '1px solid var(--divider)', borderRadius: 'var(--radius-sm)', padding: '8px 10px', display: 'grid', gap: 3, fontSize: 'var(--fs-sm)' }}>
      <strong style={{ fontSize: 'var(--fs-md)' }}>{titleCase(kind)}</strong>
      {paper && <span style={{ color: 'var(--text-muted)' }}>Paper {paper}{page ? ` · p. ${page}` : ''}</span>}
      {link && <a href={link} target="_blank" rel="noopener noreferrer" className="truncate" title={link}>{link}</a>}
      {note && <p className="clamp-2" style={{ color: 'var(--text-muted)' }} title={note}>{note}</p>}
      {checked && <small>Checked {checked}</small>}
      <details className="disclosure" style={{ borderTop: 0 }}>
        <summary style={{ padding: '3px 0', fontSize: 'var(--fs-sm)' }}>Full receipt</summary>
        <div className="body"><pre className="raw">{JSON.stringify(item, null, 2)}</pre></div>
      </details>
    </article>
  )
}

/** Where the previous implementation's metadata belongs: beside the samples, not over them. */
export function AboutPanel({ dataset, onOpenDataset }: { dataset: Dataset; onOpenDataset: (id: string) => void }) {
  const [catalogue, setCatalogue] = useState<Dataset[]>([])
  const relationships = (dataset.relationships ?? []) as Evidence[]
  useEffect(() => { if (relationships.length) provider.datasets().then(setCatalogue).catch(() => {}) }, [relationships.length])

  const evidence = (dataset.evidence ?? []) as Evidence[]
  const sourceEvidence = evidence.filter(item => item.kind !== 'corpus_mention')
  const paperEvidence = evidence.filter(item => item.kind === 'corpus_mention')
  const coverage = dataset.coverage ?? {}
  const source = safeUrl(dataset.source_url)

  return (
    <>
      <div className="insp-section">
        <p style={{ fontSize: 'var(--fs-md)', lineHeight: 1.55 }}>{dataset.description || 'No description recorded for this source yet.'}</p>
        {source && <a href={source} target="_blank" rel="noopener noreferrer" className="row" style={{ gap: 5, fontSize: 'var(--fs-md)' }}>Original source <Icon.ChevronRight size={12} /></a>}
        <div className="row" style={{ flexWrap: 'wrap', gap: 5 }}>
          {(dataset.modalities ?? []).map(value => <Tag key={value}>{titleCase(value)}</Tag>)}
          {(dataset.tasks ?? []).map(value => <Tag key={value} tone="accent">{titleCase(value)}</Tag>)}
        </div>
      </div>

      <div className="insp-section">
        <div className="insp-kicker">Coverage</div>
        <dl className="dl">
          <div><dt>Identity</dt><dd>{titleCase(coverage.identity ?? 'candidate')}</dd></div>
          <div><dt>Source</dt><dd>{titleCase(coverage.source ?? 'unverified')}</dd></div>
          <div><dt>Access</dt><dd>{titleCase(coverage.access ?? 'unknown')}</dd></div>
          <div><dt>Adapter</dt><dd>{titleCase(coverage.adapter ?? 'not started')}</dd></div>
          <div><dt>Preview</dt><dd>{titleCase(coverage.preview ?? 'none')} · {(coverage.preview_count ?? 0).toLocaleString()} {coverage.unit ?? 'example'}</dd></div>
          <div><dt>Complete data</dt><dd>{titleCase(coverage.complete_data ?? 'unimplemented')}</dd></div>
          <div><dt>Publication</dt><dd>{titleCase(coverage.publication ?? 'not reviewed')}</dd></div>
        </dl>
        {!!coverage.blockers?.length && (
          <>
            <div className="insp-kicker">Recorded blockers</div>
            <ul style={{ margin: 0, paddingLeft: 18, fontSize: 'var(--fs-md)', lineHeight: 1.5 }}>
              {coverage.blockers.map((blocker, index) => <li key={index}>{blocker}</li>)}
            </ul>
          </>
        )}
      </div>

      {!!(dataset.aliases ?? []).length && (
        <div className="insp-section">
          <div className="insp-kicker">Also known as</div>
          <p style={{ fontSize: 'var(--fs-md)' }}>{dataset.aliases?.join(' · ')}</p>
        </div>
      )}

      {!!relationships.length && (
        <div className="insp-section">
          <div className="insp-kicker">Related datasets</div>
          <p className="hint">Links describe source or annotation relationships. Each dataset keeps its own access and preview state.</p>
          {relationships.map((item, index) => {
            const target = evidenceText(item.target_id) || evidenceText(item.target) || evidenceText(item.alias_id)
            const related = catalogue.find(entry => entry.id === target)
            return (
              <div key={`${target}-${index}`} className="row" style={{ gap: 7, padding: '4px 0', fontSize: 'var(--fs-md)', flexWrap: 'wrap' }}>
                <Tag>{evidenceText(item.type).replaceAll('_', ' ') || 'related'}</Tag>
                {related
                  ? <button type="button" className="linkish truncate" onClick={() => onOpenDataset(related.id)}>{related.name}</button>
                  : <span className="truncate" style={{ color: 'var(--text-muted)' }}>{target || 'Unresolved target'}</span>}
                {evidenceText(item.scope) && <span className="hint" style={{ flexBasis: '100%', fontSize: 'var(--fs-sm)' }}>{evidenceText(item.scope)}</span>}
              </div>
            )
          })}
        </div>
      )}

      <div className="insp-section">
        <div className="insp-kicker">Rights</div>
        <dl className="dl">
          {Object.entries(dataset.rights ?? {}).map(([key, value]) => <div key={key}><dt>{titleCase(key)}</dt><dd>{display(value)}</dd></div>)}
          {!Object.keys(dataset.rights ?? {}).length && <div><dt>Status</dt><dd>Not recorded — treat as metadata-only for publication.</dd></div>}
        </dl>
      </div>

      <div className="insp-section">
        <details className="disclosure" style={{ borderTop: 0 }}>
          <summary>Evidence ({evidence.length})</summary>
          <div className="body col" style={{ gap: 8 }}>
            <p className="hint">Source checks and paper mentions have separate review scopes. A receipt does not by itself establish reuse rights.</p>
            {sourceEvidence.slice(0, 4).map((item, index) => <Receipt key={`source-${index}`} item={item} />)}
            {paperEvidence.slice(0, 3).map((item, index) => <Receipt key={`paper-${index}`} item={item} />)}
            {!evidence.length && <p className="hint">No evidence receipts are registered.</p>}
            {evidence.length > 7 && <p className="hint">{evidence.length - 7} further receipts are recorded in the registry.</p>}
          </div>
        </details>
        <details className="disclosure">
          <summary>Technical identifiers</summary>
          <div className="body">
            <dl className="dl">
              <div><dt>Dataset ID</dt><dd className="mono wrap-any">{dataset.id}</dd></div>
              <div><dt>Release</dt><dd className="wrap-any">{dataset.release ?? 'Unresolved'}</dd></div>
              <div><dt>Snapshot</dt><dd className="mono wrap-any">{dataset.snapshot_id ?? 'Unknown'}</dd></div>
              <div><dt>Adapter</dt><dd className="mono">{dataset.adapter ?? '—'}</dd></div>
              <div><dt>Papers</dt><dd className="wrap-any">{(dataset.paper_ids ?? []).join(', ') || 'None linked'}</dd></div>
            </dl>
          </div>
        </details>
      </div>
    </>
  )
}
