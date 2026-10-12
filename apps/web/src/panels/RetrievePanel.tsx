import { useEffect, useMemo, useState } from 'react'
import type { Artifact, Query } from '../generated'
import { isEmbeddingArtifact } from '../dataset/model'
import { display, shortId } from '../lib/format'
import { provider } from '../provider'
import { Field, Notice, Spinner } from '../ui/primitives'
import { hitRows, retrievalQuery, spaceLabel, type Hit } from './retrieval'

const MAX_HITS = 20

/**
 * Chat with a dataset: find the records that best match a question, then attach them to the chat.
 * Attaching only chooses records; what the model will receive is still reviewed and approved below.
 */
export function RetrievePanel({ datasetId, query, artifacts, unit, onAttach }: {
  datasetId: string; query: Query | null; artifacts: Artifact[]; unit: string
  onAttach: (ids: string[], question: string) => void
}) {
  const spaces = useMemo(() => artifacts.filter(artifact =>
    isEmbeddingArtifact(artifact) && artifact.kind !== 'import.research' && artifact.unit === unit && query !== null && artifact.snapshot_ids.includes(query.snapshot_id)), [artifacts, unit, query])
  const [spaceId, setSpaceId] = useState('')
  const [question, setQuestion] = useState('')
  const [count, setCount] = useState(8)
  const [hits, setHits] = useState<Hit[] | null>(null)
  const [ticked, setTicked] = useState<Set<string>>(new Set())
  const [note, setNote] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  useEffect(() => { if (!spaces.some(space => space.id === spaceId)) setSpaceId(spaces[0]?.id ?? '') }, [spaces, spaceId])
  useEffect(() => { setHits(null); setNote('') }, [spaceId, JSON.stringify(query?.filter), query?.search, query?.snapshot_id])

  if (provider.mode !== 'workbench' || !query) return null

  async function retrieve() {
    if (!query) return
    setBusy(true); setError('')
    try {
      const result = await provider.similarity(datasetId, { artifact_id: spaceId, text: question.trim(), query: retrievalQuery(query), limit: count })
      const found = (result.results ?? []) as Array<{ id: string; distance: number }>
      const records = found.length ? await provider.records(found.map(row => row.id), [query.snapshot_id]) : []
      const rows = hitRows(found, records)
      setHits(rows); setTicked(new Set(rows.map(row => row.id)))
      setNote(`Exact search over ${display(result.eligible_count)} embedded records (${display(result.population_scope)} scope).`)
    } catch (failure) { setError(String(failure instanceof Error ? failure.message : failure)); setHits(null) }
    finally { setBusy(false) }
  }

  return (
    <details className="disclosure" open>
      <summary>Find records to ask about</summary>
      <div className="body col" style={{ gap: 8 }}>
        <p className="hint">Search the records matching the current filters by meaning, then attach the best matches to this chat. Nothing is sent to a model until you review the context below.</p>
        {!spaces.length
          ? <Notice tone="quiet">No embedding space covers this population yet. Run an embedding (MiniLM, SigLIP 2 or a model server) from Analyze first.</Notice>
          : <>
            <Field label="Embedding space">{id => (
              <select id={id} className="select" value={spaceId} onChange={event => setSpaceId(event.target.value)}>
                {spaces.map(space => <option key={space.id} value={space.id}>{spaceLabel(space)}</option>)}
              </select>
            )}</Field>
            <Field label="Question or topic">{id => <input id={id} className="input" value={question} onChange={event => setQuestion(event.target.value)} placeholder="What are you looking for?" onKeyDown={event => { if (event.key === 'Enter' && question.trim() && !busy) void retrieve() }} />}</Field>
            <Field label="Records to retrieve">{id => <input id={id} className="input" type="number" min={1} max={MAX_HITS} value={count} onChange={event => setCount(Math.max(1, Math.min(MAX_HITS, Number(event.target.value) || 1)))} />}</Field>
            <button type="button" className="btn" disabled={!spaceId || !question.trim() || busy} onClick={() => void retrieve()}>{busy ? <Spinner label="Searching…" /> : 'Retrieve'}</button>
          </>}
        {error && <Notice tone="error">{error}</Notice>}
        {hits && (
          <>
            <p className="hint">{note}</p>
            {!hits.length && <Notice tone="quiet">No embedded record matched.</Notice>}
            <div style={{ maxHeight: 220, overflow: 'auto', border: '1px solid var(--divider)', borderRadius: 'var(--radius-sm)' }}>
              {hits.map(hit => (
                <label key={hit.id} className="row" style={{ gap: 8, padding: '5px 8px', borderBottom: '1px solid var(--divider)', cursor: 'pointer', alignItems: 'flex-start' }}>
                  <input type="checkbox" checked={ticked.has(hit.id)} aria-label={`Attach ${hit.id}`}
                    onChange={event => setTicked(current => { const next = new Set(current); if (event.target.checked) next.add(hit.id); else next.delete(hit.id); return next })} />
                  <span style={{ minWidth: 0, fontSize: 'var(--fs-sm)' }}>
                    <span className="mono" title={hit.id}>{shortId(hit.id, 16)}</span>
                    <span style={{ color: 'var(--text-muted)' }}> · distance {hit.distance.toFixed(4)}</span>
                    {hit.snippet && <span style={{ display: 'block' }}>{hit.snippet}</span>}
                  </span>
                </label>
              ))}
            </div>
            <button type="button" className="btn primary" disabled={!ticked.size}
              onClick={() => onAttach(hits.filter(hit => ticked.has(hit.id)).map(hit => hit.id), question)}>
              Attach {ticked.size} {ticked.size === 1 ? 'record' : 'records'} to the chat
            </button>
          </>
        )}
      </div>
    </details>
  )
}
