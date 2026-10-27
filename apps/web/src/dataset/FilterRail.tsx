import { useEffect, useMemo, useState } from 'react'
import type { FieldDescriptor, Query } from '../generated'
import { provider, type AggregateResponse } from '../provider'
import { display, fieldOrigin, titleCase } from '../lib/format'
import { Facet, FacetList, FacetOption, Field, Notice, Spinner } from '../ui/primitives'
import type { Clause } from './model'
import { describeClause } from './model'
import * as Icon from '../ui/Icons'

const MAX_FACET_FIELDS = 8
const MAX_KNOWN_FACET_VALUES = 160

function facetable(field: FieldDescriptor): boolean {
  if (field.dtype === 'array' || field.dtype === 'object') return false
  return field.dtype === 'category' || field.dtype === 'boolean' || Boolean(field.values?.length)
}

export type RailProps = {
  datasetId: string
  fields: FieldDescriptor[]
  clauses: Clause[]
  baseQuery: Query | null
  onAdd: (clause: Clause) => void
  onRemove: (key: string) => void
  onClear: () => void
  matchedCount: number | null
}

/** Sample filters. Every computed field keeps the run it came from visible. */
export function FilterRail({ datasetId, fields, clauses, baseQuery, onAdd, onRemove, onClear, matchedCount }: RailProps) {
  const facetFields = useMemo(() => fields.filter(facetable).slice(0, MAX_FACET_FIELDS), [fields])
  const numericFields = useMemo(() => fields.filter(field => field.dtype === 'number'), [fields])
  const [counts, setCounts] = useState<AggregateResponse | null>(null)
  const [countError, setCountError] = useState('')
  const [loading, setLoading] = useState(false)
  const facetIds = facetFields.map(field => field.id).join('|')
  const knownChoices = useMemo(() => new Map<string, Set<string>>(), [datasetId, baseQuery?.snapshot_id, baseQuery?.unit, baseQuery?.population_scope, facetIds])

  const signature = baseQuery ? JSON.stringify({ ...baseQuery, limit: 0, cursor: null }) : ''
  useEffect(() => {
    setCounts(null); setCountError('')
    if (!baseQuery || !facetFields.length) { setLoading(false); return }
    let live = true
    const controller = new AbortController()
    setLoading(true)
    const timer = setTimeout(() => {
      provider.aggregate(datasetId, { ...baseQuery, limit: 1, cursor: null }, facetFields.map(field => field.id), 40, controller.signal)
        .then(response => {
          if (!live) return
          for (const result of response.results) {
            if (result.kind !== 'categorical') continue
            const values = knownChoices.get(result.field_id) ?? new Set<string>()
            for (const item of result.counts) {
              if (values.size >= MAX_KNOWN_FACET_VALUES) break
              values.add(item.value)
            }
            knownChoices.set(result.field_id, values)
          }
          setCounts(response); setLoading(false)
        })
        .catch(failure => { if (live) { setCountError(String(failure instanceof Error ? failure.message : failure)); setCounts(null); setLoading(false) } })
    }, 150)
    return () => { live = false; clearTimeout(timer); controller.abort() }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [datasetId, signature, facetIds, knownChoices])

  const grouped = useMemo(() => {
    const map = new Map<string, FieldDescriptor[]>()
    for (const field of facetFields) {
      const origin = fieldOrigin(field)
      map.set(origin, [...(map.get(origin) ?? []), field])
    }
    return [...map]
  }, [facetFields])

  const clauseFor = (fieldId: string, value: string) => clauses.find(clause => clause.source === 'facet' && clause.fieldId === fieldId && clause.op === 'eq' && display(clause.value) === value)

  function toggleValue(field: FieldDescriptor, raw: string) {
    const existing = clauseFor(field.id, raw)
    if (existing) { onRemove(existing.key); return }
    // Recover the original typed value: category columns keep real types in `values`.
    const typed = field.values?.find(value => display(value) === raw)
      ?? (field.dtype === 'boolean' ? raw === 'true' : field.dtype === 'number' ? Number(raw) : raw)
    onAdd({
      key: `facet:${field.id}:eq:${JSON.stringify(typed)}`, fieldId: field.id, fieldName: field.name, op: 'eq', value: typed, source: 'facet',
      label: describeClause(field, 'eq', typed),
    })
  }

  return (
    <>
      <div className="rail-head">
        <h3>Filters</h3>
        {clauses.length > 0 && <button type="button" className="linkish" style={{ marginLeft: 'auto', fontSize: 'var(--fs-sm)' }} onClick={onClear}>Reset</button>}
      </div>
      <div className="rail-scroll">
        {countError && <Notice tone="warn">Facet counts unavailable: {countError}</Notice>}
        {loading && !counts && <div style={{ padding: '8px 0' }}><Spinner label="Counting…" /></div>}

        {grouped.map(([origin, items]) => (
          <div key={origin}>
            {items.map(field => {
              const result = counts?.results.find(entry => entry.field_id === field.id)
              const categorical = result?.kind === 'categorical' ? result : null
              const options = [...(categorical?.counts ?? [])]
              const known = new Set(options.map(option => option.value))
              const choices = [
                ...(field.values ?? []).map(display),
                ...(knownChoices.get(field.id) ?? []),
                ...clauses.filter(clause => clause.source === 'facet' && clause.fieldId === field.id && clause.op === 'eq').map(clause => display(clause.value)),
              ]
              for (const value of choices) {
                if (known.has(value)) continue
                known.add(value)
                // Truncated counts cannot establish zero for an omitted value.
                options.push({ value, count: categorical && !categorical.truncated ? 0 : -1 })
              }
              const missingClause = clauses.find(clause => clause.source === 'facet' && clause.fieldId === field.id && clause.op === 'is_null')
              if (!options.length && !categorical?.missing && !missingClause) return null
              const active = clauses.filter(clause => clause.fieldId === field.id).length
              return (
                <Facet key={`${field.unit}:${field.id}`} title={field.name} origin={origin} count={active || undefined} defaultOpen={options.length <= 12 || active > 0}>
                  <FacetList
                    items={options.map(option => ({ key: option.value }))}
                    initial={7}
                    render={item => {
                      const option = options.find(entry => entry.value === item.key)!
                      return (
                        <FacetOption
                          key={item.key}
                          checked={Boolean(clauseFor(field.id, item.key))}
                          onChange={() => toggleValue(field, item.key)}
                          label={item.key === '' ? '(empty)' : item.key}
                          count={option.count >= 0 ? option.count : undefined}
                          title={`${field.name} = ${item.key}`}
                        />
                      )
                    }}
                  />
                  {result && result.kind === 'categorical' && result.truncated && <p className="hint" style={{ paddingTop: 4 }}>Showing the most frequent values only.</p>}
                  {categorical && (categorical.missing > 0 || missingClause) && (
                    <FacetOption
                      checked={Boolean(missingClause)}
                      onChange={checked => {
                        if (missingClause) onRemove(missingClause.key)
                        if (checked && !missingClause) onAdd({ key: `facet:${field.id}:is_null`, fieldId: field.id, fieldName: field.name, op: 'is_null', value: true, source: 'facet', label: describeClause(field, 'is_null', true) })
                      }}
                      label="Missing" count={categorical.missing}
                    />
                  )}
                </Facet>
              )
            })}
          </div>
        ))}

        {numericFields.length > 0 && (
          <Facet title="Numeric range" defaultOpen={false}>
            <NumericFilter fields={numericFields} onAdd={onAdd} />
          </Facet>
        )}

        <Facet title="Other fields" defaultOpen={false} origin="Any registered field and operation">
          <CustomFilter fields={fields} onAdd={onAdd} />
        </Facet>

        {clauses.length > 0 && (
          <Facet title={`Applied (${clauses.length})`}>
            {clauses.map(clause => (
              <div key={clause.key} className="facet-opt" style={{ cursor: 'default' }}>
                <span className="truncate" title={clause.label}>{clause.label}</span>
                <button type="button" className="btn ghost icon sm count" onClick={() => onRemove(clause.key)} aria-label={`Remove filter ${clause.label}`}><Icon.Close size={12} /></button>
              </div>
            ))}
          </Facet>
        )}
      </div>
      <div className="rail-foot">
        {matchedCount === null ? 'Count unavailable' : `${matchedCount.toLocaleString()} matching`}
        {counts && <span className="truncate" title={counts.warnings.join(' ')} style={{ marginLeft: 'auto', fontSize: 'var(--fs-xs)' }}>{counts.population_scope}</span>}
      </div>
    </>
  )
}

function NumericFilter({ fields, onAdd }: { fields: FieldDescriptor[]; onAdd: (clause: Clause) => void }) {
  const [fieldId, setFieldId] = useState(fields[0]?.id ?? '')
  const [op, setOp] = useState('gte')
  const [value, setValue] = useState('')
  const field = fields.find(item => item.id === fieldId)
  return (
    <div className="col" style={{ gap: 8, paddingTop: 4 }}>
      <select className="select" value={fieldId} onChange={event => setFieldId(event.target.value)} aria-label="Numeric field">
        {fields.map(item => <option key={`${item.unit}:${item.id}`} value={item.id}>{item.name}</option>)}
      </select>
      <div className="row" style={{ gap: 6 }}>
        <select className="select" style={{ width: 78 }} value={op} onChange={event => setOp(event.target.value)} aria-label="Comparison">
          <option value="gte">≥</option><option value="gt">&gt;</option><option value="lte">≤</option><option value="lt">&lt;</option><option value="eq">=</option>
        </select>
        <input className="input" type="number" value={value} onChange={event => setValue(event.target.value)} placeholder="Value" aria-label="Threshold" />
      </div>
      <button
        type="button" className="btn" disabled={!field || value.trim() === ''}
        onClick={() => {
          if (!field) return
          const number = Number(value)
          onAdd({ key: `${field.id}:${op}:${number}`, fieldId: field.id, fieldName: field.name, op, value: number, label: describeClause(field, op, number) })
          setValue('')
        }}
      >
        <Icon.Plus size={13} />Add filter
      </button>
    </div>
  )
}

function CustomFilter({ fields, onAdd }: { fields: FieldDescriptor[]; onAdd: (clause: Clause) => void }) {
  const [fieldId, setFieldId] = useState('')
  const [op, setOp] = useState('eq')
  const [value, setValue] = useState('')
  const field = fields.find(item => item.id === fieldId)
  const ops = field?.query_ops ?? ['eq']
  const grouped = useMemo(() => {
    const map = new Map<string, FieldDescriptor[]>()
    for (const item of fields) map.set(fieldOrigin(item), [...(map.get(fieldOrigin(item)) ?? []), item])
    return [...map]
  }, [fields])
  return (
    <div className="col" style={{ gap: 8, paddingTop: 4 }}>
      <Field label="Field">{id => (
        <select id={id} className="select" value={fieldId} onChange={event => { setFieldId(event.target.value); setOp('eq'); setValue('') }}>
          <option value="">Choose a field</option>
          {grouped.map(([origin, items]) => (
            <optgroup key={origin} label={origin}>
              {items.map(item => <option key={`${item.unit}:${item.id}`} value={item.id}>{titleCase(item.name)}</option>)}
            </optgroup>
          ))}
        </select>
      )}</Field>
      {field && (
        <>
          <Field label="Operation">{id => (
            <select id={id} className="select" value={op} onChange={event => setOp(event.target.value)}>
              {ops.map(value => <option key={value} value={value}>{value}</option>)}
            </select>
          )}</Field>
          <Field label="Value" hint={op === 'in' ? 'Comma separated' : undefined}>{id => (
            op === 'is_null'
              ? <select id={id} className="select" value={value || 'true'} onChange={event => setValue(event.target.value)}><option value="true">Is missing</option><option value="false">Is present</option></select>
              : <input id={id} className="input" value={value} onChange={event => setValue(event.target.value)} placeholder="Value" />
          )}</Field>
          <button
            type="button" className="btn" disabled={op !== 'is_null' && !value.trim()}
            onClick={() => {
              const parse = (raw: string): unknown => {
                const match = field.values?.find(item => display(item) === raw)
                if (match !== undefined) return match
                if (field.dtype === 'number') return Number(raw)
                if (field.dtype === 'boolean') return raw === 'true'
                return raw
              }
              const typed = op === 'is_null' ? (value || 'true') === 'true' : op === 'in' ? value.split(',').map(part => parse(part.trim())) : parse(value)
              onAdd({ key: `${field.id}:${op}:${JSON.stringify(typed)}`, fieldId: field.id, fieldName: field.name, op, value: typed, label: describeClause(field, op, typed) })
              setValue('')
            }}
          >
            <Icon.Plus size={13} />Add filter
          </button>
        </>
      )}
    </div>
  )
}
