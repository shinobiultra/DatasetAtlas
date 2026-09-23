import { provider } from '../provider'

/** Display representations never replace Asset.uri in saved records or model contexts. */
export function safeViewEnabled(): boolean {
  // Only the workbench can serve a derivative; the public build would just lose every image.
  if (provider.mode !== 'workbench') return false
  try { return localStorage.getItem('atlas.safe-view') === 'true' } catch { return false }
}
export function displayUrl(url: string): string {
  if (!safeViewEnabled()) return url
  if (url.startsWith('/api/v1/media/')) {
    const parsed = new URL(url, 'http://atlas.invalid')
    parsed.searchParams.set('representation', 'safe-view')
    return parsed.pathname + parsed.search
  }
  return 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="240" height="160"%3E%3Crect width="240" height="160" fill="%23888"/%3E%3C/svg%3E'
}
