import { useEffect, useRef, useState } from 'react'
import { Box3, Color, HemisphereLight, LoadingManager, PerspectiveCamera, Scene, Vector3, WebGLRenderer, type Object3D, type Material, type Texture } from 'three'
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'
import { verifyGlbForViewer } from '../lib/glb'

/** Inspect one local original. Grid cards never create hundreds of GPU contexts. */
export default function ModelView({ url, label }: { url: string; label: string }) {
  const host = useRef<HTMLDivElement>(null)
  const [error, setError] = useState<string | null>(null)
  const [ready, setReady] = useState(false)
  useEffect(() => {
    setError(null); setReady(false)
    const element = host.current
    if (!element) return
    const abort = new AbortController()
    let renderer: WebGLRenderer | undefined, controls: OrbitControls | undefined, observer: ResizeObserver | undefined
    let model: Object3D | undefined, frame = 0, closed = false
    const scene = new Scene(); scene.background = new Color('#e8edf3')
    const camera = new PerspectiveCamera(45, 1, 0.01, 1000)
    const dispose = () => {
      closed = true; abort.abort(); cancelAnimationFrame(frame); observer?.disconnect(); controls?.dispose()
      model?.traverse(object => {
        const mesh = object as Object3D & { geometry?: { dispose: () => void }; material?: Material | Material[] }
        mesh.geometry?.dispose()
        for (const material of mesh.material ? (Array.isArray(mesh.material) ? mesh.material : [mesh.material]) : []) {
          for (const value of Object.values(material)) if ((value as Texture | null)?.isTexture) (value as Texture).dispose()
          material.dispose()
        }
      })
      renderer?.dispose(); renderer?.forceContextLoss(); renderer?.domElement.remove()
    }
    const render = () => {
      if (closed || frame) return
      frame = requestAnimationFrame(() => { frame = 0; renderer?.render(scene, camera) })
    }
    void (async () => {
      try {
        const response = await fetch(url, { signal: abort.signal, credentials: 'same-origin' })
        if (!response.ok) throw new Error(`Original model request failed (${response.status})`)
        const announced = Number(response.headers.get('content-length') ?? 0)
        if (announced > 32_000_000) throw new Error('Model exceeds the 32 MB viewer limit')
        const reader = response.body?.getReader()
        if (!reader) throw new Error('Original model stream is unavailable')
        const blocks: Uint8Array[] = []; let bytes = 0
        while (true) {
          const next = await reader.read(); if (next.done) break
          bytes += next.value.byteLength
          if (bytes > 32_000_000) { await reader.cancel(); throw new Error('Model exceeds the 32 MB viewer limit') }
          blocks.push(next.value)
        }
        const data = new Uint8Array(bytes); let offset = 0
        for (const block of blocks) { data.set(block, offset); offset += block.byteLength }
        verifyGlbForViewer(data.buffer)
        const manager = new LoadingManager()
        manager.setURLModifier(resource => {
          if (!resource.startsWith('blob:') && !resource.startsWith('data:image/')) throw new Error('Model refers to an external resource')
          return resource
        })
        const gltf = await new GLTFLoader(manager).parseAsync(data.buffer, '')
        model = gltf.scene
        if (closed) { dispose(); return }
        const box = new Box3().setFromObject(model); const size = box.getSize(new Vector3()).length()
        if (!Number.isFinite(size) || size <= 0) throw new Error('Model has no finite visible geometry')
        const centre = box.getCenter(new Vector3()); model.position.sub(centre)
        scene.add(model); scene.add(new HemisphereLight(0xffffff, 0x657080, 3))
        renderer = new WebGLRenderer({ antialias: true, powerPreference: 'high-performance' })
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
        renderer.domElement.setAttribute('aria-label', label); renderer.domElement.setAttribute('role', 'img')
        renderer.domElement.dataset.atlasModel = 'original-glb'
        element.appendChild(renderer.domElement)
        camera.near = size / 1000; camera.far = size * 100; camera.position.set(size * 0.8, size * 0.5, size * 0.8)
        controls = new OrbitControls(camera, renderer.domElement); controls.addEventListener('change', render)
        controls.update()
        observer = new ResizeObserver(() => {
          const width = Math.max(1, element.clientWidth), height = Math.max(240, element.clientHeight)
          renderer?.setSize(width, height, false); camera.aspect = width / height; camera.updateProjectionMatrix(); render()
        })
        observer.observe(element); setReady(true); render()
      } catch (failure) {
        if (!closed) { setReady(false); setError(failure instanceof Error ? failure.message : String(failure)); dispose() }
      }
    })()
    return dispose
  }, [url, label])
  return <div ref={host} style={{ width: '100%', height: '100%', minHeight: 280, position: 'relative' }}>
    {!ready && !error && <span className="overlay-note">Loading original 3D model…</span>}
    {error && <div className="fallback"><span>3D view unavailable</span><small>{error}</small><a href={url} download>Download original GLB</a></div>}
    {ready && <span className="overlay-note">Original GLB · drag to rotate · scroll to zoom</span>}
  </div>
}
