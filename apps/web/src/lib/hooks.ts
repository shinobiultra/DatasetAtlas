import { useCallback, useEffect, useRef, useState } from 'react'

/** A view preference that survives reloads. Never used for credentials. */
export function useStoredState<T>(key: string, fallback: T): [T, (value: T | ((current: T) => T)) => void] {
  const [value, setValue] = useState<T>(() => {
    try {
      const raw = localStorage.getItem(key)
      return raw === null ? fallback : JSON.parse(raw) as T
    } catch { return fallback }
  })
  const update = useCallback((next: T | ((current: T) => T)) => {
    setValue(current => {
      const resolved = typeof next === 'function' ? (next as (current: T) => T)(current) : next
      try { localStorage.setItem(key, JSON.stringify(resolved)) } catch { /* private mode */ }
      return resolved
    })
  }, [key])
  return [value, update]
}

export function useDebounced<T>(value: T, delay = 180): T {
  const [settled, setSettled] = useState(value)
  useEffect(() => {
    const timer = setTimeout(() => setSettled(value), delay)
    return () => clearTimeout(timer)
  }, [value, delay])
  return settled
}

/** Element size, for virtualization and responsive layout decisions. */
export function useElementSize<T extends HTMLElement>(): [React.RefObject<T | null>, { width: number; height: number }] {
  const ref = useRef<T>(null)
  const [size, setSize] = useState({ width: 0, height: 0 })
  useEffect(() => {
    const element = ref.current
    if (!element) return
    const observer = new ResizeObserver(entries => {
      const box = entries[0]?.contentRect
      if (box) setSize(current => (current.width === box.width && current.height === box.height ? current : { width: box.width, height: box.height }))
    })
    observer.observe(element)
    return () => observer.disconnect()
  }, [])
  return [ref, size]
}

/** Fire `onHit` when the sentinel scrolls into view — used for seamless paging. */
export function useInfiniteSentinel(onHit: () => void, enabled: boolean): React.RefObject<HTMLDivElement | null> {
  const ref = useRef<HTMLDivElement>(null)
  const callback = useRef(onHit)
  callback.current = onHit
  useEffect(() => {
    const element = ref.current
    if (!element || !enabled) return
    const observer = new IntersectionObserver(entries => {
      if (entries.some(entry => entry.isIntersecting)) callback.current()
    }, { rootMargin: '600px 0px' })
    observer.observe(element)
    return () => observer.disconnect()
  }, [enabled])
  return ref
}

export function useKey(handler: (event: KeyboardEvent) => void, deps: unknown[] = []): void {
  const callback = useRef(handler)
  callback.current = handler
  useEffect(() => {
    const listener = (event: KeyboardEvent) => callback.current(event)
    window.addEventListener('keydown', listener)
    return () => window.removeEventListener('keydown', listener)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)
}

/** True when the event came from a text entry, so shortcuts stay out of the way. */
export function inEditable(target: EventTarget | null): boolean {
  const element = target as HTMLElement | null
  if (!element) return false
  const tag = element.tagName
  return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || element.isContentEditable
}

/**
 * A drag handle that resizes a panel from its left edge.
 *
 * The width is persisted per key, clamped to the given bounds, and the pointer
 * is captured so the drag survives leaving the handle.
 */
export function usePanelResize(key: string, initial: number, min: number, max: number) {
  const [width, setWidth] = useStoredState<number>(key, initial)
  const onPointerDown = (event: React.PointerEvent<HTMLElement>) => {
    event.preventDefault()
    const startX = event.clientX
    const startWidth = width
    const target = event.currentTarget
    target.setPointerCapture(event.pointerId)
    const move = (moveEvent: PointerEvent) => {
      setWidth(Math.round(Math.min(max, Math.max(min, startWidth - (moveEvent.clientX - startX)))))
    }
    const stop = () => {
      target.releasePointerCapture?.(event.pointerId)
      target.removeEventListener('pointermove', move)
      target.removeEventListener('pointerup', stop)
      target.removeEventListener('pointercancel', stop)
    }
    target.addEventListener('pointermove', move)
    target.addEventListener('pointerup', stop)
    target.addEventListener('pointercancel', stop)
  }
  const onKeyDown = (event: React.KeyboardEvent<HTMLElement>) => {
    const step = event.shiftKey ? 48 : 16
    if (event.key === 'ArrowLeft') { event.preventDefault(); setWidth(current => Math.min(max, current + step)) }
    if (event.key === 'ArrowRight') { event.preventDefault(); setWidth(current => Math.max(min, current - step)) }
    if (event.key === 'Home') { event.preventDefault(); setWidth(initial) }
  }
  return { width, onPointerDown, onKeyDown, min, max }
}
