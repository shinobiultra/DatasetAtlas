import { useEffect, useMemo, useRef, useState } from 'react'
import { BufferAttribute, BufferGeometry, CanvasTexture, Color, MOUSE, PerspectiveCamera, Points, PointsMaterial, Scene, TOUCH, WebGLRenderer } from 'three'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'
import type { Artifact, FieldDescriptor, Record as AtlasRecord } from '../generated'
import { bulkOf, clusterSummary, colourSources, loadColumn, loadProjection, resultCount, type Numeric, type Projection } from '../lib/bulk'
import { display, shortId } from '../lib/format'
import { fieldValue } from '../query'
import { classColour } from '../ui/MediaView'
import { clusterCss, setClusterColour, setRampColour } from '../lib/palette'
import { nearestRow, projectToScreen, rowsInPolygon, strayed } from '../lib/scene'
import { Notice, Spinner } from '../ui/primitives'
import * as Icon from '../ui/Icons'
import { SelectionStrip } from './MapView'

const MISSING = '#c9cfd9'
const DIM = new Color('#d3d9e1')
const DEFAULT = new Color('#2563eb')

type Entry = { label: string; colour: string; count?: number; ids?: string[]; cluster?: number }
type Colouring = { rgb: Float32Array; legend: Entry[]; note: string }

function paint(rgb: Float32Array, index: number, colour: Color) {
  rgb[index * 3] = colour.r; rgb[index * 3 + 1] = colour.g; rgb[index * 3 + 2] = colour.b
}

function roundSprite(): CanvasTexture {
  const canvas = document.createElement('canvas')
  canvas.width = canvas.height = 64
  const context = canvas.getContext('2d')!
  context.beginPath(); context.arc(32, 32, 30, 0, Math.PI * 2); context.fillStyle = '#fff'; context.fill()
  return new CanvasTexture(canvas)
}

/**
 * Interactive 2D/3D map of a projection. Points come from arrays, so every point of a large run is
 * drawn, not only the records loaded into the page; the page's records add colours and thumbnails.
 */
export default function Map3DView({ artifact, artifacts, records, colourField, selected, onSelect, onInspect, onOpen, matchedCount = null, totalSelected }: {
  artifact: Artifact
  artifacts: Artifact[]
  records: AtlasRecord[]
  colourField: FieldDescriptor | null
  selected: Set<string>
  onSelect: (ids: string[], mode: 'replace' | 'add') => void
  onInspect: (id: string) => void
  onOpen: (id: string) => void
  matchedCount?: number | null
  /** Selected points when they are held on the server (a whole population) and `selected` is empty. */
  totalSelected?: number
}) {
  const stage = useRef<HTMLDivElement>(null)
  const [projection, setProjection] = useState<Projection | null>(null)
  const [error, setError] = useState('')
  const [mode, setMode] = useState<'rotate' | 'lasso'>('rotate')
  const [pointSize, setPointSize] = useState(3.2)
  const [lasso, setLasso] = useState<Array<{ x: number; y: number }>>([])
  const sources = useMemo(() => colourSources(artifacts, artifact), [artifacts, artifact])
  const [sourceKey, setSourceKey] = useState('')
  const source = sources.find(item => `${item.artifact.id}:${item.column}` === sourceKey) ?? (sourceKey === '' ? sources[0] : undefined)
  const [labels, setLabels] = useState<{ ids: string[]; values: Numeric } | null>(null)
  const three = useRef<{ render: () => void; project: () => Float32Array; resetView: () => void } | null>(null)

  useEffect(() => {
    let live = true
    setProjection(null); setError('')
    loadProjection(artifact).then(next => { if (live) { setProjection(next); setPointSize(next.ids.length <= 2000 ? 5 : next.ids.length <= 30000 ? 3.5 : 2.2) } }).catch(failure => { if (live) setError(String(failure instanceof Error ? failure.message : failure)) })
    return () => { live = false }
  }, [artifact])

  useEffect(() => {
    let live = true
    setLabels(null)
    if (source) loadColumn(source.artifact, source.column).then(next => { if (live) setLabels(next) }).catch(() => { if (live) setLabels(null) })
    return () => { live = false }
  }, [source?.artifact.id, source?.column])

  const index = useMemo(() => new Map((projection?.ids ?? []).map((id, row) => [id, row])), [projection])

  const colouring = useMemo<Colouring>(() => {
    const count = projection?.ids.length ?? 0
    const rgb = new Float32Array(count * 3)
    const base = new Color()
    if (!projection) return { rgb, legend: [], note: '' }
    if (source && labels) {
      const byId = new Map(labels.ids.map((id, row) => [id, labels.values[row]]))
      if (source.categorical) {
        const members = new Map<number, string[]>()
        let missing = 0
        projection.ids.forEach((id, row) => {
          const value = byId.get(id)
          if (value === undefined) { base.set(MISSING); paint(rgb, row, base); missing += 1; return }
          setClusterColour(base, value); paint(rgb, row, base)
          const list = members.get(value)
          if (list) list.push(id); else members.set(value, [id])
        })
        const sizes = new Map((clusterSummary(source.artifact)?.clusters ?? []).map(row => [row.cluster, row.size]))
        const legend = [...members].sort((a, b) => (b[1].length - a[1].length)).slice(0, 14)
          .map(([label, ids]) => ({ label: label < 0 ? 'Noise' : `Cluster ${label}`, colour: clusterCss(label), count: sizes.get(label) ?? ids.length, ids, cluster: label }))
        return { rgb, legend, note: `${members.size.toLocaleString()} groups${missing ? ` · ${missing.toLocaleString()} points not in this result` : ''}` }
      }
      let min = Infinity, max = -Infinity
      for (const value of labels.values) { if (value < min) min = value; if (value > max) max = value }
      let missing = 0
      projection.ids.forEach((id, row) => {
        const value = byId.get(id)
        if (value === undefined) { base.set(MISSING); paint(rgb, row, base); missing += 1; return }
        const fraction = (value - min) / (max - min || 1)
        setRampColour(base, fraction); paint(rgb, row, base)
      })
      return { rgb, legend: [
        { label: `${display(min)} (low)`, colour: 'hsl(222, 72%, 64%)' }, { label: `${display(max)} (high)`, colour: 'hsl(22, 72%, 44%)' },
      ], note: missing ? `${missing.toLocaleString()} points not in this result` : '' }
    }
    if (colourField && records.length) {
      const values = new Map(records.map(record => [record.id, fieldValue(record, colourField.id)]))
      const categories = new Map<string, number>()
      let loaded = 0
      projection.ids.forEach((id, row) => {
        const value = values.get(id)
        if (value === undefined || value === null) { base.set(MISSING); paint(rgb, row, base); return }
        loaded += 1
        const key = display(value)
        categories.set(key, (categories.get(key) ?? 0) + 1)
        base.set(classColour(key)); paint(rgb, row, base)
      })
      const legend = [...categories].sort((a, b) => b[1] - a[1]).slice(0, 12).map(([label, count]) => ({ label, colour: classColour(label), count }))
      return { rgb, legend, note: `${colourField.name}: ${loaded.toLocaleString()} of ${count.toLocaleString()} points have a loaded value` }
    }
    for (let row = 0; row < count; row++) paint(rgb, row, DEFAULT)
    return { rgb, legend: [], note: '' }
  }, [projection, source, labels, colourField, records])

  // Scene: built once per projection, then only colours, selection and size change.
  const scene = useRef<{ base: Points; top: Points; positions: Float32Array; setSelection: (rows: number[], palette: Float32Array) => void } | null>(null)
  useEffect(() => {
    const element = stage.current
    if (!element || !projection || !projection.ids.length) return
    const count = projection.ids.length
    const { coords, dims } = projection
    // Centre and scale to a unit cube so the camera and controls behave the same for any projection.
    const min = [Infinity, Infinity, Infinity], max = [-Infinity, -Infinity, -Infinity]
    for (let row = 0; row < count; row++) for (let axis = 0; axis < dims; axis++) {
      const value = coords[row * dims + axis]
      if (value < min[axis]) min[axis] = value
      if (value > max[axis]) max[axis] = value
    }
    const extent = Math.max(max[0] - min[0], max[1] - min[1], dims === 3 ? max[2] - min[2] : 0) || 1
    const positions = new Float32Array(count * 3)
    for (let row = 0; row < count; row++) for (let axis = 0; axis < 3; axis++) {
      positions[row * 3 + axis] = axis < dims ? ((coords[row * dims + axis] - (min[axis] + max[axis]) / 2) / extent) * 2 : 0
    }
    const renderer = new WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'high-performance' })
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2))
    renderer.setClearColor(0xffffff, 0)
    const canvas = renderer.domElement
    canvas.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;display:block'
    element.prepend(canvas)
    const camera = new PerspectiveCamera(45, 1, 0.01, 100)
    const home = () => { camera.position.set(0, 0, dims === 3 ? 3.4 : 2.6); controls.target.set(0, 0, 0); controls.update() }
    const sceneGraph = new Scene()
    const sprite = roundSprite()
    const material = () => new PointsMaterial({ size: pointSize, sizeAttenuation: false, vertexColors: true, map: sprite, alphaTest: 0.5, transparent: false })
    const baseGeometry = new BufferGeometry()
    baseGeometry.setAttribute('position', new BufferAttribute(positions, 3))
    baseGeometry.setAttribute('color', new BufferAttribute(new Float32Array(count * 3), 3))
    const base = new Points(baseGeometry, material())
    base.frustumCulled = false
    const topGeometry = new BufferGeometry()
    const top = new Points(topGeometry, material())
    top.frustumCulled = false
    sceneGraph.add(base, top)
    const controls = new OrbitControls(camera, canvas)
    controls.enableDamping = false
    controls.screenSpacePanning = true
    controls.enableRotate = dims === 3
    if (dims === 2) { controls.mouseButtons.LEFT = MOUSE.PAN; controls.touches.ONE = TOUCH.PAN }
    controls.zoomSpeed = 0.9
    let frame = 0, closed = false
    const render = () => {
      if (closed || frame) return
      frame = requestAnimationFrame(() => { frame = 0; renderer.render(sceneGraph, camera) })
    }
    controls.addEventListener('change', render)
    const resize = () => {
      const width = Math.max(1, element.clientWidth), height = Math.max(1, element.clientHeight)
      renderer.setSize(width, height, false); camera.aspect = width / height; camera.updateProjectionMatrix(); render()
    }
    const observer = new ResizeObserver(resize)
    observer.observe(element)
    resize(); home()
    const project = (): Float32Array => {
      camera.updateMatrixWorld()
      return projectToScreen(positions, camera.projectionMatrix.clone().multiply(camera.matrixWorldInverse).elements, element.clientWidth, element.clientHeight)
    }
    const setSelection = (rows: number[], palette: Float32Array) => {
      const picked = new Float32Array(rows.length * 3), own = new Float32Array(rows.length * 3)
      rows.forEach((row, at) => {
        picked.set(positions.subarray(row * 3, row * 3 + 3), at * 3)
        own.set(palette.subarray(row * 3, row * 3 + 3), at * 3)
      })
      topGeometry.setAttribute('position', new BufferAttribute(picked, 3))
      topGeometry.setAttribute('color', new BufferAttribute(own, 3))
      render()
    }
    scene.current = { base, top, positions, setSelection }
    three.current = { render, project, resetView: home }
    return () => {
      closed = true; cancelAnimationFrame(frame); observer.disconnect(); controls.dispose()
      baseGeometry.dispose(); topGeometry.dispose(); base.material.dispose(); top.material.dispose(); sprite.dispose()
      renderer.dispose(); renderer.forceContextLoss(); canvas.remove()
      scene.current = null; three.current = null
    }
  }, [projection])

  // Colours and selection: the base cloud is dimmed while a selection exists, the selection is drawn on top at full colour.
  useEffect(() => {
    const current = scene.current
    if (!current || !projection) return
    const rows: number[] = []
    for (const id of selected) { const row = index.get(id); if (row !== undefined) rows.push(row) }
    const palette = colouring.rgb
    const attribute = current.base.geometry.getAttribute('color') as BufferAttribute
    const shown = attribute.array as Float32Array
    if (rows.length) {
      for (let at = 0; at < palette.length; at += 3) {
        shown[at] = palette[at] * 0.32 + DIM.r * 0.68; shown[at + 1] = palette[at + 1] * 0.32 + DIM.g * 0.68; shown[at + 2] = palette[at + 2] * 0.32 + DIM.b * 0.68
      }
    } else shown.set(palette)
    attribute.needsUpdate = true
    current.setSelection(rows, palette)
    three.current?.render()
  }, [colouring, selected, index, projection])

  useEffect(() => {
    const current = scene.current
    if (!current) return
    ;(current.base.material as PointsMaterial).size = pointSize
    ;(current.top.material as PointsMaterial).size = pointSize + 2
    three.current?.render()
  }, [pointSize, projection])

  const gesture = useRef<{ path: Array<{ x: number; y: number }>; start: { x: number; y: number }; time: number } | null>(null)
  const local = (event: React.PointerEvent) => {
    const bounds = event.currentTarget.getBoundingClientRect()
    return { x: event.clientX - bounds.left, y: event.clientY - bounds.top }
  }
  function finish(event: React.PointerEvent<HTMLDivElement>) {
    const start = gesture.current
    gesture.current = null
    setLasso([])
    if (!start || !projection || !three.current) return
    const end = local(event)
    const path = [...start.path, end]
    const screen = three.current.project()
    // How far the gesture strayed from where it began; a closed lasso ends beside its start, so end-to-start distance would not do.
    const moved = strayed(path)
    if (mode === 'lasso' && path.length > 3 && moved > 7) {
      onSelect(rowsInPolygon(screen, path).map(row => projection.ids[row]), event.shiftKey ? 'add' : 'replace')
    } else if (moved < 5 && performance.now() - start.time < 500) {
      const nearest = nearestRow(screen, end.x, end.y, 13)
      if (nearest >= 0) onInspect(projection.ids[nearest])
    }
  }

  const bulk = bulkOf(artifact)
  const provenance = artifact.provenance?.processor_provenance as { backend?: string; method?: string } | undefined
  const plotted = projection?.ids.length ?? 0
  const selectedLoaded = records.filter(record => selected.has(record.id))

  return (
    <div className="map">
      <div
        className="map-stage" ref={stage} style={{ position: 'relative', touchAction: 'none' }}
        onPointerDown={event => {
          if (event.button !== 0) return
          const point = local(event)
          gesture.current = { path: [point], start: point, time: performance.now() }
        }}
        onPointerMove={event => {
          const current = gesture.current
          if (!current || mode !== 'lasso') return
          current.path.push(local(event)); setLasso([...current.path])
        }}
        onPointerUp={finish}
        onPointerCancel={() => { gesture.current = null; setLasso([]) }}
        role="img" aria-label={`${projection?.dims ?? ''}D projection ${artifact.kind} with ${plotted} points. ${mode === 'lasso' ? 'Draw a lasso to select; hold Shift to add.' : 'Drag to rotate, scroll to zoom.'} Click a point to inspect it.`}
      >
        {/* The lasso layer sits above the canvas and only captures the pointer in lasso mode, so rotation keeps working otherwise. */}
        {mode === 'lasso' && <div style={{ position: 'absolute', inset: 0, cursor: 'crosshair', zIndex: 2 }} />}
        {lasso.length > 1 && (
          <svg className="lasso" aria-hidden style={{ zIndex: 3 }}>
            <polyline points={lasso.map(point => `${point.x},${point.y}`).join(' ')} fill="rgba(37,99,235,.08)" stroke="#2563eb" strokeWidth="1.5" />
          </svg>
        )}
        {!projection && !error && <div style={{ position: 'absolute', inset: 0, display: 'grid', placeContent: 'center' }}><Spinner label="Loading projection…" /></div>}
        {error && <div style={{ position: 'absolute', inset: 16, zIndex: 4 }}><Notice tone="error">{error}</Notice></div>}
        <div className="map-tools" style={{ zIndex: 4 }}>
          <button type="button" className={`btn sm${mode === 'rotate' ? ' primary' : ''}`} onClick={() => setMode('rotate')}>{projection?.dims === 2 ? 'Pan' : 'Rotate'}</button>
          <button type="button" className={`btn sm${mode === 'lasso' ? ' primary' : ''}`} onClick={() => setMode('lasso')}>Lasso</button>
          <button type="button" className="btn sm icon" onClick={() => three.current?.resetView()} aria-label="Reset view"><Icon.Reset size={13} /></button>
          <input type="range" min={1} max={8} step={0.5} value={pointSize} onChange={event => setPointSize(Number(event.target.value))} aria-label="Point size" style={{ width: 70 }} />
        </div>
        {(sources.length > 0) && (
          <div style={{ position: 'absolute', top: 12, left: 100, zIndex: 4 }}>
            <select className="select" style={{ width: 230 }} value={source ? `${source.artifact.id}:${source.column}` : 'none'} aria-label="Colour by result"
              onChange={event => setSourceKey(event.target.value === 'none' ? 'none' : event.target.value)}>
              {sources.map(item => <option key={`${item.artifact.id}:${item.column}`} value={`${item.artifact.id}:${item.column}`}>{item.artifact.kind} · {item.column.replaceAll('_', ' ')}</option>)}
              <option value="none">{colourField ? `Field: ${colourField.name}` : 'One colour'}</option>
            </select>
          </div>
        )}
        {colouring.legend.length > 0 && (
          <div className="map-legend" style={{ zIndex: 4 }}>
            <h4 className="truncate">{source && labels ? `${source.artifact.kind} · ${source.column.replaceAll('_', ' ')}` : colourField?.name}</h4>
            {colouring.legend.map(entry => (
              <div className="lg" key={entry.label}>
                <span className="dot" style={{ background: entry.colour }} />
                {entry.ids
                  ? <button type="button" className="linkish truncate" title="Select this group" onClick={() => onSelect(entry.ids!, 'replace')}>{entry.label} · {(entry.count ?? 0).toLocaleString()}</button>
                  : <span className="truncate" title={entry.label}>{entry.label}{entry.count !== undefined ? ` · ${entry.count.toLocaleString()}` : ''}</span>}
              </div>
            ))}
          </div>
        )}
      </div>
      <div className="map-strip">
        <div className="row" style={{ fontSize: 'var(--fs-sm)', color: 'var(--text-muted)', flexWrap: 'wrap' }}>
          <strong style={{ color: 'var(--text)' }}>{plotted.toLocaleString()} plotted</strong>
          <span className="sep">·</span><span>{projection?.dims ?? '–'}D {provenance?.method ?? artifact.kind}{provenance?.backend ? ` on ${provenance.backend}` : ''}</span>
          {bulk && <><span className="sep">·</span><span>{resultCount(artifact).toLocaleString()} rows from arrays</span></>}
          {matchedCount !== null && <><span className="sep">·</span><span>{matchedCount.toLocaleString()} match the filter</span></>}
          <span className="sep">·</span><span>{shortId(artifact.run_id ?? artifact.id, 8)}</span>
          {colouring.note && <><span className="sep">·</span><span>{colouring.note}</span></>}
        </div>
        <SelectionStrip records={selectedLoaded} total={totalSelected ?? selected.size} onInspect={onInspect} onOpen={onOpen} />
      </div>
    </div>
  )
}
