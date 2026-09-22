import { displayUrl } from '../lib/display'
import { useEffect, useMemo, useState } from 'react'
import type { Artifact, Record as AtlasRecord } from '../generated'
import { recordHeadline, shortId } from '../lib/format'
import { AssetView, assetUrl, imageAssets, primaryAsset } from '../ui/MediaView'
import { detectorStates } from './model'
import { Tag } from '../ui/primitives'
import { useKey, inEditable } from '../lib/hooks'
import * as Icon from '../ui/Icons'

export type Fit = 'fit' | 'actual'

/** Mockup 4: the media owns the centre; browsing order and similarity stay labelled apart. */
export function FocusedInspector({ records, index, artifacts, onIndex, onClose, onInspect, matchedCount }: {
  records: AtlasRecord[]
  index: number
  artifacts: Artifact[]
  onIndex: (index: number) => void
  onClose: () => void
  onInspect: (id: string) => void
  matchedCount: number | null
}) {
  const record = records[index]
  const [fit, setFit] = useState<Fit>('fit')
  const [assetIndex, setAssetIndex] = useState(0)
  const [showOverlays, setShowOverlays] = useState(true)
  useEffect(() => { setAssetIndex(0) }, [record?.id])

  const runs = useMemo(() => (record ? detectorStates(artifacts, record.id) : []), [artifacts, record])
  const overlays = useMemo(() => runs.flatMap(state => state.overlays).map(overlay => ({ ...overlay, visible: showOverlays })), [runs, showOverlays])
  const images = record ? imageAssets(record) : []
  const asset = images[assetIndex] ?? (record ? primaryAsset(record) : null)

  useKey(event => {
    if (inEditable(event.target)) return
    if (event.key === 'Escape') { event.preventDefault(); onClose() }
    if (event.key === 'ArrowLeft' && index > 0) { event.preventDefault(); onIndex(index - 1) }
    if (event.key === 'ArrowRight' && index < records.length - 1) { event.preventDefault(); onIndex(index + 1) }
  }, [index, records.length, onIndex, onClose])

  if (!record) return null
  const detections = runs.reduce((total, state) => total + state.overlays.reduce((count, overlay) => count + overlay.boxes.length, 0), 0)

  return (
    <div className="focus">
      <div className="focus-bar">
        <button type="button" className="btn icon" onClick={() => onIndex(index - 1)} disabled={index === 0} aria-label="Previous sample"><Icon.ChevronLeft size={15} /></button>
        <button type="button" className="btn icon" onClick={() => onIndex(index + 1)} disabled={index >= records.length - 1} aria-label="Next sample"><Icon.ChevronRight size={15} /></button>
        <span className="pos">
          {index + 1} / {records.length.toLocaleString()} loaded
          {matchedCount !== null && matchedCount > records.length && <span style={{ color: 'var(--text-faint)' }}> of {matchedCount.toLocaleString()} matching</span>}
        </span>
        <span className="spacer" />
        {images.length > 1 && (
          <label className="row" style={{ gap: 6, fontSize: 'var(--fs-sm)', color: 'var(--text-muted)' }}>
            Image
            <select className="select" style={{ width: 92, height: 28 }} value={assetIndex} onChange={event => setAssetIndex(Number(event.target.value))} aria-label="Choose image in this record">
              {images.map((_, position) => <option key={position} value={position}>{position + 1} of {images.length}</option>)}
            </select>
          </label>
        )}
        {runs.length > 0 && (
          <label className="row" style={{ gap: 6, fontSize: 'var(--fs-sm)', color: 'var(--text-muted)' }}>
            <input type="checkbox" checked={showOverlays} onChange={event => setShowOverlays(event.target.checked)} />
            Boxes ({detections})
          </label>
        )}
        <div className="segmented">
          <button type="button" aria-pressed={fit === 'fit'} onClick={() => setFit('fit')}>Fit</button>
          <button type="button" aria-pressed={fit === 'actual'} onClick={() => setFit('actual')}>Actual size</button>
        </div>
        <button type="button" className="btn" onClick={onClose}><Icon.Close size={14} />Close</button>
      </div>

      <div className="focus-stage">
        {asset ? (
          <div className={`focus-frame${fit === 'actual' ? ' actual' : ''}`}>
            <AssetView asset={asset} overlays={overlays} controls fit={fit === 'actual' ? 'actual' : 'contain'} alt={`Asset ${assetIndex + 1} of record ${record.id}`} />
          </div>
        ) : (
          <div className="focus-text">{recordHeadline(record)}</div>
        )}
      </div>

      <div className="focus-below">
        {record.question && <div className="focus-question"><strong>Q.</strong> {record.question}</div>}
        {!record.question && record.text && asset && <div className="focus-question clamp-3">{record.text}</div>}
        <div className="filmstrip-head">
          <strong style={{ fontSize: 'var(--fs-md)' }}>Matching samples</strong>
          <Tag>current query order</Tag>
          <span className="hint" style={{ fontSize: 'var(--fs-sm)' }}>Neighbours in browsing order, not a similarity result.</span>
        </div>
        <div className="filmstrip">
          {records.slice(Math.max(0, index - 12), index + 24).map((item, offset) => {
            const position = Math.max(0, index - 12) + offset
            const thumb = primaryAsset(item)
            const url = thumb ? assetUrl(thumb) : null
            return (
              <button
                type="button" key={item.id} aria-current={position === index}
                onClick={() => { onIndex(position); onInspect(item.id) }}
                title={recordHeadline(item)} aria-label={`Sample ${position + 1}: ${shortId(item.id, 14)}`}
              >
                {url && thumb?.modality === 'image'
                  ? <img src={displayUrl(url)} alt="" loading="lazy" onError={event => { event.currentTarget.style.visibility = 'hidden' }} />
                  : <span className="tph clamp-3">{recordHeadline(item)}</span>}
              </button>
            )
          })}
        </div>
      </div>
    </div>
  )
}
