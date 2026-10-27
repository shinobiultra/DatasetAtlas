import { describe, expect, it } from 'vitest'
import { membershipRows, nearestRow, projectToScreen, rowsInPolygon } from './scene'

const IDENTITY = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]

describe('projection population membership', () => {
  it('keeps original row indices when filtering and restores the whole fitted population', () => {
    expect(membershipRows(4, undefined)).toBeUndefined()
    expect(Array.from(membershipRows(4, Uint8Array.from([0, 1, 0, 1]))!)).toEqual([1, 3])
    expect(membershipRows(4, Uint8Array.from([1, 1, 1, 1]))).toBeUndefined()
    expect(Array.from(membershipRows(4, null)!)).toEqual([])
  })

  it('rejects a mask from another population or non-binary membership', () => {
    expect(() => membershipRows(4, Uint8Array.from([1, 1]))).toThrow(/population length/)
    expect(() => membershipRows(4, Uint8Array.from([1, 2, 0, 1]))).toThrow(/0 or 1/)
  })

  it('never picks or lassos excluded points or a population still resolving', () => {
    const positions = Float32Array.from([-0.8, 0, 0, -0.2, 0, 0, 0.2, 0, 0, 0.8, 0, 0])
    const mask = Uint8Array.from([0, 1, 0, 1])
    const screen = projectToScreen(positions, IDENTITY, 100, 100, mask)
    const outline = [{ x: 0, y: 0 }, { x: 100, y: 0 }, { x: 100, y: 100 }, { x: 0, y: 100 }]
    expect(rowsInPolygon(screen, outline)).toEqual([1, 3])
    expect(nearestRow(screen, 10, 50, 13)).toBe(-1)
    expect(nearestRow(screen, 90, 50, 13)).toBe(3)
    const pending = projectToScreen(positions, IDENTITY, 100, 100, null)
    expect(rowsInPolygon(pending, outline)).toEqual([])
    expect(nearestRow(pending, 90, 50, 13)).toBe(-1)
  })
})
