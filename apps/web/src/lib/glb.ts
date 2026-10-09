/** Bound decoded allocations before GLTFLoader, including zero-filled and sparse accessors. */
interface View { buffer?: number; byteOffset?: number; byteLength: number; byteStride?: number }
interface Accessor {
  count: number; type: string; componentType: number; bufferView?: number; byteOffset?: number
  sparse?: { count: number; indices: { bufferView: number; byteOffset?: number; componentType: number }; values: { bufferView: number; byteOffset?: number } }
}
interface Document {
  asset?: { version: string }; buffers?: { byteLength: number; uri?: string }[]; bufferViews?: View[]; accessors?: Accessor[]
  extensionsRequired?: string[]; images?: { uri?: string; bufferView?: number }[]; nodes?: { children?: number[]; mesh?: number; skin?: number; extensions?: Record<string, unknown> }[]; scenes?: { nodes?: number[] }[]
  meshes?: { primitives?: { indices?: number; attributes?: { POSITION?: number } }[] }[]; skins?: { joints?: number[] }[]
}
const widths: Record<number, number> = { 5120: 1, 5121: 1, 5122: 2, 5123: 2, 5125: 4, 5126: 4 }
const sizes: Record<string, number> = { SCALAR: 1, VEC2: 2, VEC3: 3, VEC4: 4, MAT2: 4, MAT3: 9, MAT4: 16 }
const supported = new Set(['KHR_materials_unlit', 'KHR_texture_transform', 'KHR_materials_clearcoat', 'KHR_materials_transmission',
  'KHR_materials_ior', 'KHR_materials_specular', 'KHR_materials_sheen', 'KHR_materials_volume', 'KHR_materials_emissive_strength',
  'KHR_materials_iridescence', 'KHR_lights_punctual', 'KHR_materials_anisotropy', 'KHR_materials_dispersion'])
function requireValid(condition: unknown, message: string): asserts condition { if (!condition) throw new Error(message) }
function integer(value: unknown): value is number { return Number.isSafeInteger(value) }
function texturePixels(data: Uint8Array): number {
  const view = new DataView(data.buffer, data.byteOffset, data.byteLength)
  if (data.length >= 24 && view.getUint32(0) === 0x89504e47 && view.getUint32(4) === 0x0d0a1a0a && view.getUint32(12) === 0x49484452)
    return view.getUint32(16) * view.getUint32(20)
  requireValid(data.length >= 4 && data[0] === 0xff && data[1] === 0xd8, 'Unsupported embedded texture')
  let offset = 2
  while (offset + 4 <= data.length) {
    requireValid(data[offset++] === 0xff, 'Invalid embedded JPEG texture')
    while (data[offset] === 0xff) offset++
    const marker = data[offset++]
    if (marker === 0xd9 || marker === 0xda) break
    if (marker === 0x01 || (marker >= 0xd0 && marker <= 0xd7)) continue
    requireValid(offset + 2 <= data.length, 'Truncated embedded JPEG texture')
    const length = view.getUint16(offset)
    requireValid(length >= 2 && offset + length <= data.length, 'Invalid embedded JPEG texture length')
    if ([0xc0, 0xc1, 0xc2, 0xc3, 0xc5, 0xc6, 0xc7, 0xc9, 0xca, 0xcb, 0xcd, 0xce, 0xcf].includes(marker)) {
      requireValid(length >= 7, 'Invalid embedded JPEG dimensions')
      return view.getUint16(offset + 3) * view.getUint16(offset + 5)
    }
    offset += length
  }
  throw new Error('Embedded JPEG has no bounded dimensions')
}
export function verifyGlbForViewer(data: ArrayBuffer): { decodedAccessorBytes: number } {
  requireValid(data.byteLength >= 20 && data.byteLength <= 32_000_000, 'Model exceeds the viewer byte limit')
  const header = new DataView(data)
  requireValid(header.getUint32(0, true) === 0x46546c67 && header.getUint32(4, true) === 2 && header.getUint32(8, true) === data.byteLength, 'Invalid GLB header')
  let offset = 12; const chunks: { kind: number; start: number; size: number }[] = []
  while (offset < data.byteLength) {
    requireValid(offset + 8 <= data.byteLength, 'Truncated GLB chunk')
    const size = header.getUint32(offset, true), kind = header.getUint32(offset + 4, true); offset += 8
    requireValid(size % 4 === 0 && offset + size <= data.byteLength, 'Invalid GLB chunk length')
    chunks.push({ kind, start: offset, size }); offset += size
  }
  requireValid(chunks.length > 0 && chunks.length <= 2 && chunks[0].kind === 0x4e4f534a && (chunks.length === 1 || chunks[1].kind === 0x004e4942), 'Unsupported GLB chunk layout')
  requireValid(chunks[0].size <= 8_000_000, 'Model JSON exceeds the viewer limit')
  const native = JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(new Uint8Array(data, chunks[0].start, chunks[0].size))) as Document
  requireValid(native.asset?.version === '2.0' && !(native.extensionsRequired ?? []).some(name => !supported.has(name)), 'Unsupported GLB version or decoder')
  const buffers = native.buffers ?? [], views = native.bufferViews ?? [], accessors = native.accessors ?? []
  const binary = chunks[1] ? new Uint8Array(data, chunks[1].start, chunks[1].size) : new Uint8Array()
  requireValid(buffers.length === 1 && buffers[0].uri === undefined && integer(buffers[0].byteLength) && buffers[0].byteLength >= 0 && buffers[0].byteLength <= binary.length, 'Model requires one embedded buffer')
  for (const view of views) requireValid((view.buffer ?? 0) === 0 && integer(view.byteOffset ?? 0) && (view.byteOffset ?? 0) >= 0 && integer(view.byteLength) && view.byteLength >= 0 && (view.byteOffset ?? 0) + view.byteLength <= buffers[0].byteLength, 'Invalid GLB buffer view')
  const viewBytes = views.reduce((sum, view) => sum + view.byteLength, 0)
  requireValid(viewBytes <= 64_000_000, 'Model exceeds the decoded buffer view allocation limit')
  const checkRange = (index: number | undefined, start: number, count: number, element: number, alignment: number, allowStride = true) => {
    requireValid(integer(index) && index >= 0 && index < views.length, 'Invalid GLB accessor view')
    const view = views[index], stride = allowStride ? (view.byteStride ?? element) : element
    requireValid(integer(start) && start >= 0 && start % alignment === 0 && integer(stride) && stride >= element && (view.byteStride === undefined || (allowStride && stride >= 4 && stride <= 252 && stride % 4 === 0)), 'Invalid GLB accessor layout')
    requireValid(start + (count === 0 ? 0 : (count - 1) * stride + element) <= view.byteLength, 'GLB accessor exceeds its buffer view')
  }
  let decodedAccessorBytes = 0, vertices = 0
  for (const accessor of accessors) {
    requireValid(integer(accessor.count) && accessor.count >= 0 && Object.hasOwn(widths, accessor.componentType) && Object.hasOwn(sizes, accessor.type), 'Invalid GLB accessor count or type')
    const width = widths[accessor.componentType], elements = sizes[accessor.type], allocation = accessor.count * elements * width
    decodedAccessorBytes += allocation
    const dimension = accessor.type.startsWith('MAT') ? Number(accessor.type.slice(-1)) : 1
    const element = accessor.type.startsWith('MAT') ? dimension * Math.ceil(dimension * width / 4) * 4 : elements * width
    if (accessor.bufferView !== undefined) checkRange(accessor.bufferView, accessor.byteOffset ?? 0, accessor.count, element, width)
    else requireValid((accessor.byteOffset ?? 0) === 0, 'Unbacked GLB accessor has an offset')
    if (accessor.sparse) {
      const sparse = accessor.sparse
      requireValid(integer(sparse.count) && sparse.count >= 0 && sparse.count <= accessor.count && [5121, 5123, 5125].includes(sparse.indices?.componentType), 'Invalid GLB sparse accessor')
      const indexWidth = widths[sparse.indices.componentType]
      checkRange(sparse.indices.bufferView, sparse.indices.byteOffset ?? 0, sparse.count, indexWidth, indexWidth, false)
      checkRange(sparse.values?.bufferView, sparse.values?.byteOffset ?? 0, sparse.count, element, width, false)
      decodedAccessorBytes += allocation + sparse.count * (elements * width + indexWidth)
    }
    if (accessor.type === 'VEC3') vertices += accessor.count
    requireValid(decodedAccessorBytes + viewBytes <= 64_000_000 && vertices <= 1_000_000, 'Model exceeds the decoded geometry allocation limit')
  }
  let pixels = 0
  for (const image of native.images ?? []) {
    let payload: Uint8Array
    if (image.uri !== undefined) {
      requireValid(/^data:image\/(?:png|jpeg);base64,/.test(image.uri), 'Model refers to an external or unsupported texture')
      const raw = atob(image.uri.slice(image.uri.indexOf(',') + 1)); payload = Uint8Array.from(raw, char => char.charCodeAt(0))
    } else {
      requireValid(integer(image.bufferView) && image.bufferView >= 0 && image.bufferView < views.length, 'Invalid GLB texture view')
      const view = views[image.bufferView]; payload = binary.subarray(view.byteOffset ?? 0, (view.byteOffset ?? 0) + view.byteLength)
    }
    const count = texturePixels(payload); requireValid(count > 0 && count <= 10_000_000, 'Model exceeds the texture pixel limit')
    pixels += count; requireValid(pixels <= 10_000_000, 'Model exceeds the texture pixel limit')
  }
  const nodes = native.nodes ?? [], active = new Set<number>(), done = new Set<number>(), parents = new Set<number>()
  requireValid(nodes.length * Math.max(1, native.scenes?.length ?? 0) <= 10_000 && (native.scenes?.length ?? 0) <= 128, 'Model exceeds the node or scene allocation limit')
  const visit = (index: number, depth: number) => {
    requireValid(integer(index) && index >= 0 && index < nodes.length && depth <= 128 && !active.has(index), 'Invalid or cyclic GLB hierarchy')
    if (done.has(index)) return
    active.add(index)
    for (const child of nodes[index].children ?? []) { requireValid(!parents.has(child), 'GLB node has multiple parents'); parents.add(child); visit(child, depth + 1) }
    active.delete(index); done.add(index)
  }
  for (let index = 0; index < nodes.length; index++) visit(index, 0)
  let roots = 0
  for (const scene of native.scenes ?? []) for (const index of scene.nodes ?? []) { requireValid(integer(index) && index >= 0 && index < nodes.length && !parents.has(index), 'Invalid GLB scene root'); roots++ }
  requireValid(roots <= 10_000, 'Model exceeds the scene allocation limit')
  const weights = (native.meshes ?? []).map(mesh => (mesh.primitives ?? []).reduce((sum, primitive) => {
    const index = primitive.indices ?? primitive.attributes?.POSITION
    requireValid(integer(index) && index >= 0 && index < accessors.length, 'Invalid GLB primitive accessor')
    return sum + accessors[index].count
  }, 0))
  let rendered = 0, joints = 0
  for (const node of nodes) {
    requireValid(!Object.hasOwn(node.extensions ?? {}, 'EXT_mesh_gpu_instancing'), 'Model instancing exceeds the supported preview scope')
    if (node.mesh !== undefined) { requireValid(integer(node.mesh) && node.mesh >= 0 && node.mesh < weights.length, 'Invalid GLB mesh reference'); rendered += weights[node.mesh] }
    if (node.skin !== undefined) { requireValid(integer(node.skin) && node.skin >= 0 && node.skin < (native.skins?.length ?? 0), 'Invalid GLB skin reference'); joints += native.skins![node.skin].joints?.length ?? 0 }
  }
  requireValid(rendered * Math.max(1, native.scenes?.length ?? 0) <= 3_000_000 && joints * Math.max(1, native.scenes?.length ?? 0) <= 100_000, 'Model exceeds the instanced render allocation limit')
  return { decodedAccessorBytes }
}
