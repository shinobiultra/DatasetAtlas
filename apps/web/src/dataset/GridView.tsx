import { useEffect, useMemo, useRef, useState } from 'react'
import type { FieldDescriptor, Record as AtlasRecord } from '../generated'
import { fieldValue } from '../query'
import { display, isMissing, recordHeadline } from '../lib/format'
import { AssetView, imageAssets, primaryAsset } from '../ui/MediaView'
import * as Icon from '../ui/Icons'

const GAP = 12
const PAD = 16

export type GridProps = {
  records: AtlasRecord[]
  cardWidth: number
  labelFields: FieldDescriptor[]
  selected: Set<string>
  inspected: string | null
  onInspect: (id: string) => void
  onToggle: (id: string, checked: boolean) => void
  onOpen: (id: string) => void
  scrollRef: React.RefObject<HTMLDivElement | null>
  footer?: React.ReactNode
}

function Card({ record, width, labelFields, selected, inspected, onInspect, onToggle, onOpen }: {
  record: AtlasRecord; width: number; labelFields: FieldDescriptor[]
  selected: boolean; inspected: boolean
  onInspect: () => void; onToggle: (checked: boolean) => void; onOpen: () => void
}) {
  const asset = primaryAsset(record)
  const images = imageAssets(record)
  const mediaHeight = Math.round(width * 0.66)
  const headline = recordHeadline(record)
  const conversation = (record.conversation?.length ?? 0) > 0
  return (
    <article className="sample-card" data-record-id={record.id} data-selected={selected} data-inspected={inspected}>
      <span className="sample-check">
        <input
          type="checkbox" checked={selected}
          onChange={event => onToggle(event.target.checked)}
          aria-label={`Select record ${record.id}`}
          onClick={event => event.stopPropagation()}
        />
      </span>
      <button type="button" className="btn icon sm sample-open-btn" title="Open focused inspection" aria-label={`Open focused inspection for ${record.id}`}
        onClick={event => { event.stopPropagation(); onOpen() }}>
        <Icon.Expand size={13} />
      </button>
      <button
        type="button" className="open" onClick={onInspect} onDoubleClick={onOpen}
        aria-label={`Inspect record ${record.id}`} aria-pressed={inspected}
      >
        <div className="sample-media" style={{ height: mediaHeight }}>
          {asset ? <AssetView asset={asset} fit="contain" alt="" /> : <div className="textprev clamp-3">{headline}</div>}
          {(images.length > 1 || conversation) && (
            <span className="sample-badges">
              {images.length > 1 && <span className="b"><Icon.Layers size={11} />{images.length}</span>}
              {conversation && <span className="b"><Icon.Chat size={11} />{record.conversation?.length}</span>}
            </span>
          )}
        </div>
        <div className="sample-body">
          {asset && <div className="primary clamp-2">{headline}</div>}
          {labelFields.length > 0 && (
            <div className="fields">
              {labelFields.slice(0, 3).map(field => {
                const value = fieldValue(record, field.id)
                return (
                  <span key={field.id} className="tag" title={`${field.name}: ${display(value)}`}>
                    <span className="tag-key">{field.name}</span>
                    <span className={isMissing(value) ? 'tag-missing' : undefined}>{display(value)}</span>
                  </span>
                )
              })}
            </div>
          )}
        </div>
      </button>
    </article>
  )
}

/** Virtualized contact sheet: only the visible rows exist in the DOM. */
export function GridView({ records, cardWidth, labelFields, selected, inspected, onInspect, onToggle, onOpen, scrollRef, footer }: GridProps) {
  const [viewport, setViewport] = useState({ top: 0, height: 800, width: 1000 })
  const inner = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const element = scrollRef.current
    if (!element) return
    const measure = () => setViewport({ top: element.scrollTop, height: element.clientHeight, width: (inner.current?.clientWidth ?? element.clientWidth) })
    measure()
    element.addEventListener('scroll', measure, { passive: true })
    const observer = new ResizeObserver(measure)
    observer.observe(element)
    if (inner.current) observer.observe(inner.current)
    return () => { element.removeEventListener('scroll', measure); observer.disconnect() }
  }, [scrollRef])

  const columns = Math.max(1, Math.floor((viewport.width + GAP) / (cardWidth + GAP)))
  const actualWidth = Math.floor((viewport.width - GAP * (columns - 1)) / columns) || cardWidth
  const rowHeight = Math.round(actualWidth * 0.66) + (labelFields.length ? 68 : 44) + GAP
  const rows = Math.ceil(records.length / columns)
  const first = Math.max(0, Math.floor((viewport.top - PAD) / rowHeight) - 2)
  const last = Math.min(rows, Math.ceil((viewport.top - PAD + viewport.height) / rowHeight) + 2)
  const slice = useMemo(() => records.slice(first * columns, last * columns), [records, first, last, columns])

  return (
    <div className="sample-grid">
      <div ref={inner}>
        <div style={{ height: first * rowHeight }} aria-hidden />
        <div className="sample-grid-inner" style={{ gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))` }}>
          {slice.map(record => (
            <Card
              key={record.id} record={record} width={actualWidth} labelFields={labelFields}
              selected={selected.has(record.id)} inspected={inspected === record.id}
              onInspect={() => onInspect(record.id)}
              onToggle={checked => onToggle(record.id, checked)}
              onOpen={() => onOpen(record.id)}
            />
          ))}
        </div>
        <div style={{ height: Math.max(0, (rows - last) * rowHeight) }} aria-hidden />
      </div>
      {footer}
    </div>
  )
}
