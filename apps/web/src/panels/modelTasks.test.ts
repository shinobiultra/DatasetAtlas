import { describe, expect, it } from 'vitest'
import type { Artifact } from '../generated'
import { emptyModelParams, isLoopbackUrl, modelConfig, tagSchema, textSources, type ModelParams, type Preset } from './modelTasks'

const preset: Preset = { template: 'Answer.\nQuestion: {question}', use_images: true, max_tokens: 24 }
const params = (patch: Partial<ModelParams> = {}): ModelParams => ({ ...emptyModelParams(), providerId: 'local', ...patch })
const artifact = (id: string, texts: string[], extra: Partial<Artifact> = {}) => ({
  id, kind: 'vlm.answer', unit: 'example', snapshot_ids: ['s1'], ids: [],
  data: { bulk: { dir: 'x', count: 3, arrays: {}, ...(texts.length ? { texts: Object.fromEntries(texts.map(name => [name, { file: `${name}.json`, bytes: 1, sha256: 'a' }])) } : {}) } }, ...extra,
}) as Artifact

describe('model run configuration', () => {
  it('sends only what differs from the processor, and always names the server', () => {
    expect(modelConfig('vlm.answer', params(), preset)).toEqual({ config: { provider_id: 'local' }, problems: [] })
    const changed = modelConfig('vlm.answer', params({ template: 'Say it: {question}', useImages: false, maxTokens: '8', thinking: 'off', concurrency: '4' }), preset)
    expect(changed.config).toEqual({ provider_id: 'local', template: 'Say it: {question}', use_images: false, max_tokens: 8, thinking: false, concurrency: 4 })
    expect(modelConfig('vlm.answer', params({ template: '  Answer.\nQuestion: {question}  ' }), preset).config).not.toHaveProperty('template')
    expect(modelConfig('vlm.answer', params({ providerId: '' }), preset).problems).toEqual(['Choose a model server.'])
  })

  it('ignores a number that is not a whole number instead of sending a wrong request', () => {
    const { config } = modelConfig('vlm.answer', params({ maxTokens: '8.5', concurrency: 'many' }), preset)
    expect(config).toEqual({ provider_id: 'local' })
  })

  it('builds a tag schema and says what is wrong with it', () => {
    const good = tagSchema([{ name: 'topic', type: 'enum', values: 'a, b ,a, c', description: 'the subject' }, { name: 'ok', type: 'boolean', values: '', description: '' }])
    expect(good.problems).toEqual([])
    expect(good.schema).toEqual([{ name: 'topic', type: 'enum', values: ['a', 'b', 'c'], description: 'the subject' }, { name: 'ok', type: 'boolean' }])
    const bad = tagSchema([{ name: 'Topic', type: 'enum', values: 'a', description: '' }, { name: 'status', type: 'string', values: '', description: '' }, { name: 'x', type: 'string', values: '', description: '' }, { name: 'x', type: 'number', values: '', description: '' }])
    expect(bad.problems).toHaveLength(4)
    expect(tagSchema([{ name: '', type: 'enum', values: '', description: '' }]).problems).toEqual(['Add at least one tag field.'])
  })

  it('needs saved answers to judge or score, and reads the chosen column', () => {
    expect(modelConfig('vlm.judge', params(), preset).problems).toEqual(['Choose the saved answers to judge.'])
    const judge = modelConfig('vlm.judge', params({ savedArtifactId: 'a1', answerColumn: 'answer', referenceField: 'source.answers', explain: true }), preset)
    expect(judge).toEqual({ config: { provider_id: 'local', candidate_artifact_id: 'a1', answer_column: 'answer', reference_field: 'source.answers', explain: true }, problems: [] })
    const score = modelConfig('score.vqa_accuracy', params({ savedArtifactId: 'a1', answerColumn: 'answer' }))
    expect(score.config).toEqual({ answers_artifact_id: 'a1', answer_column: 'answer' })
    expect(score.config).not.toHaveProperty('provider_id')  // scoring calls no model
    expect(modelConfig('score.vqa_accuracy', params()).problems).toEqual(['Choose the saved answers to score.'])
  })

  it('configures API embeddings, including the two prefixes', () => {
    expect(modelConfig('embed.api', params({ representation: 'text', documentPrefix: 'passage: ', queryPrefix: 'query: ', batchSize: '32' })).config)
      .toEqual({ provider_id: 'local', representation: 'text', document_prefix: 'passage: ', query_prefix: 'query: ', batch_size: 32 })
    expect(modelConfig('embed.api', params()).config).toEqual({ provider_id: 'local', representation: 'question' })
  })
})

describe('what the form may choose from', () => {
  it('offers only saved text columns of the same unit and snapshots', () => {
    const answers = artifact('answers', ['answer'])
    const sources = textSources([answers, artifact('numbers', []), artifact('other-unit', ['answer'], { unit: 'asset' }), artifact('other-snapshot', ['answer'], { snapshot_ids: ['s2'] })], 'example', ['s1'])
    expect(sources.map(source => source.artifact.id)).toEqual(['answers'])
    expect(sources[0].columns).toEqual(['answer'])
    expect(textSources([answers], 'example', undefined)).toHaveLength(1)
  })

  it('treats only this machine as a place dataset contents may go', () => {
    for (const url of ['http://127.0.0.1:8001/v1', 'http://localhost:11434/v1', 'http://[::1]:1234/v1', 'http://127.0.1.1/v1']) expect(isLoopbackUrl(url)).toBe(true)
    for (const url of ['http://192.168.1.5:8000/v1', 'https://api.example.com/v1', 'http://127.0.0.1.evil.test/v1', 'not a url', undefined]) expect(isLoopbackUrl(url)).toBe(false)
  })
})
