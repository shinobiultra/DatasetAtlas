import type { Artifact, FieldDescriptor } from '../generated'
import { runLabel } from '../dataset/model'
import { resultCount } from '../lib/bulk'
import { Field, Notice } from '../ui/primitives'
import { needsServer, textSources, type ModelParams, type Preset, type TagField } from './modelTasks'

export type ServerChoice = { id: string; model: string }

const PLACEHOLDERS = '{question}  {text}  {choices}  {candidate}  {reference}  {field:source.name}'

/** The options of a model-server run: which server, the wording, and what to do with the reply. */
export function ModelTaskForm({ processorId, preset, params, onChange, servers, hiddenServers, artifacts, fields, unit, snapshotIds }: {
  processorId: string
  preset?: Preset
  params: ModelParams
  onChange: (next: ModelParams) => void
  servers: ServerChoice[]
  /** Configured servers that are not on this machine; they cannot receive a batch run. */
  hiddenServers: number
  artifacts: Artifact[]
  fields: FieldDescriptor[]
  unit: string
  snapshotIds?: string[]
}) {
  const set = (patch: Partial<ModelParams>) => onChange({ ...params, ...patch })
  const isModel = processorId.startsWith('vlm.')
  const sources = textSources(artifacts, unit, snapshotIds)
  const source = sources.find(item => item.artifact.id === params.savedArtifactId)
  const template = params.template ?? preset?.template ?? ''
  const useImages = params.useImages ?? preset?.use_images ?? false
  const setTag = (index: number, patch: Partial<TagField>) => set({ tags: params.tags.map((tag, i) => (i === index ? { ...tag, ...patch } : tag)) })
  const referenceChoices = fields.filter(field => ['source', 'human', 'prediction'].includes(field.id.split('.')[0]))

  return (
    <>
      {needsServer(processorId) && (
        <>
          <Field label="Model server" hint="Dataset contents are sent only to a server on this machine (vLLM, Ollama, LM Studio, llama.cpp).">{id => (
            <select id={id} className="select" value={params.providerId} onChange={event => set({ providerId: event.target.value })}>
              <option value="">Choose a model server</option>
              {servers.map(server => <option key={server.id} value={server.id}>{server.model} · {server.id}</option>)}
            </select>
          )}</Field>
          {!servers.length && <Notice tone="warn">No model server on this machine is configured. Add one under Ask model → Add connection, using its loopback address.</Notice>}
          {hiddenServers > 0 && <p className="hint">{hiddenServers} configured {hiddenServers === 1 ? 'server is' : 'servers are'} not on this machine and cannot receive a batch run.</p>}
        </>
      )}

      {isModel && (
        <>
          <Field label="Prompt" hint={<>Rendered for every record. Placeholders: <code>{PLACEHOLDERS}</code>. The estimate shows the exact text for the first record.</>}>{id => (
            <textarea id={id} className="textarea" rows={5} value={template} spellCheck={false} onChange={event => set({ template: event.target.value })} />
          )}</Field>
          {params.template !== undefined && params.template !== preset?.template && (
            <button type="button" className="btn sm" onClick={() => set({ template: undefined })}>Use the default prompt</button>
          )}
          {processorId === 'vlm.answer' && (
            <label className="facet-opt"><input type="checkbox" checked={useImages} onChange={event => set({ useImages: event.target.checked })} /><span>Send the record’s image with each question</span></label>
          )}
          <div className="row" style={{ gap: 8 }}>
            <Field label="Reply tokens">{id => <input id={id} className="input" type="number" min={1} placeholder={String(preset?.max_tokens ?? '')} value={params.maxTokens} onChange={event => set({ maxTokens: event.target.value })} />}</Field>
            <Field label="Parallel requests">{id => <input id={id} className="input" type="number" min={1} max={128} placeholder="16" value={params.concurrency} onChange={event => set({ concurrency: event.target.value })} />}</Field>
          </div>
          <Field label="Reasoning" hint="Turn thinking off for models that would spend the whole reply budget reasoning (the run says so when a reply is all reasoning).">{id => (
            <select id={id} className="select" value={params.thinking} onChange={event => set({ thinking: event.target.value as ModelParams['thinking'] })}>
              <option value="auto">Model default</option><option value="off">Off</option><option value="on">On</option>
            </select>
          )}</Field>
        </>
      )}

      {processorId === 'vlm.tag' && (
        <div className="col" style={{ gap: 6 }}>
          <div className="insp-kicker">Fields to fill in</div>
          {params.tags.map((tag, index) => (
            <div key={index} className="col" style={{ gap: 4, border: '1px solid var(--divider)', borderRadius: 'var(--radius-sm)', padding: 8 }}>
              <div className="row" style={{ gap: 6 }}>
                <input className="input" aria-label={`Tag ${index + 1} name`} placeholder="name, e.g. topic" value={tag.name} onChange={event => setTag(index, { name: event.target.value })} />
                <select className="select" aria-label={`Tag ${index + 1} type`} value={tag.type} onChange={event => setTag(index, { type: event.target.value as TagField['type'] })}>
                  <option value="enum">One of</option><option value="string">Text</option><option value="boolean">Yes / no</option><option value="number">Number</option>
                </select>
                <button type="button" className="btn sm" aria-label={`Remove tag ${index + 1}`} disabled={params.tags.length === 1} onClick={() => set({ tags: params.tags.filter((_, i) => i !== index) })}>Remove</button>
              </div>
              {tag.type === 'enum' && <input className="input" aria-label={`Tag ${index + 1} values`} placeholder="allowed values, comma separated" value={tag.values} onChange={event => setTag(index, { values: event.target.value })} />}
              <input className="input" aria-label={`Tag ${index + 1} description`} placeholder="what to look for (optional)" value={tag.description} onChange={event => setTag(index, { description: event.target.value })} />
            </div>
          ))}
          <button type="button" className="btn sm" disabled={params.tags.length >= 16} onClick={() => set({ tags: [...params.tags, { name: '', type: 'enum', values: '', description: '' }] })}>Add a field</button>
        </div>
      )}

      {(processorId === 'vlm.judge' || processorId === 'score.vqa_accuracy') && (
        <>
          <Field label="Saved answers" hint="A finished answer run over the same records. Its text column is what is judged or scored.">{id => (
            <select id={id} className="select" value={params.savedArtifactId} onChange={event => {
              const chosen = sources.find(item => item.artifact.id === event.target.value)
              set({ savedArtifactId: event.target.value, answerColumn: chosen?.columns.includes(params.answerColumn) ? params.answerColumn : chosen?.columns[0] ?? 'answer' })
            }}>
              <option value="">Choose saved answers</option>
              {sources.map(({ artifact }) => <option key={artifact.id} value={artifact.id}>{runLabel(artifact)} · {resultCount(artifact).toLocaleString()} answers</option>)}
            </select>
          )}</Field>
          {!sources.length && <Notice tone="quiet">No saved answers cover these records yet. Run “Answer questions with a model server” first.</Notice>}
          {source && source.columns.length > 1 && (
            <Field label="Column">{id => (
              <select id={id} className="select" value={params.answerColumn} onChange={event => set({ answerColumn: event.target.value })}>
                {source.columns.map(column => <option key={column} value={column}>{column}</option>)}
              </select>
            )}</Field>
          )}
        </>
      )}

      {processorId === 'vlm.judge' && (
        <>
          <Field label="Reference answers" hint="The field holding the human or gold answers the verdict is judged against.">{id => (
            <select id={id} className="select" value={params.referenceField} onChange={event => set({ referenceField: event.target.value })}>
              <option value="">None</option>
              {referenceChoices.map(field => <option key={field.id} value={field.id}>{field.name || field.id} · {field.namespace}</option>)}
            </select>
          )}</Field>
          <label className="facet-opt"><input type="checkbox" checked={params.explain} onChange={event => set({ explain: event.target.checked })} /><span>Ask for a one-line reason with each verdict</span></label>
        </>
      )}

      {processorId === 'score.vqa_accuracy' && (
        <p className="hint">Scores each answer with the official VQA accuracy, min(1, matching human answers ÷ 3), averaged over leave-one-annotator-out subsets, against the human answers in <code>source.answers</code>. No model is called.</p>
      )}

      {processorId === 'embed.api' && (
        <>
          <Field label="Embed" hint="What is turned into a vector for each record.">{id => (
            <select id={id} className="select" value={params.representation} onChange={event => set({ representation: event.target.value as ModelParams['representation'] })}>
              <option value="question">The question</option><option value="text">The text</option>
            </select>
          )}</Field>
          <Field label="Document prefix" hint="Some retrieval models want one, such as “passage: ”. It changes the stored vectors, so it is part of the space’s identity.">{id => <input id={id} className="input" maxLength={200} value={params.documentPrefix} onChange={event => set({ documentPrefix: event.target.value })} />}</Field>
          <Field label="Query prefix" hint="Added in front of a search text, such as “query: ”.">{id => <input id={id} className="input" maxLength={200} value={params.queryPrefix} onChange={event => set({ queryPrefix: event.target.value })} />}</Field>
          <div className="row" style={{ gap: 8 }}>
            <Field label="Texts per request">{id => <input id={id} className="input" type="number" min={1} max={512} placeholder="64" value={params.batchSize} onChange={event => set({ batchSize: event.target.value })} />}</Field>
            <Field label="Parallel requests">{id => <input id={id} className="input" type="number" min={1} max={64} placeholder="8" value={params.concurrency} onChange={event => set({ concurrency: event.target.value })} />}</Field>
          </div>
        </>
      )}
    </>
  )
}
