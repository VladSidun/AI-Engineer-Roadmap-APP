import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { PointerEvent as ReactPointerEvent, RefObject } from 'react'
import type { Camera, Point } from '../../lib/api'
import { boundCamera, zoomAt } from './camera'
import type { Size } from './camera'

type Target = Camera | ((camera: Camera) => Camera)
type Flight = { from: Camera; to: Camera; started: number }
const midpoint = ([a, b]: Point[]) => b ? { x: (a!.x + b.x) / 2, y: (a!.y + b.y) / 2 } : a!
const separation = ([a, b]: Point[]) => b ? Math.max(1, Math.hypot(a!.x - b.x, a!.y - b.y)) : 1
const distance = (a: Point, b: Point) => Math.hypot(a.x - b.x, a.y - b.y)

export function useCamera(element: RefObject<HTMLDivElement | null>, initial: Camera, world: Size, save: (camera: Camera) => void) {
  const [size, setSize] = useState({ width: 1, height: 1 })
  const [rendered, setRendered] = useState(initial)
  const [dragging, setDragging] = useState(false)
  const camera = useMemo(() => boundCamera(rendered, size, world), [rendered, size, world])
  const live = useRef(initial)
  const frame = useRef<number | null>(null)
  const flight = useRef<Flight | null>(null)
  const wheelSave = useRef<ReturnType<typeof setTimeout> | null>(null)
  const viewport = useRef(size)
  const saver = useRef(save)
  const points = useRef(new Map<number, Point>())
  const bounds = useRef<DOMRect | null>(null)
  const origin = useRef<Point | null>(null)
  const dragged = useRef(false)
  const blockClick = useRef(false)

  useEffect(() => { saver.current = save }, [save])
  useEffect(() => {
    const surface = element.current
    if (!surface) return
    const resize = new ResizeObserver(([entry]) => {
      if (!entry || entry.contentRect.width <= 0 || entry.contentRect.height <= 0) return
      const next = { width: entry.contentRect.width, height: entry.contentRect.height }
      live.current = boundCamera(live.current, next, world)
      viewport.current = next
      setSize(next)
    })
    resize.observe(surface)
    return () => resize.disconnect()
  }, [element, world])

  const stopFlight = useCallback(() => {
    if (!flight.current) return
    if (frame.current !== null) cancelAnimationFrame(frame.current)
    frame.current = null
    flight.current = null
  }, [])

  const clearWheelSave = useCallback(() => {
    if (wheelSave.current !== null) clearTimeout(wheelSave.current)
    wheelSave.current = null
  }, [])

  const commit = useCallback((next: Camera) => {
    clearWheelSave()
    saver.current(next)
  }, [clearWheelSave])

  const renderSoon = useCallback(() => {
    if (frame.current !== null) return
    frame.current = requestAnimationFrame(() => {
      frame.current = null
      setRendered(live.current)
    })
  }, [])

  const update = useCallback((target: Target, motion: 'animate' | 'instant' = 'animate') => {
    const prior = flight.current?.to ?? live.current
    const next = boundCamera(typeof target === 'function' ? target(prior) : target, viewport.current, world)
    stopFlight()
    clearWheelSave()
    if (motion === 'instant' || window.matchMedia('(prefers-reduced-motion: reduce)').matches ||
        (distance(live.current, next) < .01 && Math.abs(live.current.zoom - next.zoom) < .0001)) {
      live.current = next
      renderSoon()
      commit(next)
      return
    }
    if (frame.current !== null) cancelAnimationFrame(frame.current)
    const transition = { from: live.current, to: next, started: performance.now() }
    flight.current = transition
    const step = (time: number) => {
      const fraction = Math.max(0, Math.min(1, (time - transition.started) / 230))
      const eased = 1 - (1 - fraction) ** 3
      const { from, to } = transition
      live.current = boundCamera({
        x: from.x + (to.x - from.x) * eased,
        y: from.y + (to.y - from.y) * eased,
        zoom: from.zoom * (to.zoom / from.zoom) ** eased,
      }, viewport.current, world)
      setRendered(live.current)
      if (fraction < 1) frame.current = requestAnimationFrame(step)
      else {
        frame.current = null
        flight.current = null
        commit(live.current)
      }
    }
    frame.current = requestAnimationFrame(step)
  }, [clearWheelSave, commit, renderSoon, stopFlight, world])

  useEffect(() => {
    const flush = () => {
      const pending = flight.current?.to ?? live.current
      if (flight.current || wheelSave.current !== null || (points.current.size && dragged.current)) {
        stopFlight()
        commit(pending)
      }
    }
    window.addEventListener('pagehide', flush)
    return () => {
      window.removeEventListener('pagehide', flush)
      flush()
      if (frame.current !== null) cancelAnimationFrame(frame.current)
      frame.current = null
    }
  }, [commit, stopFlight])

  useEffect(() => {
    const surface = element.current
    if (!surface) return
    const wheel = (event: WheelEvent) => {
      if (!event.ctrlKey && !event.metaKey && !surface.contains(document.activeElement)) return
      event.preventDefault()
      if (points.current.size) return
      stopFlight()
      const rect = surface.getBoundingClientRect()
      const anchor = { x: event.clientX - rect.left, y: event.clientY - rect.top }
      const screen = viewport.current
      const delta = event.deltaY * (event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? screen.height : 1)
      live.current = zoomAt(live.current, screen, world, anchor, anchor, Math.exp(-delta * .0017))
      renderSoon()
      clearWheelSave()
      wheelSave.current = setTimeout(() => commit(live.current), 150)
    }
    surface.addEventListener('wheel', wheel, { passive: false })
    return () => surface.removeEventListener('wheel', wheel)
  }, [clearWheelSave, commit, element, renderSoon, stopFlight, world])

  function point(event: ReactPointerEvent<HTMLDivElement>): Point {
    const rect = bounds.current!
    return { x: event.clientX - rect.left, y: event.clientY - rect.top }
  }

  function finishPointer(event: ReactPointerEvent<HTMLDivElement>) {
    if (!points.current.delete(event.pointerId) || points.current.size) return
    bounds.current = null
    origin.current = null
    if (dragged.current) {
      blockClick.current = true
      setDragging(false)
      commit(live.current)
    }
  }

  const handlers = {
    onPointerDown(event: ReactPointerEvent<HTMLDivElement>) {
      if (event.button !== 0 || points.current.size >= 2) return
      if (!points.current.size) {
        if (flight.current) {
          stopFlight()
          commit(live.current)
        }
        if (wheelSave.current !== null) commit(live.current)
        dragged.current = false
        blockClick.current = false
        bounds.current = event.currentTarget.getBoundingClientRect()
        origin.current = point(event)
        if (!(event.target instanceof Element) || !event.target.closest('[data-atlas-marker]')) {
          event.currentTarget.focus({ preventScroll: true })
        }
      }
      points.current.set(event.pointerId, point(event))
      if (points.current.size === 2) {
        dragged.current = true
        setDragging(true)
        for (const id of points.current.keys()) event.currentTarget.setPointerCapture(id)
      } else if (event.target instanceof Element) {
        event.target.setPointerCapture(event.pointerId)
      }
    },
    onPointerMove(event: ReactPointerEvent<HTMLDivElement>) {
      if (!points.current.has(event.pointerId)) return
      const previous = [...points.current.values()]
      points.current.set(event.pointerId, point(event))
      const next = [...points.current.values()]
      let from = midpoint(previous)
      const to = midpoint(next)
      if (!dragged.current) {
        from = origin.current!
        if (distance(from, to) < 6) return
        dragged.current = true
        setDragging(true)
      }
      live.current = zoomAt(live.current, viewport.current, world, from, to, separation(next) / separation(previous))
      renderSoon()
    },
    onPointerUp: finishPointer,
    onPointerCancel: finishPointer,
    onLostPointerCapture(event: ReactPointerEvent<HTMLDivElement>) {
      if (event.target === event.currentTarget) finishPointer(event)
    },
    onClickCapture(event: React.MouseEvent<HTMLDivElement>) {
      if (blockClick.current && event.detail > 0) {
        event.stopPropagation()
        blockClick.current = false
      }
    },
  }

  return { size, camera, update, dragging, handlers }
}
