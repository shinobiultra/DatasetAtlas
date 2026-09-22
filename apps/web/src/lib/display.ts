/** Display representations never replace Asset.uri in saved records or model contexts. */
export function safeViewEnabled(): boolean { return localStorage.getItem('atlas.safe-view') === 'true' }
export function displayUrl(url: string): string {
  if (!safeViewEnabled()) return url
  if (url.startsWith('/api/v1/media/')) return `${url}${url.includes('?') ? '&' : '?'}representation=safe-view`
  return 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="240" height="160"%3E%3Crect width="240" height="160" fill="%23888"/%3E%3C/svg%3E'
}
