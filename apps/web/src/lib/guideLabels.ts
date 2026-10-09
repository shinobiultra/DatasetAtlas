/** Words for the public guide's how-to-get states, shared by the dataset page and the catalogue list. */
export const GUIDE_LABELS: Record<string, string> = {
  in_site: 'Examples on this site', live_preview: 'Live preview from Hugging Face', fetch_with_atlas: 'Fetch with Dataset Atlas', fetch_after_terms: 'Accept terms, then fetch',
  accept_terms: 'Gated at the source', request_from_authors: 'Request from the authors',
  source_only: 'Get it from the source', unreleased: 'Not released', source_unverified: 'No verified public source',
}
export const GUIDE_SHORT: Record<string, string> = {
  in_site: 'Live examples', live_preview: 'Live preview', fetch_with_atlas: 'Fetch with Atlas', fetch_after_terms: 'Accept terms, then fetch',
  accept_terms: 'Gated', request_from_authors: 'On request',
  source_only: 'Source link', unreleased: 'Not released', source_unverified: 'No verified source',
}
export const GUIDE_TONES: Record<string, 'ok' | 'warn' | 'default'> = {
  in_site: 'ok', live_preview: 'ok', fetch_with_atlas: 'ok', fetch_after_terms: 'warn', accept_terms: 'warn', request_from_authors: 'warn',
  source_only: 'default', unreleased: 'default', source_unverified: 'default',
}
