import { useCallback, useEffect, useState } from 'react'

/** Hash routing: the static GitHub Pages build needs no server rewrite rules. */
export type Route =
  | { name: 'catalogue' }
  | { name: 'dataset'; id: string; tab: 'samples' | 'overview' }
  | { name: 'collections' }
  | { name: 'collection'; id: string }
  | { name: 'runs' }
  | { name: 'settings'; section: string }
  | { name: 'unknown'; path: string }

export function parseRoute(hash: string): Route {
  const path = decodeURI(hash.replace(/^#/, '')) || '/'
  const [bare] = path.split('?')
  const parts = bare.split('/').filter(Boolean).map(decodeURIComponent)
  if (!parts.length) return { name: 'catalogue' }
  if (parts[0] === 'dataset' && parts[1]) {
    return { name: 'dataset', id: parts[1], tab: parts[2] === 'overview' ? 'overview' : 'samples' }
  }
  if (parts[0] === 'collections') return parts[1] ? { name: 'collection', id: parts[1] } : { name: 'collections' }
  if (parts[0] === 'selection' && parts[1]) return { name: 'collection', id: parts[1] }
  if (parts[0] === 'runs') return { name: 'runs' }
  if (parts[0] === 'settings') return { name: 'settings', section: parts[1] ?? 'sources' }
  return { name: 'unknown', path: bare }
}

export function href(route: Route): string {
  switch (route.name) {
    case 'catalogue': return '#/'
    case 'dataset': return `#/dataset/${encodeURIComponent(route.id)}${route.tab === 'overview' ? '/overview' : ''}`
    case 'collections': return '#/collections'
    case 'collection': return `#/collections/${encodeURIComponent(route.id)}`
    case 'runs': return '#/runs'
    case 'settings': return `#/settings/${route.section}`
    default: return '#/'
  }
}

export function useRoute(): [Route, (route: Route) => void] {
  const [hash, setHash] = useState(() => window.location.hash)
  useEffect(() => {
    const update = () => setHash(window.location.hash)
    window.addEventListener('hashchange', update)
    return () => window.removeEventListener('hashchange', update)
  }, [])
  const navigate = useCallback((route: Route) => {
    const next = href(route)
    if (window.location.hash !== next) window.location.hash = next
    else setHash(next)
  }, [])
  return [parseRoute(hash), navigate]
}
