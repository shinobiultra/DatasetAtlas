import { displayUrl, safeViewEnabled } from '../lib/display'
import { useEffect, useRef, useState } from 'react'
import type { Asset, Record as AtlasRecord } from '../generated'
import { provider, publicUrl } from '../provider'
import { display } from '../lib/format'
import * as Icon from './Icons'

export type Box = { box: [number, number, number, number]; class: string; score: number }
export type Overlay = {
  assetId: string
  width: number
  height: number
  boxes: Box[]
  run: string
  kind: string
  threshold: unknown
  visible: boolean
}

export function assetUrl(asset: Asset): string | null {
  if (!asset.uri) return null
  return provider.mode === 'static' ? publicUrl(asset.uri) : asset.uri
}

export function imageAssets(record: AtlasRecord): Asset[] {
  return (record.assets ?? []).filter(asset => asset.modality === 'image')
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
          aria-label={`${overlay.boxes.length} detections from run ${overlay.run}, extraction threshold ${display(overlay.threshold)}`}
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
  if (asset.modality === 'audio') return <audio src={url} controls={controls} preload="none" aria-label={alt ?? `Audio asset ${asset.id}`} style={{ width: '92%' }} onError={() => setFailed(true)} />
  if (asset.modality === 'video') return <video src={url} controls={controls} preload="metadata" aria-label={alt ?? `Video asset ${asset.id}`} onError={() => setFailed(true)} />
  if (asset.modality !== 'image') {
    return <div className="fallback"><Icon.Layers size={20} /><span>{asset.modality} record</span><small className="mono wrap-any">{asset.id}</small></div>
  }

  const hiddenBySafeView = safeViewEnabled() && overlays.some(overlay => overlay.assetId === asset.id && overlay.visible)
  const expected = (safeViewEnabled() ? [] : overlays).filter(overlay => overlay.assetId === asset.id && overlay.visible)
  const misaligned = natural ? expected.filter(overlay => overlay.width !== natural.width || overlay.height !== natural.height) : []
  return (
    <>
      <img
        src={displayUrl(url)} alt={alt ?? ''} loading="lazy" decoding="async"
        style={fit === 'actual' ? { width: natural?.width, height: natural?.height, maxWidth: 'none', maxHeight: 'none' } : { objectFit: fit }}
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
  const representation = safeViewEnabled() ? 'Safe-view display derivative' : asset.representation ?? 'original'
  return <span className="tag" title={`Asset ${asset.id}`}>{representation === 'original' ? 'Original' : representation}</span>
}
