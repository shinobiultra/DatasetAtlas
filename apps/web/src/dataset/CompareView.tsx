import { useMemo, useState } from 'react'
import type { Artifact, FieldDescriptor, Record as AtlasRecord } from '../generated'
import { fieldValue } from '../query'
import { display, fieldOrigin, isMissing, recordHeadline, shortId, titleCase } from '../lib/format'
import { AssetView, primaryAsset } from '../ui/MediaView'
import { detectorStates } from './model'
import { Empty, Tag } from '../ui/primitives'
import { Value } from '../ui/Value'
import * as Icon from '../ui/Icons'

type Side = 'a' | 'b'
type Section = 'annotations' | 'outputs' | 'metadata'

function Pane({ side, record, records, onNavigate, onClear }: {
  side: Side; record: AtlasRecord | null; records: AtlasRecord[]
  onNavigate: (delta: number) => void; onClear: () => void
}) {
  const asset = record ? primaryAsset(record) : null
  const position = record ? records.findIndex(item => item.id === record.id) : -1
  return (
    <section className="compare-pane" aria-label={`Comparison side ${side.toUpperCase()}`}>
      <div className="compare-pane-head">
        <span className={`side-badge ${side}`}>{side.toUpperCase()}</span>
        <div style={{ minWidth: 0 }}>
          <div className="truncate" style={{ fontSize: 'var(--fs-md)', fontWeight: 580 }}>{record ? record.dataset_id : 'Nothing pinned'}</div>
          <div className="truncate mono" style={{ fontSize: 'var(--fs-sm)', color: 'var(--text-muted)' }} title={record?.id}>{record ? shortId(record.id, 22) : '—'}</div>
        </div>
        <span className="spacer" />
        {position >= 0 && <span style={{ fontSize: 'var(--fs-sm)', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>{position + 1} / {records.length}</span>}
        <button type="button" className="btn icon sm" onClick={() => onNavigate(-1)} disabled={position <= 0} aria-label={`Previous sample on side ${side.toUpperCase()}`}><Icon.ChevronLeft size={13} /></button>
        <button type="button" className="btn icon sm" onClick={() => onNavigate(1)} disabled={position < 0 || position >= records.length - 1} aria-label={`Next sample on side ${side.toUpperCase()}`}><Icon.ChevronRight size={13} /></button>
        <button type="button" className="btn icon sm" onClick={onClear} disabled={!record} aria-label={`Unpin side ${side.toUpperCase()}`}><Icon.Close size={13} /></button>
      </div>
      <div className="compare-pane-media">
        {record
          ? (asset ? <AssetView asset={asset} controls alt={`Side ${side.toUpperCase()}: ${record.id}`} /> : <div style={{ padding: 20, fontSize: 'var(--fs-md)', overflow: 'auto', maxHeight: '100%' }}>{recordHeadline(record)}</div>)
          : <div className="fallback" style={{ padding: 22 }}><Icon.Compare size={20} /><span>Select a record and pin it to {side.toUpperCase()}</span></div>}
      </div>
      {record && <div className="compare-pane-foot">{record.question ?? record.text ?? <span style={{ color: 'var(--text-faint)' }}>No text content</span>}</div>}
    </section>
  )
}

/** Mockup 9: two equal media panels above aligned evidence, with an explicit pin model. */
export function CompareView({ pair, records, fields, artifacts, unit, populationScope, onPin, onAskModel }: {
  pair: [string | null, string | null]
  records: AtlasRecord[]
  fields: FieldDescriptor[]
  artifacts: Artifact[]
  unit: string
  populationScope: string
  onPin: (side: Side, id: string | null) => void
  onAskModel: () => void
}) {
  const [section, setSection] = useState<Section>('annotations')
  const [diffOnly, setDiffOnly] = useState(false)
  const a = records.find(record => record.id === pair[0]) ?? null
  const b = records.find(record => record.id === pair[1]) ?? null

  const relationship = useMemo(() => {
    if (!a || !b) return null
    const forward = (a.relations ?? []).find(relation => relation.object_id === b.id)
    const backward = (b.relations ?? []).find(relation => relation.object_id === a.id)
    const found = forward ?? backward
    return found ? { type: found.type, direction: forward ? 'A → B' : 'B → A' } : null
  }, [a, b])

  const rows = useMemo(() => {
    if (!a && !b) return []
    const entries: Array<{ key: string; label: string; origin: string; left: unknown; right: unknown; comparable: boolean }> = []
    if (section === 'annotations' || section === 'outputs') {
      const namespace = section === 'annotations' ? 'source' : 'prediction'
      const keys = [...new Set([
        ...Object.keys((a?.[namespace] ?? {}) as Record<string, unknown>),
        ...Object.keys((b?.[namespace] ?? {}) as Record<string, unknown>),
      ])].sort()
      for (const key of keys) {
        const fieldId = `${namespace}.${key}`
        const field = fields.find(item => item.id === fieldId)
        const left = a ? fieldValue(a, fieldId) : undefined
        const right = b ? fieldValue(b, fieldId) : undefined
        entries.push({
          key: fieldId,
          label: field?.name ?? key,
          origin: field ? fieldOrigin(field) : (namespace === 'source' ? 'Source annotations' : 'Computed results'),
          left, right,
          // Only fields registered on both sides are meaningfully comparable.
          comparable: !isMissing(left) && !isMissing(right) && typeof left === typeof right,
        })
      }
    } else {
      const metadata: Array<[string, (record: AtlasRecord) => unknown]> = [
        ['Record ID', record => record.id],
        ['Dataset', record => record.dataset_id],
        ['Release', record => record.release_id],
        ['Snapshot', record => record.snapshot_id],
        ['Unit', record => record.unit ?? 'example'],
        ['Assets', record => (record.assets ?? []).length],
        ['Modalities', record => [...new Set((record.assets ?? []).map(asset => asset.modality))].join(', ')],
        ['Representation', record => [...new Set((record.assets ?? []).map(asset => asset.representation ?? 'original'))].join(', ')],
      ]
      for (const [label, pick] of metadata) {
        const left = a ? pick(a) : undefined
        const right = b ? pick(b) : undefined
        entries.push({ key: label, label, origin: 'Record structure', left, right, comparable: !isMissing(left) && !isMissing(right) })
      }
    }
    return entries
  }, [a, b, fields, section])

  const shownRows = diffOnly ? rows.filter(row => row.comparable && display(row.left) !== display(row.right)) : rows
  const runsA = a ? detectorStates(artifacts, a.id) : []
  const runsB = b ? detectorStates(artifacts, b.id) : []

  return (
    <div className="compare">
      <div className="compare-top">
        <Pane side="a" record={a} records={records} onClear={() => onPin('a', null)}
          onNavigate={delta => { const index = records.findIndex(record => record.id === a?.id); const next = records[index + delta]; if (next) onPin('a', next.id) }} />
        <Pane side="b" record={b} records={records} onClear={() => onPin('b', null)}
          onNavigate={delta => { const index = records.findIndex(record => record.id === b?.id); const next = records[index + delta]; if (next) onPin('b', next.id) }} />
      </div>

      <div className="compare-bottom">
        <div className="compare-bottom-head">
          <div className="tabs" role="tablist" aria-label="Comparison detail" style={{ borderBottom: 0, gap: 16 }}>
            {(['annotations', 'outputs', 'metadata'] as Section[]).map(value => (
              <button key={value} role="tab" type="button" aria-selected={section === value} onClick={() => setSection(value)}>
                {value === 'outputs' ? 'Model outputs' : titleCase(value)}
              </button>
            ))}
          </div>
          <span className="spacer" />
          {relationship
            ? <Tag tone="accent">Recorded relation: {relationship.type.replaceAll('_', ' ')} ({relationship.direction})</Tag>
            : a && b && <Tag>No recorded relation between A and B</Tag>}
          <label className="row" style={{ gap: 6, fontSize: 'var(--fs-sm)', color: 'var(--text-muted)' }}>
            <input type="checkbox" checked={diffOnly} onChange={event => setDiffOnly(event.target.checked)} />
            Differences only
          </label>
          <button type="button" className="btn sm" disabled={!a || !b} onClick={onAskModel}><Icon.Chat size={13} />Ask about these two</button>
        </div>

        <div className="compare-table">
          {!a && !b ? (
            <Empty title="Pin two records">Select records in Grid or Table, then use Compare. Pinned records stay until you replace them, even when the filter changes.</Empty>
          ) : (
            <>
              {section === 'outputs' && (runsA.length > 0 || runsB.length > 0) && (
                <table className="aligned">
                  <thead><tr><th className="k">Detector run</th><th>A</th><th>B</th></tr></thead>
                  <tbody>
                    {[...new Set([...runsA, ...runsB].map(state => state.artifact.id))].map(artifactId => {
                      const left = runsA.find(state => state.artifact.id === artifactId)
                      const right = runsB.find(state => state.artifact.id === artifactId)
                      const label = (left ?? right)!.runLabel
                      return (
                        <tr key={artifactId}>
                          <td className="k">{label}</td>
                          <td>{left ? left.summary : 'Not computed'}</td>
                          <td>{right ? right.summary : 'Not computed'}</td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              )}
              <table className="aligned">
                <thead>
                  <tr>
                    <th className="k">Field</th>
                    <th><span className="row" style={{ gap: 6 }}><span className="side-badge a" style={{ width: 16, height: 16, fontSize: 10 }}>A</span>{a ? shortId(a.id, 18) : '—'}</span></th>
                    <th><span className="row" style={{ gap: 6 }}><span className="side-badge b" style={{ width: 16, height: 16, fontSize: 10 }}>B</span>{b ? shortId(b.id, 18) : '—'}</span></th>
                  </tr>
                </thead>
                <tbody>
                  {shownRows.map(row => {
                    const different = row.comparable && display(row.left) !== display(row.right)
                    return (
                      <tr key={row.key} data-diff={different}>
                        <td className="k"><div className="truncate" title={row.key}>{row.label}</div><div className="origin-line">{row.origin}</div></td>
                        <td><Value value={row.left} inline /></td>
                        <td><Value value={row.right} inline /></td>
                      </tr>
                    )
                  })}
                  {!shownRows.length && (
                    <tr><td colSpan={3} style={{ color: 'var(--text-muted)', padding: 16 }}>
                      {diffOnly ? 'No comparable field differs between A and B.' : 'No fields in this section.'}
                    </td></tr>
                  )}
                </tbody>
              </table>
              <p className="hint" style={{ padding: '8px 12px' }}>
                Differences are computed only between values present on both sides with the same type, over {unit} records in the {populationScope} population.
                Two numbers from unrelated runs are not compared.
              </p>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
