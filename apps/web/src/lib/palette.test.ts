import { Color } from 'three'
import { describe, expect, it } from 'vitest'
import { clusterCss, NOISE_COLOUR, setClusterColour, setRampColour } from './palette'

const key = (colour: Color) => `${colour.r.toFixed(3)},${colour.g.toFixed(3)},${colour.b.toFixed(3)}`

describe('cluster palette', () => {
  it('never paints a cluster white, which is what an unparsed colour string would do', () => {
    const colour = new Color()
    for (let label = 0; label < 40; label++) {
      expect(key(setClusterColour(colour, label))).not.toBe('1.000,1.000,1.000')
    }
  })

  it('gives the first dozen clusters different colours', () => {
    const colour = new Color()
    const seen = new Set(Array.from({ length: 12 }, (_, label) => key(setClusterColour(colour, label))))
    expect(seen.size).toBe(12)
  })

  it('draws noise grey and matches the legend swatch family', () => {
    expect(key(setClusterColour(new Color(), -1))).toBe(key(new Color(NOISE_COLOUR)))
    expect(clusterCss(-1)).toBe(NOISE_COLOUR)
    expect(clusterCss(3)).toMatch(/^hsl\(\d+(\.\d+)?, 62%, 50%\)$/)
  })

  it('ramps from blue to orange', () => {
    const low = setRampColour(new Color(), 0), high = setRampColour(new Color(), 1)
    expect(low.b).toBeGreaterThan(low.r)
    expect(high.r).toBeGreaterThan(high.b)
  })
})
