import { describe, expect, it } from 'vitest'
import { nearestRow, projectToScreen, rowsInPolygon, strayed } from './scene'

// Column-major identity projection*view: x and y map straight to the screen, with w = 1.
const IDENTITY = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]

describe('projectToScreen', () => {
  it('maps normalised device coordinates to pixels with y pointing down', () => {
    const screen = projectToScreen([0, 0, 0, 1, 1, 0, -1, -1, 0], IDENTITY, 200, 100)
    expect(Array.from(screen)).toEqual([100, 50, 200, 0, 0, 100])
  })

  it('marks points behind the camera so they are never picked', () => {
    const behind = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, -1, 0, 0, 0, 0] // w = -z... negative for z > 0
    const screen = projectToScreen([0, 0, 1], behind, 100, 100)
    expect(Number.isNaN(screen[0]) && Number.isNaN(screen[1])).toBe(true)
  })
})

describe('lasso and picking', () => {
  const screen = Float32Array.from([10, 10, 50, 50, 90, 90, NaN, NaN])
  const square = [{ x: 0, y: 0 }, { x: 60, y: 0 }, { x: 60, y: 60 }, { x: 0, y: 60 }]

  it('selects exactly the points inside the polygon and skips off-screen ones', () => {
    expect(rowsInPolygon(screen, square)).toEqual([0, 1])
  })

  it('works for a concave outline', () => {
    const arrow = [{ x: 0, y: 0 }, { x: 100, y: 0 }, { x: 100, y: 100 }, { x: 50, y: 40 }, { x: 0, y: 100 }]
    expect(rowsInPolygon(Float32Array.from([50, 20, 50, 90, 4, 90]), arrow)).toEqual([0, 2])
  })

  it('treats a closed lasso as a lasso: it ends beside its start but strays far from it', () => {
    const closed = [{ x: 10, y: 10 }, { x: 110, y: 10 }, { x: 110, y: 90 }, { x: 10, y: 90 }, { x: 11, y: 11 }]
    expect(strayed(closed)).toBeGreaterThan(100)
    expect(strayed([{ x: 5, y: 5 }, { x: 6, y: 6 }, { x: 5, y: 5 }])).toBeLessThan(5)
  })

  it('picks the nearest point within the radius and nothing beyond it', () => {
    expect(nearestRow(screen, 52, 49, 13)).toBe(1)
    expect(nearestRow(screen, 70, 20, 13)).toBe(-1)
    expect(nearestRow(Float32Array.from([NaN, NaN, 5, 5]), 5, 5, 13)).toBe(1)
  })
})
