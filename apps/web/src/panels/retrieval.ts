import type { Artifact, Query, Record as AtlasRecord } from '../generated'

/** Added to the user's question so a retrieved-context answer stays tied to what was attached. */
export const GROUNDING_INSTRUCTION = 'Answer only from the attached records and cite each one you use as [record:<id>]. If they do not contain the answer, say so.'

export function groundedPrompt(question: string): string {
  return `${question.trim()}\n\n${GROUNDING_INSTRUCTION}`
}

/** The knowledge base is the filtered population; a random sample is a way of paging through it, not a population. */
export function retrievalQuery(query: Query): Query {
  return { ...query, sample: null, cursor: null }
}

export type Hit = { id: string; distance: number; snippet: string }

export function snippet(record: AtlasRecord | undefined, max = 140): string {
  const text = (record?.question ?? record?.text ?? '').replace(/\s+/g, ' ').trim()
  return text.length > max ? `${text.slice(0, max - 1)}…` : text
}

/** Hits in the order the search ranked them; a record that could not be fetched keeps its row. */
export function hitRows(results: Array<{ id: string; distance: number }>, records: AtlasRecord[]): Hit[] {
  const byId = new Map(records.map(record => [record.id, record]))
  return results.map(row => ({ id: row.id, distance: row.distance, snippet: snippet(byId.get(row.id)) }))
}

/** What tells two embedding spaces apart: the model, what was embedded, and how many records have a vector. */
export function spaceLabel(artifact: Artifact): string {
  const provenance = (artifact.provenance?.processor_provenance ?? {}) as { model_id?: string; recipe?: { model_id?: string; representation?: string } }
  const model = provenance.model_id ?? provenance.recipe?.model_id
  const representation = provenance.recipe?.representation
  const bulk = artifact.data?.bulk as { count?: number } | undefined
  const count = bulk?.count ?? artifact.ids.length
  return [artifact.kind, model, representation, `${count.toLocaleString('en-US')} records`, `…${artifact.id.slice(-6)}`].filter(Boolean).join(' · ')
}
