import { useEffect, useId, useRef, useState, type ReactNode } from 'react'
import * as Icon from './Icons'

export function Chip({ children, onRemove, tone = 'accent', title }: { children: ReactNode; onRemove?: () => void; tone?: 'accent' | 'neutral'; title?: string }) {
  return (
    <span className={`chip${tone === 'neutral' ? ' neutral' : ''}`} title={title}>
      <span className="truncate">{children}</span>
      {onRemove && <button type="button" className="x" onClick={onRemove} aria-label="Remove filter"><Icon.Close size={13} /></button>}
    </span>
  )
}

export function Tag({ children, tone = 'default', title }: { children: ReactNode; tone?: 'default' | 'accent' | 'ok' | 'warn' | 'danger'; title?: string }) {
  return <span className={`tag${tone === 'default' ? '' : ` ${tone}`}`} title={title}>{children}</span>
}

export function Segmented<T extends string>({ value, options, onChange, label }: {
  value: T
  options: Array<{ value: T; label: string; icon?: ReactNode }>
  onChange: (value: T) => void
  label: string
}) {
  return (
    <div className="segmented" role="group" aria-label={label}>
      {options.map(option => (
        <button key={option.value} type="button" aria-pressed={value === option.value} onClick={() => onChange(option.value)} title={option.label}>
          {option.icon}
          <span>{option.label}</span>
        </button>
      ))}
    </div>
  )
}

export function Tabs<T extends string>({ value, options, onChange, label }: {
  value: T; options: Array<{ value: T; label: string }>; onChange: (value: T) => void; label: string
}) {
  return (
    <div className="tabs" role="tablist" aria-label={label}>
      {options.map(option => (
        <button key={option.value} role="tab" type="button" aria-selected={value === option.value} onClick={() => onChange(option.value)}>
          {option.label}
        </button>
      ))}
    </div>
  )
}

/** A popover anchored to its trigger. Closes on outside click and Escape. */
export function Popover({ trigger, children, align = 'right', label }: {
  trigger: (open: boolean) => ReactNode; children: (close: () => void) => ReactNode; align?: 'left' | 'right'; label: string
}) {
  const [open, setOpen] = useState(false)
  const wrap = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!open) return
    const onDown = (event: MouseEvent) => { if (!wrap.current?.contains(event.target as Node)) setOpen(false) }
    const onKey = (event: KeyboardEvent) => { if (event.key === 'Escape') { setOpen(false); event.stopPropagation() } }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey, true)
    return () => { document.removeEventListener('mousedown', onDown); document.removeEventListener('keydown', onKey, true) }
  }, [open])
  return (
    <div className="pop" ref={wrap}>
      <button type="button" className="btn" aria-expanded={open} aria-haspopup="dialog" aria-label={label} onClick={() => setOpen(value => !value)}>
        {trigger(open)}
      </button>
      {open && <div className={`pop-panel${align === 'left' ? ' left' : ''}`} role="dialog" aria-label={label}>{children(() => setOpen(false))}</div>}
    </div>
  )
}

export function Notice({ tone = 'info', children, onDismiss }: { tone?: 'info' | 'warn' | 'error' | 'quiet'; children: ReactNode; onDismiss?: () => void }) {
  const className = `notice${tone === 'info' ? '' : ` ${tone}`}`
  const icon = tone === 'error' || tone === 'warn' ? <Icon.Warning size={15} /> : <Icon.Info size={15} />
  return (
    <div className={className} role={tone === 'error' ? 'alert' : 'status'}>
      <span style={{ flex: 'none', marginTop: 1 }}>{icon}</span>
      <div style={{ minWidth: 0 }}>{children}</div>
      {onDismiss && <button type="button" className="x btn ghost sm icon" onClick={onDismiss} aria-label="Dismiss"><Icon.Close size={13} /></button>}
    </div>
  )
}

export function Empty({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="empty">
      <h3>{title}</h3>
      {children && <p>{children}</p>}
      {action}
    </div>
  )
}

export function Field({ label, hint, children, id }: { label: string; hint?: ReactNode; children: (id: string) => ReactNode; id?: string }) {
  const generated = useId()
  const fieldId = id ?? generated
  return (
    <div className="field">
      <label className="label" htmlFor={fieldId}>{label}</label>
      {children(fieldId)}
      {hint && <div className="hint">{hint}</div>}
    </div>
  )
}

export function Facet({ title, origin, defaultOpen = true, children, count }: {
  title: string; origin?: string; defaultOpen?: boolean; children: ReactNode; count?: number
}) {
  return (
    <details className="facet" open={defaultOpen}>
      <summary>
        <span>{title}</span>
        {count !== undefined && <span className="count" style={{ marginLeft: 'auto', paddingRight: 6 }}>{count}</span>}
        {origin && <span className="facet-origin">{origin}</span>}
      </summary>
      <div className="facet-body">{children}</div>
    </details>
  )
}

export function FacetOption({ checked, onChange, label, count, title }: {
  checked: boolean; onChange: (checked: boolean) => void; label: ReactNode; count?: number | string; title?: string
}) {
  return (
    <label className="facet-opt" title={title}>
      <input type="checkbox" checked={checked} onChange={event => onChange(event.target.checked)} />
      <span>{label}</span>
      {count !== undefined && <span className="count">{typeof count === 'number' ? count.toLocaleString() : count}</span>}
    </label>
  )
}

/** A facet list that shows the first `initial` options and expands on request. */
export function FacetList({ items, initial = 6, render }: {
  items: Array<{ key: string }>; initial?: number; render: (item: { key: string }, index: number) => ReactNode
}) {
  const [expanded, setExpanded] = useState(false)
  const shown = expanded ? items : items.slice(0, initial)
  return (
    <>
      {shown.map((item, index) => render(item, index))}
      {items.length > initial && (
        <button type="button" className="linkish facet-more" onClick={() => setExpanded(value => !value)}>
          {expanded ? 'Show fewer' : `Show ${items.length - initial} more`}
        </button>
      )}
    </>
  )
}

export function Spinner({ label }: { label?: string }) {
  return <span className="row" style={{ gap: 7, color: 'var(--text-muted)', fontSize: 'var(--fs-sm)' }}><span className="spinner" />{label}</span>
}

export function CopyButton({ value, label = 'Copy ID' }: { value: string; label?: string }) {
  const [done, setDone] = useState(false)
  return (
    <button
      type="button" className="btn sm"
      onClick={() => { navigator.clipboard?.writeText(value).then(() => { setDone(true); setTimeout(() => setDone(false), 1400) }).catch(() => setDone(false)) }}
    >
      <Icon.Copy size={13} />{done ? 'Copied' : label}
    </button>
  )
}
