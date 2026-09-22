import { displayUrl } from '../lib/display'
import { useEffect, useMemo, useRef, useState } from 'react'
import type { Artifact, FieldDescriptor, Record as AtlasRecord } from '../generated'
import { fieldValue } from '../query'
import { display, shortId, titleCase } from '../lib/format'
import { assetUrl, classColour, primaryAsset } from '../ui/MediaView'
import { Empty } from '../ui/primitives'
import * as Icon from '../ui/Icons'

type Point = { id: string; x: number; y: number }

const MISSING_COLOUR = '#c9cfd9'

function extractPoints(artifact: Artifact): Point[] {
  const data = artifact.data ?? {}
  const raw = (data.points ?? data.items ?? []) as Array<{ id: string; x?: number; y?: number; status?: string; output?: { x?: number; y?: number } }>
  return raw
    .map(item => ({ id: item.id, x: item.x ?? item.output?.x, y: item.y ?? item.output?.y }))
    .filter((item): item is Point => Number.isFinite(item.x) && Number.isFinite(item.y))
}

export function MapView({ artifact, records, colourField, onInspect, onSelect, selected, onOpen, loadingMore = false, matchedCount = null, capped = false }: {
  artifact: Artifact
  records: AtlasRecord[]
  colourField: FieldDescriptor | null
  onInspect: (id: string) => void
  onSelect: (ids: string[], mode: 'replace' | 'add') => void
  selected: Set<string>
  onOpen: (id: string) => void
  loadingMore?: boolean
  matchedCount?: number | null
  capped?: boolean
}) {
  const canvas = useRef<HTMLCanvasElement>(null)
  const stage = useRef<HTMLDivElement>(null)
  const drag = useRef<{ path: Array<{ x: number; y: number }>; pan: boolean; last: { x: number; y: number } } | null>(null)
  const [lasso, setLasso] = useState<Array<{ x: number; y: number }>>([])
  const [mode, setMode] = useState<'lasso' | 'pan'>('lasso')
  const [transform, setTransform] = useState({ scale: 1, dx: 0, dy: 0 })
  const [size, setSize] = useState({ width: 900, height: 560 })

  useEffect(() => {
    const element = stage.current
    if (!element) return
    const measure = () => setSize({ width: element.clientWidth, height: element.clientHeight })
    measure()
    const observer = new ResizeObserver(measure)
    observer.observe(element)
    return () => observer.disconnect()
  }, [])

  const points = useMemo(() => extractPoints(artifact), [artifact])
  const loaded = useMemo(() => new Set(records.map(record => record.id)), [records])

  const layout = useMemo(() => {
    const present = points.filter(point => loaded.has(point.id))
    const padding = 26
    const width = size.width - padding * 2, height = size.height - padding * 2
    // Lay out strictly inside the measured canvas: a layout larger than the
    // canvas would push points outside it and silently drop them from the draw.
    if (!present.length || width <= 0 || height <= 0) return []
    const xs = present.map(point => point.x), ys = present.map(point => point.y)
    const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys)
    return present.map(point => ({
      id: point.id,
      x: padding + width * (point.x - minX) / (maxX - minX || 1),
      y: padding + height * (1 - (point.y - minY) / (maxY - minY || 1)),
    }))
  }, [points, loaded, size])

  const colouring = useMemo(() => {
    if (!colourField) return { colours: new Map<string, string>(), legend: [] as Array<{ label: string; colour: string }>, missing: 0 }
    const values = new Map(records.map(record => [record.id, fieldValue(record, colourField.id)]))
    const numeric = [...values.values()].filter((value): value is number => typeof value === 'number' && Number.isFinite(value))
    const colours = new Map<string, string>()
    let missing = 0
    if (numeric.length && numeric.length === [...values.values()].filter(value => value !== null && value !== undefined).length) {
      const min = Math.min(...numeric), max = Math.max(...numeric)
      for (const point of layout) {
        const value = values.get(point.id)
        if (typeof value !== 'number') { colours.set(point.id, MISSING_COLOUR); missing += 1; continue }
        const fraction = (value - min) / (max - min || 1)
        colours.set(point.id, `hsl(${222 - 200 * fraction} 72% ${64 - 20 * fraction}%)`)
      }
      return {
        colours, missing,
        legend: [
          { label: `${display(min)} (low)`, colour: 'hsl(222 72% 64%)' },
          { label: `${display(max)} (high)`, colour: 'hsl(22 72% 44%)' },
          ...(missing ? [{ label: `${missing} missing`, colour: MISSING_COLOUR }] : []),
        ],
      }
    }
    const categories = new Map<string, number>()
    for (const point of layout) {
      const value = values.get(point.id)
      if (value === null || value === undefined) { colours.set(point.id, MISSING_COLOUR); missing += 1; continue }
      const key = display(value)
      categories.set(key, (categories.get(key) ?? 0) + 1)
      colours.set(point.id, classColour(key))
    }
    const legend = [...categories].sort((a, b) => b[1] - a[1]).slice(0, 12).map(([label]) => ({ label, colour: classColour(label) }))
    if (missing) legend.push({ label: `${missing} missing`, colour: MISSING_COLOUR })
    return { colours, legend, missing }
  }, [colourField, records, layout])

  useEffect(() => {
    const element = canvas.current
    const context = element?.getContext('2d')
    if (!element || !context) return
    const ratio = window.devicePixelRatio || 1
    element.width = Math.max(1, Math.round(size.width * ratio))
    element.height = Math.max(1, Math.round(size.height * ratio))
    context.setTransform(ratio, 0, 0, ratio, 0, 0)
    context.clearRect(0, 0, size.width, size.height)
    const radius = Math.max(1.6, 3.2 * Math.sqrt(transform.scale))
    for (const point of layout) {
      const x = point.x * transform.scale + transform.dx
      const y = point.y * transform.scale + transform.dy
      if (x < -8 || y < -8 || x > size.width + 8 || y > size.height + 8) continue
      const chosen = selected.has(point.id)
      context.beginPath()
      context.arc(x, y, chosen ? radius + 1.6 : radius, 0, Math.PI * 2)
      context.fillStyle = colouring.colours.get(point.id) ?? '#2563eb'
      context.globalAlpha = selected.size && !chosen ? 0.34 : 0.9
      context.fill()
      if (chosen) {
        context.globalAlpha = 1
        context.lineWidth = 1.6
        context.strokeStyle = '#171d27'
        context.stroke()
      }
    }
    context.globalAlpha = 1
  }, [layout, colouring, transform, size, selected])

  function position(event: React.PointerEvent<HTMLCanvasElement>) {
    const bounds = event.currentTarget.getBoundingClientRect()
    return { x: event.clientX - bounds.left, y: event.clientY - bounds.top }
  }

  function finish(event: React.PointerEvent<HTMLCanvasElement>) {
    const start = drag.current
    if (!start) return
    const pointer = position(event)
    if (start.pan) { drag.current = null; setLasso([]); return }
    const path = [...start.path, pointer]
    const moved = path.some(point => Math.hypot(path[0].x - point.x, path[0].y - point.y) > 7)
    if (path.length > 3 && moved) {
      const inside = (x: number, y: number) => {
        let hit = false
        for (let index = 0, previous = path.length - 1; index < path.length; previous = index++) {
          const a = path[index], b = path[previous]
          if ((a.y > y) !== (b.y > y) && x < (b.x - a.x) * (y - a.y) / (b.y - a.y) + a.x) hit = !hit
        }
        return hit
      }
      const hits = layout.filter(point => inside(point.x * transform.scale + transform.dx, point.y * transform.scale + transform.dy)).map(point => point.id)
      onSelect(hits, event.shiftKey ? 'add' : 'replace')
    } else {
      let nearest: { id: string; distance: number } | null = null
      for (const point of layout) {
        const distance = Math.hypot(point.x * transform.scale + transform.dx - pointer.x, point.y * transform.scale + transform.dy - pointer.y)
        if (!nearest || distance < nearest.distance) nearest = { id: point.id, distance }
      }
      if (nearest && nearest.distance < 13) onInspect(nearest.id)
    }
    drag.current = null
    setLasso([])
  }

  function zoom(factor: number) {
    setTransform(current => {
      const scale = Math.min(10, Math.max(0.4, current.scale * factor))
      const ratio = scale / current.scale
      const cx = size.width / 2, cy = size.height / 2
      return { scale, dx: cx - (cx - current.dx) * ratio, dy: cy - (cy - current.dy) * ratio }
    })
  }

  const selectedRecords = records.filter(record => selected.has(record.id)).slice(0, 40)
  const plotted = layout.length

  return (
    <div className="map">
      <div className="map-stage" ref={stage}>
        <canvas
          ref={canvas} style={{ cursor: mode === 'pan' ? 'grab' : 'crosshair' }}
          role="img"
          aria-label={`Projection ${artifact.kind} with ${plotted} plotted points. ${mode === 'pan' ? 'Drag to pan.' : 'Draw a lasso to select; hold Shift to add.'} Click a point to inspect it.`}
          onPointerDown={event => {
            const pointer = position(event)
            drag.current = { path: [pointer], pan: mode === 'pan' || event.button === 1, last: pointer }
            event.currentTarget.setPointerCapture(event.pointerId)
          }}
          onPointerMove={event => {
            const current = drag.current
            if (!current) return
            const pointer = position(event)
            if (current.pan) {
              setTransform(view => ({ ...view, dx: view.dx + pointer.x - current.last.x, dy: view.dy + pointer.y - current.last.y }))
              current.last = pointer
            } else {
              current.path.push(pointer)
              setLasso([...current.path])
            }
          }}
          onPointerUp={finish}
          onPointerCancel={() => { drag.current = null; setLasso([]) }}
        />
        {lasso.length > 1 && (
          <svg className="lasso" aria-hidden>
            <polyline points={lasso.map(point => `${point.x},${point.y}`).join(' ')} fill="rgba(37,99,235,.08)" stroke="#2563eb" strokeWidth="1.5" />
          </svg>
        )}
        <div className="map-tools">
          <button type="button" className={`btn sm${mode === 'lasso' ? ' primary' : ''}`} onClick={() => setMode('lasso')}>Lasso</button>
          <button type="button" className={`btn sm${mode === 'pan' ? ' primary' : ''}`} onClick={() => setMode('pan')}>Pan</button>
          <button type="button" className="btn sm icon" onClick={() => zoom(1.4)} aria-label="Zoom in"><Icon.Plus size={13} /></button>
          <button type="button" className="btn sm icon" onClick={() => zoom(1 / 1.4)} aria-label="Zoom out"><span aria-hidden>−</span></button>
          <button type="button" className="btn sm icon" onClick={() => setTransform({ scale: 1, dx: 0, dy: 0 })} aria-label="Reset view"><Icon.Reset size={13} /></button>
        </div>
        {colourField && colouring.legend.length > 0 && (
          <div className="map-legend">
            <h4 className="truncate" title={colourField.name}>{colourField.name}</h4>
            {colouring.legend.map(entry => (
              <div className="lg" key={entry.label}><span className="dot" style={{ background: entry.colour }} /><span className="truncate" title={entry.label}>{entry.label}</span></div>
            ))}
          </div>
        )}
        {!plotted && (
          <div style={{ position: 'absolute', inset: 0, display: 'grid', placeContent: 'center' }}>
            <Empty title="No points from this projection are in view">
              The projection covers {artifact.ids.length.toLocaleString()} {artifact.unit} IDs, none of which are in the {records.length.toLocaleString()} currently loaded records. Widen the filter or load more.
            </Empty>
          </div>
        )}
      </div>
      <div className="map-strip">
        <div className="row" style={{ fontSize: 'var(--fs-sm)', color: 'var(--text-muted)', flexWrap: 'wrap' }}>
          <strong style={{ color: 'var(--text)' }}>{plotted.toLocaleString()} plotted</strong>
          <span className="sep">·</span>
          <span>{records.length.toLocaleString()} loaded{matchedCount !== null ? ` of ${matchedCount.toLocaleString()} matching` : ''} · {artifact.ids.length.toLocaleString()} in the projection population</span>
          {loadingMore && <><span className="sep">·</span><span>loading more points…</span></>}
          {capped && <><span className="sep">·</span><span>plotting is capped here; narrow the filter to inspect the rest</span></>}
          <span className="sep">·</span>
          <span>{artifact.kind} · {shortId(artifact.run_id ?? artifact.id, 8)}</span>
          {colouring.missing > 0 && <><span className="sep">·</span><span>{colouring.missing.toLocaleString()} grey points have no colour value</span></>}
        </div>
        {selectedRecords.length > 0 ? (
          <div className="map-strip-row">
            {selectedRecords.map(record => {
              const asset = primaryAsset(record)
              const url = asset ? assetUrl(asset) : null
              return (
                <button type="button" key={record.id} onClick={() => onInspect(record.id)} onDoubleClick={() => onOpen(record.id)} title={record.id}>
                  {url && asset?.modality === 'image' ? <img src={displayUrl(url)} alt="" loading="lazy" /> : <div style={{ height: 62, background: 'var(--n-150)' }} />}
                  <div className="cap clamp-2">{record.question ?? record.text ?? shortId(record.id, 14)}</div>
                </button>
              )
            })}
            {selected.size > selectedRecords.length && <div style={{ alignSelf: 'center', fontSize: 'var(--fs-sm)', color: 'var(--text-muted)', padding: '0 8px' }}>+{(selected.size - selectedRecords.length).toLocaleString()} more selected</div>}
          </div>
        ) : (
          <div style={{ fontSize: 'var(--fs-sm)', color: 'var(--text-faint)' }}>Lasso points to build a selection; their examples appear here.</div>
        )}
      </div>
    </div>
  )
}

export function MapUnavailable({ workbench, onOpenAnalyze }: { workbench: boolean; onOpenAnalyze: () => void }) {
  return (
    <div style={{ padding: 24 }}>
      <Empty
        title="No projection for this population yet"
        action={workbench ? <button type="button" className="btn primary" onClick={onOpenAnalyze}><Icon.Sparkle size={14} />Create a projection</button> : undefined}
      >
        {workbench
          ? 'A map needs a projection artifact built from an embedding run over this snapshot. Open Analyze to embed a selection and project it.'
          : 'This published pack contains no projection artifact. Projections are computed in the local workbench.'}
      </Empty>
    </div>
  )
}

export function ColourPicker({ fields, value, onChange }: { fields: FieldDescriptor[]; value: string; onChange: (id: string) => void }) {
  const groups = new Map<string, FieldDescriptor[]>()
  for (const field of fields) {
    const key = field.namespace === 'prediction' ? 'Computed results' : field.namespace === 'human' ? 'Human review' : field.namespace === 'record' ? 'Record structure' : 'Source annotations'
    groups.set(key, [...(groups.get(key) ?? []), field])
  }
  return (
    <select className="select" style={{ width: 210 }} value={value} onChange={event => onChange(event.target.value)} aria-label="Colour by">
      <option value="">One colour</option>
      {[...groups].map(([group, items]) => (
        <optgroup key={group} label={group}>
          {items.map(field => <option key={`${field.unit}:${field.id}`} value={field.id}>{titleCase(field.name)}</option>)}
        </optgroup>
      ))}
    </select>
  )
}
