import { describe, expect, it } from 'vitest'
import { isViewerAsset, normalizeRows, rowsUrl } from './hfRows'

const viewer = 'https://datasets-server.huggingface.co/cached-assets/x/0/img/image.jpg?Expires=1&Signature=abc'

describe('live preview rows', () => {
  it('accepts only assets served by the viewer over https', () => {
    expect(isViewerAsset(viewer)).toBe(true)
    expect(isViewerAsset('http://datasets-server.huggingface.co/a.jpg')).toBe(false)
    expect(isViewerAsset('https://evil.example/a.jpg')).toBe(false)
    expect(isViewerAsset('https://datasets-server.huggingface.co.evil.example/a.jpg')).toBe(false)
    expect(isViewerAsset('javascript:alert(1)')).toBe(false)
    expect(isViewerAsset(undefined)).toBe(false)
  })
  it('builds a rows URL with every parameter encoded', () => {
    const url = rowsUrl({ repo: 'a/b c', config: 'c&d', split: 'test' }, 5, 48)
    expect(url).toContain('dataset=a%2Fb+c')
    expect(url).toContain('config=c%26d')
    expect(url).toContain('offset=5&length=48')
  })
  it('names class labels, keeps viewer media and drops media from other hosts', () => {
    const page = normalizeRows({
      features: [{ name: 'img', type: { _type: 'Image' } }, { name: 'label', type: { _type: 'ClassLabel', names: ['cat', 'dog'] } }, { name: 'text', type: { _type: 'Value' } }, { name: 'other', type: { _type: 'Image' } }],
      rows: [{ row_idx: 7, row: { img: { src: viewer }, label: 1, text: 'hello', other: { src: 'https://evil.example/x.png' } } }],
      num_rows_total: 10000,
    })
    expect(page.total).toBe(10000)
    expect(page.rows[0].media).toEqual([{ kind: 'image', src: viewer }])
    expect(page.rows[0].fields).toEqual([{ name: 'label', text: 'dog' }, { name: 'text', text: 'hello' }])
    expect(page.rows[0].index).toBe(7)
  })
  it('clips long text and shows structured cells as JSON', () => {
    const page = normalizeRows({ features: [{ name: 'a', type: { _type: 'Value' } }, { name: 'b', type: {} }], rows: [{ row_idx: 0, row: { a: 'x'.repeat(500), b: { k: [1, 2] } } }] })
    expect(page.rows[0].fields[0].text.length).toBe(220)
    expect(page.rows[0].fields[1].text).toBe('{"k":[1,2]}')
  })
})
