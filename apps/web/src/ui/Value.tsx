import { display, isMissing } from '../lib/format'

const LONG_VALUE = 140

/**
 * Structured and long values stay inspectable without flooding the first screenful.
 * Nothing is truncated away: the full value is one disclosure click below.
 */
export function Value({ value, inline = false }: { value: unknown; inline?: boolean }) {
  if (isMissing(value)) return <span className="tag-missing">—</span>
  const structured = typeof value === 'object'
  const text = display(value)
  if (!structured && text.length <= LONG_VALUE) return <>{text}</>
  const label = structured
    ? (Array.isArray(value) ? `${value.length} items` : `${Object.keys(value as object).length} keys`)
    : `${text.length.toLocaleString()} characters`
  return (
    <details className="disclosure" style={{ borderTop: 0 }}>
      <summary style={{ padding: '2px 0', fontWeight: 500, fontSize: 'var(--fs-sm)' }}>{label}</summary>
      <div className="body">
        {structured
          ? <pre className="raw">{JSON.stringify(value, null, 2)}</pre>
          : <p className="wrap-any" style={{ fontSize: 'var(--fs-sm)', lineHeight: 1.5, maxHeight: inline ? 200 : undefined, overflow: 'auto' }}>{text}</p>}
      </div>
    </details>
  )
}
