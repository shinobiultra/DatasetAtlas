import { browserRenderRequired, displayUrl, safeViewEnabled } from '../lib/display'
import { lazy, Suspense, useEffect, useRef, useState } from 'react'
import type { Asset, Record as AtlasRecord } from '../generated'
import { provider, publicUrl } from '../provider'
import { display } from '../lib/format'
import * as Icon from './Icons'

const ModelView = lazy(() => import('./ModelView'))

export type Box = { box: [number, number, number, number]; class: string; score: number }
export type Overlay = {
  assetId: string
  width: number
  height: number
  boxes: Box[]
  run: string
  kind: string
  threshold: unknown
  extractionThreshold?: unknown
  visible: boolean
}

export function assetUrl(asset: Asset): string | null {
  if (!asset.uri) return null
  return provider.mode === 'static' ? publicUrl(asset.uri) : asset.uri
}

export function imageAssets(record: AtlasRecord): Asset[] {
  return (record.assets ?? []).filter(asset => asset.modality === 'image')
}

export function assetLabel(asset: Asset, index = 0): string {
  const condition = asset.metadata?.condition
  if (typeof condition === 'string' && condition.trim()) return condition
  const role = asset.metadata?.source_role ?? asset.metadata?.role
  if (typeof role === 'string' && role.trim()) {
    return ({ ref: 'Reference', p0: 'Patch 0', p1: 'Patch 1' } as Record<string, string>)[role] ?? role
  }
  const kind = asset.modality === 'audio' ? 'Audio' : asset.modality === 'video' ? 'Video' : asset.modality === 'model3d' ? '3D model' : 'Image'
  return `${kind} ${index + 1}`
}

export function primaryAsset(record: AtlasRecord): Asset | null {
  return (record.assets ?? []).find(asset => asset.modality === 'image' && asset.uri)
    ?? (record.assets ?? []).find(asset => asset.uri)
    ?? (record.assets ?? [])[0]
    ?? null
}

const PALETTE = ['#2563eb', '#0f8a6a', '#c2620d', '#8b5cf6', '#d14343', '#0e7490', '#a16207', '#be185d']
export function classColour(name: string): string {
  let hash = 0
  for (const character of name) hash = (Math.imul(hash, 31) + character.charCodeAt(0)) | 0
  return PALETTE[Math.abs(hash) % PALETTE.length]
}

/** Draws detector boxes in the detector's own pixel space, aligned by intrinsic size. */
function BoxLayer({ overlays, natural, highlight }: {
  overlays: Overlay[]; natural: { width: number; height: number } | null; highlight?: string | null
}) {
  if (!natural) return null
  const aligned = overlays.filter(overlay => overlay.visible && overlay.width === natural.width && overlay.height === natural.height)
  if (!aligned.length) return null
  return (
    <>
      {aligned.map(overlay => (
        <svg
          key={overlay.run} data-run-id={overlay.run} className="box-layer" viewBox={`0 0 ${overlay.width} ${overlay.height}`}
          preserveAspectRatio="xMidYMid meet" role="img"
          aria-label={`${overlay.boxes.length} detections from run ${overlay.run}, extraction threshold ${display(overlay.extractionThreshold ?? overlay.threshold)}, display threshold ${display(overlay.threshold)}`}
        >
          {overlay.boxes.map((detection, index) => {
            const key = `${overlay.run}:${index}`
            const colour = classColour(detection.class)
            const dim = highlight != null && highlight !== key
            const [x0, y0, x1, y1] = detection.box
            return (
              <g key={key} opacity={dim ? 0.3 : 1}>
                <rect x={x0} y={y0} width={Math.max(0, x1 - x0)} height={Math.max(0, y1 - y0)} fill="none" stroke={colour} strokeWidth={highlight === key ? 4 : 2.5} />
                <rect x={x0} y={Math.max(0, y0 - 18)} width={Math.max(46, (detection.class.length + 5) * 8)} height={18} fill={colour} />
                <text x={x0 + 4} y={Math.max(13, y0 - 5)} fontSize="13" fill="#fff" fontFamily="system-ui, sans-serif">
                  {detection.class} {detection.score.toFixed(2)}
                </text>
              </g>
            )
          })}
        </svg>
      ))}
    </>
  )
}

/** One asset, honest about what representation is on screen and whether overlays align. */
export function AssetView({ asset, overlays = [], controls = false, highlight, fit = 'contain', onNatural, alt }: {
  asset: Asset
  overlays?: Overlay[]
  controls?: boolean
  highlight?: string | null
  fit?: 'contain' | 'cover' | 'actual'
  onNatural?: (size: { width: number; height: number }) => void
  alt?: string
}) {
  const url = assetUrl(asset)
  const [failed, setFailed] = useState(false)
  const [natural, setNatural] = useState<{ width: number; height: number } | null>(null)
  const notified = useRef(false)
  useEffect(() => { setFailed(false); setNatural(null); notified.current = false }, [url])

  if (!url && asset.text) return <div className="textprev">{asset.text}</div>
  if (!url) {
    return (
      <div className="fallback">
        <Icon.Image size={20} />
        <span>{asset.metadata?.availability === 'absent_from_pinned_release' ? 'Listed by the source, absent from this release' : `${asset.modality} representation is not available here`}</span>
        <small className="mono wrap-any">{String(asset.metadata?.source_path ?? asset.id)}</small>
      </div>
    )
  }
  if (failed) {
    return (
      <div className="fallback">
        <Icon.Warning size={20} />
        <span>Media could not be loaded</span>
        <small>The record is still here; only its {asset.modality} failed to load.</small>
      </div>
    )
  }
  if (asset.modality === 'audio') return <audio src={url} controls={controls} preload="none" aria-label={alt ?? `Audio asset ${asset.id}`} style={{ width: '100%' }} onError={() => setFailed(true)} />
  if (asset.modality === 'video') {
    const rendered = browserRenderRequired(asset) && provider.mode === 'workbench' && url.startsWith('/api/v1/media/')
    const videoUrl = rendered
      ? `${url}${url.includes('?') ? '&' : '?'}representation=display` : url
    return <><video src={videoUrl} controls={controls} preload="metadata" aria-label={alt ?? `Video asset ${asset.id}`} onError={() => setFailed(true)} />
      {rendered && <small className="overlay-note">Lossless video display; native audio copied. Original AVI remains available.</small>}</>
  }
  if (asset.modality === 'model3d') return controls
    ? <Suspense fallback={<div className="fallback">Loading 3D viewer…</div>}><ModelView url={url} label={alt ?? `Original 3D model ${asset.id}`} /></Suspense>
    : <div className="fallback"><Icon.Layers size={28} /><span>Original 3D object</span><small>Open to rotate and inspect</small></div>
  if (asset.modality !== 'image') {
    return <div className="fallback"><Icon.Layers size={20} /><span>{asset.modality} record</span><small className="mono wrap-any">{asset.id}</small></div>
  }

  const browserRender = browserRenderRequired(asset)
  const derivative = safeViewEnabled() || browserRender
  const hiddenBySafeView = derivative && overlays.some(overlay => overlay.assetId === asset.id && overlay.visible)
  const expected = (derivative ? [] : overlays).filter(overlay => overlay.assetId === asset.id && overlay.visible)
  const misaligned = natural ? expected.filter(overlay => overlay.width !== natural.width || overlay.height !== natural.height) : []
  return (
    <>
      <img
        src={displayUrl(url, browserRender)} alt={alt ?? ''} loading="lazy" decoding="async"
        style={{ ...(fit === 'actual' ? { width: natural?.width, height: natural?.height, maxWidth: 'none', maxHeight: 'none' } : { objectFit: fit }), ...(asset.metadata?.binary_label_mask === true ? { filter: 'brightness(255)' } : {}) }}
        onLoad={event => {
          const size = { width: event.currentTarget.naturalWidth, height: event.currentTarget.naturalHeight }
          setNatural(size)
          if (!notified.current) { notified.current = true; onNatural?.(size) }
        }}
        onError={() => setFailed(true)}
      />
      <BoxLayer overlays={expected} natural={natural} highlight={highlight} />
      {hiddenBySafeView && <span className="overlay-note">Detector boxes are not drawn over a safe-view derivative</span>}
      {misaligned.length > 0 && (
        <span className="overlay-note">
          Overlay hidden: {misaligned[0].width}×{misaligned[0].height} detector input differs from this {natural?.width}×{natural?.height} representation
        </span>
      )}
    </>
  )
}

/** The representation label a researcher needs before trusting what they see. */
export function RepresentationTag({ asset }: { asset: Asset }) {
  if (asset.metadata?.availability === 'absent_from_pinned_release') return <span className="tag">Unavailable in source release</span>
  if (asset.metadata?.binary_label_mask === true) return <span className="tag" title="The display maps label 1 to white. Original PNG label values remain 0/1 for download, analysis and export.">Binary mask · contrast view</span>
  if (asset.modality === 'video' && browserRenderRequired(asset)) return <>
    <span className="tag" title="Decoded video frames are checked for exact parity; native MP3/AAC audio packets are copied. The original AVI remains the source.">Lossless video display</span>
    <a className="btn sm" href={assetUrl(asset) ?? undefined} target="_blank" rel="noreferrer">Open original AVI</a>
  </>
  if (browserRenderRequired(asset)) return <>
    <span className="tag" title="A PNG display derivative at bounded resolution. The original TIFF bytes remain the source for analysis and export.">TIFF display derivative</span>
    <a className="btn sm" href={assetUrl(asset) ?? undefined} target="_blank" rel="noreferrer">Open original TIFF</a>
  </>
  if (!safeViewEnabled() && ['compressed_avif', 'optimized_on_demand'].includes(asset.representation ?? '')) return <>
    <span className="tag" title="AVIF browsing copy at the source pixel dimensions, retaining the original if conversion is unsuitable or larger. Model inputs use the original.">{asset.representation === 'compressed_avif' ? 'Compressed · full resolution' : 'Full-resolution browsing copy'}</span>
    {typeof asset.metadata?.original_uri === 'string' && asset.metadata.original_uri.startsWith('/api/v1/media/') &&
      <a className="btn sm" href={asset.metadata.original_uri} target="_blank" rel="noreferrer">Open original</a>}
  </>
  const representation = safeViewEnabled() ? 'Safe-view display derivative' : asset.representation ?? 'original'
  return <span className="tag" title={`Asset ${asset.id}`}>{representation === 'original' ? 'Original' : representation === 'lossless_mask_render' ? 'Lossless mask view' : representation}</span>
}
