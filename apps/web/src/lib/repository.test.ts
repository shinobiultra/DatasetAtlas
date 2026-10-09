import { describe, expect, it } from 'vitest'
import { repositoryUrl } from './repository'

describe('repositoryUrl', () => {
  it('derives the repository from a GitHub Pages project site', () => {
    expect(repositoryUrl({ hostname: 'shinobiultra.github.io', pathname: '/DatasetAtlas/' })).toBe('https://github.com/shinobiultra/DatasetAtlas')
  })
  it('does not guess for another host or a user site without a repository path', () => {
    expect(repositoryUrl({ hostname: '127.0.0.1', pathname: '/' })).toBeNull()
    expect(repositoryUrl({ hostname: 'example.org', pathname: '/DatasetAtlas/' })).toBeNull()
    expect(repositoryUrl({ hostname: 'someone.github.io', pathname: '/' })).toBeNull()
  })
})
