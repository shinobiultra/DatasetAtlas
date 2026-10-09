import { describe, expect, it } from 'vitest'
import { verifyGlbForViewer } from './glb'
function fixture(accessors: unknown[]) {
  const json = new TextEncoder().encode(JSON.stringify({ asset: { version: '2.0' }, buffers: [{ byteLength: 36 }], bufferViews: [{ byteLength: 36 }], accessors }))
  const size = Math.ceil(json.length / 4) * 4, result = new ArrayBuffer(12 + 8 + size + 8 + 36), view = new DataView(result)
  view.setUint32(0, 0x46546c67, true); view.setUint32(4, 2, true); view.setUint32(8, result.byteLength, true)
  view.setUint32(12, size, true); view.setUint32(16, 0x4e4f534a, true)
  new Uint8Array(result, 20, size).fill(32); new Uint8Array(result, 20, json.length).set(json)
  view.setUint32(20 + size, 36, true); view.setUint32(24 + size, 0x004e4942, true)
  return result
}
describe('GLB decoded allocation bounds before loading', () => {
  it('accepts bounded geometry and refuses billion-element scalar/index allocations', () => {
    expect(verifyGlbForViewer(fixture([{ bufferView: 0, componentType: 5126, type: 'VEC3', count: 3 }])).decodedAccessorBytes).toBe(36)
    for (const type of ['SCALAR', 'VEC2', 'VEC4', 'MAT2', 'MAT3', 'MAT4'])
      expect(() => verifyGlbForViewer(fixture([{ componentType: 5125, type, count: 1_000_000_000 }]))).toThrow(/allocation limit/)
  })
  it('rejects invalid views and sparse references without creating typed arrays', () => {
    expect(() => verifyGlbForViewer(fixture([{ bufferView: 0, componentType: 5126, type: 'VEC3', count: 4 }]))).toThrow(/exceeds/)
    expect(() => verifyGlbForViewer(fixture([{ componentType: 5126, type: 'VEC3', count: 2, sparse: { count: 3 } }]))).toThrow(/sparse/)
  })
})
