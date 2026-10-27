export type Point = { x: number; y: number }

/** Original projection row indices; an absent index draws the whole population. */
export function membershipRows(count: number, membership?: Uint8Array | null): Uint32Array | undefined {
  if (membership === undefined) return undefined
  if (membership === null) return new Uint32Array(0)
  if (membership.length !== count) throw new Error('Projection membership population length differs from the fitted projection')
  let included = 0
  for (const flag of membership) {
    if (flag !== 0 && flag !== 1) throw new Error('Projection membership flags must be 0 or 1')
    included += flag
  }
  if (included === count) return undefined
  const rows = new Uint32Array(included)
  for (let row = 0, at = 0; row < count; row++) if (membership[row]) rows[at++] = row
  return rows
}

/**
 * Screen position of every point, from a column-major projection*view matrix (three.js `Matrix4.elements`).
 * Points behind the camera get NaN so picking and lasso selection skip them.
 */
export function projectToScreen(positions: ArrayLike<number>, e: ArrayLike<number>, width: number, height: number, membership?: Uint8Array | null): Float32Array {
  const count = positions.length / 3
  const out = new Float32Array(count * 2)
  for (let row = 0; row < count; row++) {
    if (membership === null || (membership !== undefined && membership[row] !== 1)) {
      out[row * 2] = NaN; out[row * 2 + 1] = NaN; continue
    }
    const x = positions[row * 3], y = positions[row * 3 + 1], z = positions[row * 3 + 2]
    const w = e[3] * x + e[7] * y + e[11] * z + e[15]
    if (w <= 0) { out[row * 2] = NaN; out[row * 2 + 1] = NaN; continue }
    out[row * 2] = ((e[0] * x + e[4] * y + e[8] * z + e[12]) / w * 0.5 + 0.5) * width
    out[row * 2 + 1] = (1 - ((e[1] * x + e[5] * y + e[9] * z + e[13]) / w * 0.5 + 0.5)) * height
  }
  return out
}

/** How far a gesture strayed from where it began. A closed lasso ends beside its start, so end-to-start distance is no measure. */
export function strayed(path: Point[]): number {
  return path.reduce((far, point) => Math.max(far, Math.hypot(point.x - path[0].x, point.y - path[0].y)), 0)
}

/** Rows whose screen position lies inside the polygon (even-odd rule), after a bounding-box cut. */
export function rowsInPolygon(screen: ArrayLike<number>, path: Point[]): number[] {
  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity
  for (const point of path) { minX = Math.min(minX, point.x); maxX = Math.max(maxX, point.x); minY = Math.min(minY, point.y); maxY = Math.max(maxY, point.y) }
  const rows: number[] = []
  for (let row = 0; row < screen.length / 2; row++) {
    const x = screen[row * 2], y = screen[row * 2 + 1]
    if (!(x >= minX && x <= maxX && y >= minY && y <= maxY)) continue
    let inside = false
    for (let at = 0, previous = path.length - 1; at < path.length; previous = at++) {
      const a = path[at], b = path[previous]
      if ((a.y > y) !== (b.y > y) && x < (b.x - a.x) * (y - a.y) / (b.y - a.y) + a.x) inside = !inside
    }
    if (inside) rows.push(row)
  }
  return rows
}

/** The row nearest to (x, y) within `radius` pixels, or -1. */
export function nearestRow(screen: ArrayLike<number>, x: number, y: number, radius: number): number {
  let nearest = -1, best = radius
  for (let row = 0; row < screen.length / 2; row++) {
    const distance = Math.hypot(screen[row * 2] - x, screen[row * 2 + 1] - y)
    if (distance < best) { best = distance; nearest = row }
  }
  return nearest
}
