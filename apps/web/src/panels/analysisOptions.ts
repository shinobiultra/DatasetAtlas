export type Option = { key: string; label: string; hint?: string } & (
  | { kind: 'select'; choices: Array<[string, string]>; initial: string }
  | { kind: 'number'; min: number; max: number; step: number; initial: number }
)

const METRIC: Option = { key: 'metric', label: 'Distance', kind: 'select', choices: [['cosine', 'Cosine'], ['euclidean', 'Euclidean']], initial: 'cosine' }
const DIMENSIONS: Option = { key: 'dimensions', label: 'Dimensions', kind: 'select', choices: [['2', '2D'], ['3', '3D']], initial: '3', hint: 'A 3D projection opens in the rotatable 3D map.' }
const PRECISION: Option = { key: 'precision', label: 'Precision', kind: 'select', choices: [['auto', 'Automatic (bf16 on a GPU)'], ['fp32', 'Full (fp32)'], ['bf16', 'bf16'], ['fp16', 'fp16']], initial: 'auto', hint: 'Used for stored array runs; reduced precision is recorded in the result.' }

/** What each analysis lets you tune, with the defaults shown on screen. */
export const OPTIONS: Record<string, Option[]> = {
  'project.pca': [DIMENSIONS],
  'project.umap': [DIMENSIONS, { key: 'neighbors', label: 'Neighbours', kind: 'number', min: 2, max: 200, step: 1, initial: 15, hint: 'Larger values preserve more global structure.' },
    { key: 'min_dist', label: 'Minimum distance', kind: 'number', min: 0, max: 1, step: 0.05, initial: 0.1, hint: 'Smaller values pack points into tighter clumps.' }, METRIC],
  'cluster.kmeans': [{ key: 'clusters', label: 'Clusters', kind: 'number', min: 1, max: 100000, step: 1, initial: 8 },
    { key: 'n_init', label: 'Restarts', kind: 'number', min: 1, max: 50, step: 1, initial: 1, hint: 'The best of several seeds is kept.' }, { ...METRIC, initial: 'euclidean' }],
  'cluster.hdbscan': [{ key: 'min_cluster_size', label: 'Smallest cluster', kind: 'number', min: 2, max: 1000000, step: 1, initial: 15, hint: 'Points in smaller groups are labelled noise.' }, METRIC],
  'cluster.agglomerative': [{ key: 'clusters', label: 'Clusters', kind: 'number', min: 1, max: 100000, step: 1, initial: 8 },
    { key: 'linkage', label: 'Linkage', kind: 'select', choices: [['ward', 'Ward'], ['average', 'Average'], ['complete', 'Complete'], ['single', 'Single']], initial: 'ward' }],
  'outlier.knn': [{ key: 'neighbors', label: 'Neighbours', kind: 'number', min: 1, max: 1000, step: 1, initial: 5, hint: 'The score is the distance to this neighbour.' }, METRIC],
  'embed.siglip2': [PRECISION],
  'embed.minilm': [PRECISION],
}

/**
 * The configuration a form sends. Every option is sent with the value the form shows, changed or not, so a run always
 * matches the screen even where a form default (3D) differs from the processor's own (2D). Numbers become numbers.
 */
export function optionConfig(processorId: string, params: Record<string, string | number>): Record<string, unknown> {
  const chosen: Record<string, unknown> = {}
  for (const option of OPTIONS[processorId] ?? []) {
    const value = params[option.key] ?? option.initial
    if (value === '') continue
    chosen[option.key] = option.kind === 'number' || option.key === 'dimensions' ? Number(value) : value
  }
  return chosen
}
