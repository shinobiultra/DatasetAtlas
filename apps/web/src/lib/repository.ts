/** `https://<owner>.github.io/<repo>/` is served from `https://github.com/<owner>/<repo>`; anywhere else there is no repository link to guess. */
export function repositoryUrl(location: Pick<Location, 'hostname' | 'pathname'> = window.location): string | null {
  const match = /^([a-z0-9-]+)\.github\.io$/i.exec(location.hostname)
  const repo = location.pathname.split('/').filter(Boolean)[0]
  return match && repo ? `https://github.com/${match[1]}/${repo}` : null
}
