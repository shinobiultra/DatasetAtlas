import { displayUrl } from '../lib/display'
import { useEffect, useMemo, useRef, useState } from 'react'
import type { FieldDescriptor, Record as AtlasRecord } from '../generated'
import { fieldValue } from '../query'
import { display, isMissing, recordHeadline, shortId } from '../lib/format'
import { assetUrl, primaryAsset } from '../ui/MediaView'
import * as Icon from '../ui/Icons'

export type Sort = { field_id: string; direction: 'asc' | 'desc' } | null

export type TableProps = {
  records: AtlasRecord[]
  columns: FieldDescriptor[]
  showThumbnail: boolean
  showText: boolean
  textHeader: string
  dense: boolean
  selected: Set<string>
  inspected: string | null
  sort: Sort
  onSort: (field: FieldDescriptor) => void
  onInspect: (id: string) => void
  onToggle: (id: string, checked: boolean) => void
  onToggleAllVisible: (checked: boolean) => void
  onOpen: (id: string) => void
  scrollRef: React.RefObject<HTMLDivElement | null>
  footer?: React.ReactNode
}

const DTYPE_MARK: Record<string, string> = { number: '#', string: 'A', boolean: '01', category: '◇', array: '[]', object: '{}' }

function Cell({ record, field }: { record: AtlasRecord; field: FieldDescriptor }) {
  const value = fieldValue(record, field.id)
  if (isMissing(value)) return <td className="missing" title={`${field.name} is missing for this record`}>—</td>
  if (field.dtype === 'number') return <td className="num">{display(value)}</td>
  return <td><span className="cellclip" title={display(value)}>{display(value)}</span></td>
}

/** Virtualized rows with fixed height so scrolling a complete index stays smooth. */
export function TableView(props: TableProps) {
  const { records, columns, showThumbnail, showText, textHeader, dense, selected, inspected, sort, onSort, onInspect, onToggle, onToggleAllVisible, onOpen, scrollRef, footer } = props
  const rowHeight = dense ? 34 : 40
  const [viewport, setViewport] = useState({ top: 0, height: 800 })
  const headRef = useRef<HTMLTableSectionElement>(null)

  useEffect(() => {
    const element = scrollRef.current
    if (!element) return
    const measure = () => setViewport({ top: element.scrollTop, height: element.clientHeight })
    measure()
    element.addEventListener('scroll', measure, { passive: true })
    const observer = new ResizeObserver(measure)
    observer.observe(element)
    return () => { element.removeEventListener('scroll', measure); observer.disconnect() }
  }, [scrollRef])

  const headHeight = headRef.current?.clientHeight ?? 36
  const first = Math.max(0, Math.floor((viewport.top - headHeight) / rowHeight) - 4)
  const last = Math.min(records.length, Math.ceil((viewport.top - headHeight + viewport.height) / rowHeight) + 6)
  const slice = useMemo(() => records.slice(first, last), [records, first, last])
  const allVisibleSelected = records.length > 0 && records.every(record => selected.has(record.id))

  return (
    <>
      <table className={`data${dense ? ' dense' : ''}`}>
        <thead ref={headRef}>
          <tr>
            <th className="checkcell">
              <input
                type="checkbox" checked={allVisibleSelected}
                ref={element => { if (element) element.indeterminate = !allVisibleSelected && records.some(record => selected.has(record.id)) }}
                onChange={event => onToggleAllVisible(event.target.checked)}
                aria-label="Select all loaded records"
              />
            </th>
            {showThumbnail && <th style={{ width: 68 }}>Preview</th>}
            {showText && <th style={{ minWidth: 240 }}>{textHeader}</th>}
            {columns.map(field => (
              <th key={`${field.unit}:${field.id}`} title={field.description || field.id} aria-sort={sort?.field_id === field.id ? (sort.direction === 'asc' ? 'ascending' : 'descending') : 'none'}>
                <span className="th" role="button" tabIndex={0} onClick={() => onSort(field)}
                  onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); onSort(field) } }}>
                  <span className="dtype">{DTYPE_MARK[field.dtype ?? 'string'] ?? '·'}</span>
                  <span className="truncate">{field.name}</span>
                  {sort?.field_id === field.id && <span aria-hidden>{sort.direction === 'asc' ? '↑' : '↓'}</span>}
                </span>
              </th>
            ))}
            <th style={{ width: 92 }}>Record</th>
          </tr>
        </thead>
        <tbody>
          {first > 0 && <tr style={{ height: first * rowHeight }} aria-hidden><td colSpan={columns.length + 3 + (showThumbnail ? 1 : 0) + (showText ? 1 : 0)} /></tr>}
          {slice.map(record => {
            const asset = showThumbnail ? primaryAsset(record) : null
            const url = asset ? assetUrl(asset) : null
            return (
              <tr key={record.id} data-record-id={record.id} data-selected={selected.has(record.id)} data-inspected={inspected === record.id}
                onClick={() => onInspect(record.id)} onDoubleClick={() => onOpen(record.id)} style={{ cursor: 'pointer' }}>
                <td className="checkcell" onClick={event => event.stopPropagation()}>
                  <input type="checkbox" checked={selected.has(record.id)} onChange={event => onToggle(record.id, event.target.checked)} aria-label={`Select record ${record.id}`} />
                </td>
                {showThumbnail && (
                  <td className="thumbcell">
                    {url && asset?.modality === 'image'
                      ? <img src={displayUrl(url)} alt="" loading="lazy" decoding="async" onError={event => { event.currentTarget.style.visibility = 'hidden' }} />
                      : <span className="ph" />}
                  </td>
                )}
                {showText && <td><span className="cellclip" title={recordHeadline(record)}>{recordHeadline(record)}</span></td>}
                {columns.map(field => <Cell key={`${field.unit}:${field.id}`} record={record} field={field} />)}
                <td onClick={event => event.stopPropagation()}>
                  <button type="button" className="linkish mono" style={{ fontSize: 'var(--fs-sm)' }} title={record.id} onClick={() => onOpen(record.id)}>
                    {shortId(record.id, 9)}
                  </button>
                </td>
              </tr>
            )
          })}
          {last < records.length && <tr style={{ height: (records.length - last) * rowHeight }} aria-hidden><td colSpan={columns.length + 3 + (showThumbnail ? 1 : 0) + (showText ? 1 : 0)} /></tr>}
        </tbody>
      </table>
      {footer}
    </>
  )
}

export function ColumnPicker({ fields, chosen, onChange }: {
  fields: FieldDescriptor[]; chosen: string[]; onChange: (ids: string[]) => void
}) {
  const groups = new Map<string, FieldDescriptor[]>()
  for (const field of fields) {
    const key = field.namespace === 'prediction' ? 'Computed results' : field.namespace === 'human' ? 'Human review' : field.namespace === 'record' ? 'Record structure' : 'Source annotations'
    groups.set(key, [...(groups.get(key) ?? []), field])
  }
  return (
    <div className="colpicker">
      {[...groups].map(([group, items]) => (
        <div key={group}>
          <div className="insp-kicker" style={{ padding: '7px 0 3px' }}>{group}</div>
          {items.map(field => (
            <label className="facet-opt" key={`${field.unit}:${field.id}`} title={field.description || field.id}>
              <input
                type="checkbox" checked={chosen.includes(field.id)}
                onChange={event => onChange(event.target.checked ? [...chosen, field.id] : chosen.filter(id => id !== field.id))}
              />
              <span>{field.name}</span>
            </label>
          ))}
        </div>
      ))}
      {!fields.length && <p className="hint" style={{ padding: 6 }}>No fields are registered for this unit.</p>}
      <div className="row" style={{ marginTop: 8, gap: 6 }}>
        <button type="button" className="btn sm" onClick={() => onChange([])}><Icon.Reset size={13} />Clear all</button>
      </div>
    </div>
  )
}
