import type { Color } from 'three'

export const NOISE_COLOUR = '#b8bfc9'

/** Cluster labels get well-separated hues however many clusters there are (golden-angle spacing). */
export const clusterHue = (label: number): number => (label * 137.508) % 360

/** CSS colour for legends and swatches. */
export function clusterCss(label: number): string {
  return label < 0 ? NOISE_COLOUR : `hsl(${clusterHue(label)}, 62%, 50%)`
}

/**
 * Set a three.js Color from a cluster label. This uses HSL numbers on purpose: three.js does not parse the
 * space-separated CSS form (`hsl(137 62% 50%)`) and silently keeps the colour it already had, which paints every point white.
 */
export function setClusterColour(target: Color, label: number): Color {
  return label < 0 ? target.set(NOISE_COLOUR) : target.setHSL(clusterHue(label) / 360, 0.62, 0.5)
}

/** Blue (low) to orange (high) ramp for numeric scores; `fraction` is 0..1. */
export function setRampColour(target: Color, fraction: number): Color {
  return target.setHSL((222 - 200 * fraction) / 360, 0.72, (64 - 20 * fraction) / 100)
}
