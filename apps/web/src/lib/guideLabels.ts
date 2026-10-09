/** Words for the public guide's how-to-get states, shared by the dataset page and the catalogue list. */
export const GUIDE_LABELS: Record<string, string> = {
  in_site: 'Examples on this site', fetch_with_atlas: 'Fetch with Dataset Atlas', fetch_after_terms: 'Accept terms, then fetch',
  prepared_by_maintainers_only: 'Maintainer preview, no public recipe', accept_terms: 'Gated at the source', request_from_authors: 'Request from the authors',
  public_no_adapter: 'Public source, no Atlas recipe yet', unreleased: 'Not released', source_unverified: 'No verified public source',
}
export const GUIDE_SHORT: Record<string, string> = {
  in_site: 'Live examples', fetch_with_atlas: 'Fetch with Atlas', fetch_after_terms: 'Accept terms, then fetch',
  prepared_by_maintainers_only: 'Maintainer preview', accept_terms: 'Gated', request_from_authors: 'On request',
  public_no_adapter: 'Public, no recipe yet', unreleased: 'Not released', source_unverified: 'No verified source',
}
export const GUIDE_TONES: Record<string, 'ok' | 'warn' | 'default'> = {
  in_site: 'ok', fetch_with_atlas: 'ok', fetch_after_terms: 'warn', accept_terms: 'warn', request_from_authors: 'warn',
  prepared_by_maintainers_only: 'default', public_no_adapter: 'default', unreleased: 'default', source_unverified: 'default',
}
