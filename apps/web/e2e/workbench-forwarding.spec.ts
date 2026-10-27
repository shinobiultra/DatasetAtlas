import { expect, test } from '@playwright/test'
import { workbenchResponseHeaders } from './helpers'

test('live workbench forwarding preserves binary and media metadata without forwarding credentials', () => {
  const headers = workbenchResponseHeaders(new Response(null, { headers: {
    'Content-Type': 'application/octet-stream', 'Content-Length': '4',
    'Content-Range': 'bytes 0-3/4', 'Accept-Ranges': 'bytes',
    'X-Atlas-Dtype': 'uint8', 'X-Atlas-Shape': '4', 'X-Atlas-Column': 'synthetic',
    'X-Atlas-Media-Representation': 'original', 'X-Atlas-Original-SHA256': 'synthetic-only',
    'Cache-Control': 'private, max-age=0', ETag: '"synthetic"',
    'Set-Cookie': 'private=secret', Authorization: 'Bearer secret', 'Proxy-Authenticate': 'secret',
  } }))
  expect(headers).toEqual({
    'content-type': 'application/octet-stream', 'content-length': '4',
    'content-range': 'bytes 0-3/4', 'accept-ranges': 'bytes',
    'x-atlas-dtype': 'uint8', 'x-atlas-shape': '4', 'x-atlas-column': 'synthetic',
    'x-atlas-media-representation': 'original', 'x-atlas-original-sha256': 'synthetic-only',
    'cache-control': 'private, max-age=0', etag: '"synthetic"',
  })
})
