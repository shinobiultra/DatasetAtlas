/** Saved view state that is safe to drop; starred datasets and notes are the user's own data and stay. */
export const VIEW_PREFERENCE_KEYS = [
  'atlas.nav', 'atlas.recent', 'atlas.view', 'atlas.dense', 'atlas.card', 'atlas.columns', 'atlas.rail', 'atlas.panel-width',
  'atlas.catalogue.facets', 'atlas.catalogue.layout', 'atlas.catalogue.sort',
]

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

/**
 * A saved preference only counts while it still has the shape of today's default.
 * Older builds saved other shapes (a facet added since has no saved array), and
 * trusting them crashes the first render.
 */
export function coerceStored<T>(saved: unknown, fallback: T): T {
  if (Array.isArray(fallback)) return (Array.isArray(saved) ? saved : fallback) as T
  if (isPlainObject(fallback)) {
    if (!isPlainObject(saved)) return fallback
    const merged: Record<string, unknown> = { ...saved }
    for (const key of Object.keys(fallback)) merged[key] = coerceStored(saved[key], fallback[key])
    return merged as T
  }
  return (typeof saved === typeof fallback ? saved : fallback) as T
}
