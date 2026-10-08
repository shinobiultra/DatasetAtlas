import type { Artifact } from '../generated'
import { display, shortId } from '../lib/format'

type Summary = {
  kind: string; left_field: string; right_field: string; sample_unit: string; population_scope: string
  selected: number; paired: number; missing_left: number; missing_right: number; pearson_r?: number | null
  cells?: Array<{ left: unknown; right: unknown; left_type: string; right_type: string; count: number }>
  groups?: Array<{ group: unknown; group_type: string; count: number; mean: number; median: number; minimum: number; maximum: number }>
}
type Item = { id: string; status: string; output?: { left?: unknown; right?: unknown; left_type?: string; right_type?: string } }

function category(value: unknown, type: string): string { return `${type}: ${JSON.stringify(value)}` }

export function ComparisonResults({ artifacts, onSelectIds }: { artifacts: Artifact[]; onSelectIds?: (ids: string[]) => void }) {
  return <>{artifacts.filter(artifact => artifact.kind === 'compare.fields').map(artifact => {
    const provenance = artifact.provenance?.processor_provenance as { comparison?: Summary } | undefined
    const summary = provenance?.comparison
    if (!summary) return null
    const items = (artifact.data?.items ?? []) as Item[]
    const select = (predicate: (item: Item) => boolean) => onSelectIds?.(items.filter(item => item.status === 'completed' && predicate(item)).map(item => item.id))
    return <section className="insp-section" key={artifact.id} aria-label={`Comparison result ${artifact.id}`}>
      <div className="insp-kicker">Field comparison · {shortId(artifact.id, 12)}</div>
      <p className="hint">{summary.left_field} × {summary.right_field}</p>
      <dl className="dl">
        <div><dt>Population</dt><dd>{summary.population_scope} · {summary.sample_unit}</dd></div>
        <div><dt>Selected / paired</dt><dd>{summary.selected} / {summary.paired}</dd></div>
        <div><dt>Missing first / second</dt><dd>{summary.missing_left} / {summary.missing_right}</dd></div>
        {summary.kind === 'correlation' && <div><dt>Pearson r</dt><dd>{summary.pearson_r == null ? 'Unavailable: too few pairs or a constant field' : summary.pearson_r.toFixed(4)}</dd></div>}
      </dl>
      {onSelectIds && <button type="button" className="btn sm" onClick={() => select(() => true)}>Select paired records</button>}
      {summary.cells && <table className="table"><thead><tr><th>First category</th><th>Second category</th><th>Count</th></tr></thead><tbody>
        {summary.cells.slice(0, 100).map((cell, index) => <tr key={index}><td>{category(cell.left, cell.left_type)}</td><td>{category(cell.right, cell.right_type)}</td><td><button type="button" className="btn sm" disabled={!onSelectIds} onClick={() => select(item => item.output?.left_type === cell.left_type && item.output?.right_type === cell.right_type && Object.is(item.output?.left, cell.left) && Object.is(item.output?.right, cell.right))}>{cell.count}</button></td></tr>)}
      </tbody></table>}
      {summary.groups && <table className="table"><thead><tr><th>Category</th><th>Count</th><th>Mean / median</th><th>Range</th></tr></thead><tbody>
        {summary.groups.slice(0, 100).map((group, index) => <tr key={index}><td>{category(group.group, group.group_type)}</td><td><button type="button" className="btn sm" disabled={!onSelectIds} onClick={() => select(item => item.output?.left_type === group.group_type && Object.is(item.output?.left, group.group))}>{group.count}</button></td><td>{display(group.mean)} / {display(group.median)}</td><td>{display(group.minimum)} – {display(group.maximum)}</td></tr>)}
      </tbody></table>}
      <p className="hint">Frozen result over {artifact.ids.length.toLocaleString()} recorded IDs. Tables show up to 100 categories; the full artifact retains all categories. Snapshot {artifact.snapshot_ids.map(id => shortId(id, 12)).join(', ')}.</p>
    </section>
  })}</>
}
