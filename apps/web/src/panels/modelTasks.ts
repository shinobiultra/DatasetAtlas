import type { Artifact } from '../generated'
import { bulkOf } from '../lib/bulk'

/** Processors that talk to a model server or score what one produced; their results are always stored as arrays and text. */
export const MODEL_PROCESSORS = ['vlm.answer', 'vlm.tag', 'vlm.judge', 'embed.api', 'score.vqa_accuracy'] as const
export const isModelProcessor = (id: string): boolean => (MODEL_PROCESSORS as readonly string[]).includes(id)
/** Processors that send dataset contents to the chosen model server. */
export const needsServer = (id: string): boolean => ['vlm.answer', 'vlm.tag', 'vlm.judge', 'embed.api'].includes(id)

export type Preset = { template: string; use_images: boolean; max_tokens: number }
export type TagType = 'enum' | 'string' | 'boolean' | 'number'
export type TagField = { name: string; type: TagType; values: string; description: string }

export type ModelParams = {
  providerId: string
  /** undefined = the processor's own wording */
  template?: string
  useImages?: boolean
  maxTokens: string
  thinking: 'auto' | 'off' | 'on'
  concurrency: string
  tags: TagField[]
  explain: boolean
  savedArtifactId: string
  answerColumn: string
  referenceField: string
  representation: 'text' | 'question'
  documentPrefix: string
  queryPrefix: string
  batchSize: string
}

export function emptyModelParams(): ModelParams {
  return {
    providerId: '', maxTokens: '', thinking: 'auto', concurrency: '', tags: [{ name: '', type: 'enum', values: '', description: '' }], explain: false,
    savedArtifactId: '', answerColumn: 'answer', referenceField: '', representation: 'question', documentPrefix: '', queryPrefix: '', batchSize: '',
  }
}

const NAME = /^[a-z][a-z0-9_]{0,39}$/
const RESERVED = new Set(['status', 'prompt_tokens', 'completion_tokens', 'latency_ms', 'finish_reason'])

export function enumValues(text: string): string[] {
  return [...new Set(text.split(',').map(value => value.trim()).filter(Boolean))]
}

/** What the tag editor says, as the server's tag schema, and what is wrong with it. */
export function tagSchema(tags: TagField[]): { schema: Array<Record<string, unknown>>; problems: string[] } {
  const problems: string[] = []
  const used = new Set<string>()
  const schema = tags.filter(tag => tag.name.trim() || tag.values.trim() || tag.description.trim()).map(tag => {
    const name = tag.name.trim()
    if (!NAME.test(name)) problems.push(`Tag name “${name}” must be lower-case letters, digits and underscores, starting with a letter.`)
    else if (RESERVED.has(name) || used.has(name)) problems.push(`Tag name “${name}” repeats or collides with a result column.`)
    used.add(name)
    const item: Record<string, unknown> = { name, type: tag.type }
    if (tag.type === 'enum') {
      const values = enumValues(tag.values)
      if (values.length < 2) problems.push(`Tag “${name}” needs at least two values, separated by commas.`)
      item.values = values
    }
    if (tag.description.trim()) item.description = tag.description.trim()
    return item
  })
  if (!schema.length) problems.push('Add at least one tag field.')
  if (schema.length > 16) problems.push('At most 16 tag fields.')
  return { schema, problems }
}

function whole(text: string): number | undefined {
  return text.trim() !== '' && Number.isInteger(Number(text)) ? Number(text) : undefined
}

/**
 * The configuration for a model-server processor from what the form shows, and what still stops it from running.
 * Only values that differ from the processor's own defaults are sent, so a run records exactly what was chosen.
 */
export function modelConfig(processorId: string, params: ModelParams, preset?: Preset): { config: Record<string, unknown>; problems: string[] } {
  const config: Record<string, unknown> = {}
  const problems: string[] = []
  if (needsServer(processorId)) {
    if (params.providerId) config.provider_id = params.providerId
    else problems.push('Choose a model server.')
  }
  const concurrency = whole(params.concurrency)
  if (concurrency !== undefined) config.concurrency = concurrency
  if (processorId.startsWith('vlm.')) {
    if (params.template !== undefined && params.template.trim() !== (preset?.template ?? '').trim()) config.template = params.template
    if (params.useImages !== undefined && params.useImages !== preset?.use_images) config.use_images = params.useImages
    const maxTokens = whole(params.maxTokens)
    if (maxTokens !== undefined) config.max_tokens = maxTokens
    if (params.thinking !== 'auto') config.thinking = params.thinking === 'on'
  }
  if (processorId === 'vlm.tag') {
    const { schema, problems: tagProblems } = tagSchema(params.tags)
    config.schema = schema
    problems.push(...tagProblems)
  }
  if (processorId === 'vlm.judge') {
    if (params.savedArtifactId) { config.candidate_artifact_id = params.savedArtifactId; config.answer_column = params.answerColumn }
    else problems.push('Choose the saved answers to judge.')
    if (params.referenceField) config.reference_field = params.referenceField
    if (params.explain) config.explain = true
  }
  if (processorId === 'score.vqa_accuracy') {
    if (params.savedArtifactId) { config.answers_artifact_id = params.savedArtifactId; config.answer_column = params.answerColumn }
    else problems.push('Choose the saved answers to score.')
  }
  if (processorId === 'embed.api') {
    config.representation = params.representation
    if (params.documentPrefix) config.document_prefix = params.documentPrefix
    if (params.queryPrefix) config.query_prefix = params.queryPrefix
    const batch = whole(params.batchSize)
    if (batch !== undefined) config.batch_size = batch
  }
  return { config, problems }
}

/** Saved result columns that hold text, so a judge or a score can read them. */
export function textSources(artifacts: Artifact[], unit: string, snapshotIds: string[] | undefined): Array<{ artifact: Artifact; columns: string[] }> {
  return artifacts
    .filter(artifact => artifact.unit === unit && (!snapshotIds?.length || artifact.snapshot_ids.some(id => snapshotIds.includes(id))))
    .map(artifact => ({ artifact, columns: Object.keys(bulkOf(artifact)?.texts ?? {}) }))
    .filter(source => source.columns.length > 0)
}

/** Loopback servers only: a batch run sends dataset contents, and only a server on this machine may receive them. */
export function isLoopbackUrl(url: string | undefined): boolean {
  if (!url) return false
  try {
    const host = new URL(url).hostname.replace(/^\[|\]$/g, '')
    return host === 'localhost' || host === '::1' || /^127\.\d+\.\d+\.\d+$/.test(host)
  } catch { return false }
}
