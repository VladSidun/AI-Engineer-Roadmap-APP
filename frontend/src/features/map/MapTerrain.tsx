import type { KeyboardEvent, RefObject } from 'react'
import type { Camera, Locale, MapLayout, Point } from '../../lib/api'
import { entryLabel, entryName, entryNumber } from '../../lib/entryLabels'
import { labels } from '../../lib/messages'
import { project } from './camera'
import type { Size } from './camera'
import type { Destination } from './worldData'

export const terrainAsset = '/assets/atlas-terrain.svg'

function routePath(from: Point, to: Point, waypoints: [number, number][]) {
  const start = `M${from.x} ${from.y}`
  const end = `${to.x} ${to.y}`
  if (!waypoints.length) return `${start} L${end}`
  return `${start} ${waypoints.slice(0, -1).map(point => `L${point.join(' ')}`).join(' ')} Q${waypoints.at(-1)!.join(' ')} ${end}`
}

type Props = {
  layout: MapLayout
  destinations: Destination[]
  camera: Camera
  screen: Size
  selected: Destination
  currentId: string | undefined
  showDependencies: boolean
  locale: Locale
  onSelect: (item: Destination) => void
  onMarkerKey: (event: KeyboardEvent<SVGGElement>, id: string) => void
  markerElements: RefObject<Map<string, SVGGElement>>
}

function splitLabel(title: string, limit: number) {
  const lines: string[] = []
  let line = ''
  for (const word of title.split(' ')) {
    if (line && line.length + word.length + 1 > limit) {
      lines.push(line)
      line = word
    } else line = line ? `${line} ${word}` : word
  }
  if (line) lines.push(line)
  return lines
}

type Box = { x: number; y: number; width: number; height: number }
const overlaps = (a: Box, b: Box) => a.x < b.x + b.width && a.x + a.width > b.x
  && a.y < b.y + b.height && a.y + a.height > b.y

export function MapTerrain({
  layout, destinations, camera, screen, selected, currentId, showDependencies, locale, onSelect, onMarkerKey, markerElements,
}: Props) {
  const t = labels(locale)
  const origin = project(camera, screen, { x: 0, y: 0 })
  const selectedRegion = layout.regions.find(region => region.id === selected.region.id)
  const byId = new Map(destinations.map(destination => [destination.entry.id, destination]))
  const roomForNames = camera.zoom >= .25 || (camera.zoom >= .16 && screen.width >= 620)
  const dense = camera.zoom < .34
  const markers = [...destinations.filter(node => node !== selected), selected].map(item => ({
    item, ...project(camera, screen, item),
    extent: dense ? (item.kind === 'gate' ? 8 : 5) : item.kind === 'gate' ? 17 : 14,
    names: item.kind === 'region' && (roomForNames || item === selected) ? splitLabel(item.entry.title, dense ? 16 : 26) : [],
  }))
  const occupied: Box[] = markers.map(({ item, x, y, extent, names }) => {
    if (item.kind !== 'region') return { x: x - extent - 4, y: y - extent - 4, width: 2 * extent + 8, height: 2 * extent + 8 }
    const width = Math.max(55, ...names.map(line => line.length * (dense ? 6.6 : 8.5)))
    return { x: x - width / 2, y: y - 17, width, height: 34 + names.length * (dense ? 10.5 : 14) }
  })
  occupied.push({ x: 6, y: 7, width: 60, height: 258 },
    { x: screen.width - 166, y: screen.height - 125, width: 166, height: 125 })
  const captions = new Map<string, { box: Box; lines: string[] }>()
  const ordered = [...markers].sort((a, b) => Number(b.item === selected) - Number(a.item === selected)
    || Number(b.item.entry.id === currentId) - Number(a.item.entry.id === currentId))
  for (const { item, x, y, extent } of ordered) {
    if (item.kind === 'region' || camera.zoom < (item === selected || item.entry.id === currentId ? .43 : .59)) continue
    const lines = [entryNumber(item.entry.id, locale), ...splitLabel(entryName(item.entry), 23)]
    const width = Math.max(...lines.map(line => line.length)) * 7.25 + 14
    const height = lines.length * 14 + 8
    const box = [0, -width / 3, width / 3].map(offset => ({
      x: Math.max(4, Math.min(screen.width - width - 4, x - width / 2 + offset)),
      y: y + extent + 9, width, height,
    })).find(candidate => x >= candidate.x - 12 && x <= candidate.x + width + 12
      && y > 0 && candidate.y + height < screen.height - 4 && !occupied.some(obstacle => overlaps(candidate, obstacle)))
    if (box) {
      occupied.push(box)
      captions.set(item.entry.id, { box, lines })
    }
  }
  return <svg className="atlas-svg" viewBox={`0 0 ${screen.width} ${screen.height}`} aria-label={t.campaign}>
    <defs>
      <filter id="marker-halo" x="-100%" width="300%" y="-100%" height="300%">
        <feGaussianBlur stdDeviation="5" />
      </filter>
    </defs>
    <g transform={`translate(${origin.x} ${origin.y}) scale(${camera.zoom})`}>
      <image href={terrainAsset} width={layout.worldWidth} height={layout.worldHeight} />
      {selectedRegion && <polygon className="atlas-territory" points={selectedRegion.polygon.map(point => point.join(',')).join(' ')} />}
      {layout.edges.map(edge => {
        const from = byId.get(edge.from)!
        const to = byId.get(edge.to)!
        const complete = from.state === 'mastered'
        const live = from.state !== 'planned' && to.state !== 'planned'
        const path = routePath(from, to, edge.waypoints)
        return <g key={edge.to} aria-hidden="true">
          <path className="atlas-route-bed" d={path} />
          <path className={`atlas-route ${complete ? 'atlas-route-earned' : live ? 'atlas-route-open' : ''}`} d={path} />
        </g>
      })}
      {showDependencies && selected.missing.map(key => {
        const from = byId.get(key.startsWith('SR-') ? key.slice(3) : key)
        return from && <path key={key} aria-hidden="true" className="atlas-route atlas-route-required"
          d={routePath(from, selected, [])} />
      })}
    </g>
    {markers.map(({ item, x, y, extent, names }) => {
      const id = item.entry.id
      const active = selected === item
      const current = currentId === id
      const region = item.kind === 'region'
      const gate = item.kind === 'gate'
      const hidden = x < 4 || x > screen.width - 4 || y < 4 || y > screen.height - 4
      const caption = captions.get(id)
      const name = entryLabel(item.entry, locale)
      return <g key={id} className={`atlas-marker atlas-${item.kind} atlas-state-${item.state}${active ? ' atlas-chosen' : ''}${current ? ' atlas-current' : ''}`}
        transform={`translate(${x} ${y})`} data-atlas-marker={id} data-state={item.state}
        role="button" aria-label={`${name} · ${t[item.state]}${item.reviewDue ? ` · ${t.attention}` : ''}`}
        aria-pressed={active} aria-current={current ? 'step' : undefined}
        tabIndex={active && !hidden ? 0 : -1}
        ref={element => { if (element) markerElements.current.set(id, element); else markerElements.current.delete(id) }}
        onKeyDown={event => onMarkerKey(event, id)} onClick={() => onSelect(item)}>
        <title>{name}</title>
        {region ? <>
          <rect className="atlas-hit" x={dense ? -51 : -92} y="-18" width={dense ? 102 : 184} height={names.length ? 34 + names.length * 14 : 30} />
          <text className="atlas-region-id" y="-4">{entryNumber(id, locale)}</text>
          {names.map((line, index) => <text key={index} className={`atlas-region-title${dense ? ' atlas-small-title' : ''}`} y={12 + index * (dense ? 10.5 : 14)}>{line}</text>)}
        </> : <>
          <circle className="atlas-hit" r={dense ? 12 : 22} />
          {(active || current) && <circle className="atlas-halo" r={extent + 8} filter="url(#marker-halo)" />}
          {gate
            ? <path className="atlas-node-shape" d={`M0 ${-extent} ${extent} 0 0 ${extent} ${-extent} 0Z`} />
            : <circle className="atlas-node-shape" r={extent} />}
          {item.state === 'mastered'
            ? <path className="atlas-glyph" d={dense ? 'm-2 0 1.5 1.5 3-3' : 'm-5 0 3 3 7-7'} />
            : gate ? <path className="atlas-glyph" d={dense ? 'M0 -3v6m-2 -2h4' : 'M0 -7V7m-5-5h10'} />
              : <circle className="atlas-glyph-dot" r={dense ? 1.5 : 3.1} />}
          {item.reviewDue && <circle className="atlas-review-dot" cx={extent * .7} cy={-extent * .72} r={dense ? 2.5 : 4.5} />}
          {current && <circle className="atlas-current-ring" r={extent + (dense ? 4 : 6)} />}
          {caption && <g className="atlas-node-caption" aria-hidden="true"
            transform={`translate(${caption.box.x - x} ${caption.box.y - y})`}>
            <rect width={caption.box.width} height={caption.box.height} rx={5} />
            {caption.lines.map((line, index) => <text key={index} x={caption.box.width / 2} y={14 + index * 14}
              className={index === 0 ? 'atlas-node-number' : undefined}>{line}</text>)}
          </g>}
        </>}
      </g>
    })}
  </svg>
}

export function Minimap({ layout, camera, screen, current, name, onJump }: {
  layout: MapLayout; camera: Camera; screen: Size; current: Destination; name: string; onJump: (point: Point) => void
}) {
  const { worldWidth: width, worldHeight: height } = layout
  const rectWidth = Math.min(width, screen.width / camera.zoom)
  const rectHeight = Math.min(height, screen.height / camera.zoom)
  return <button type="button" className="atlas-minimap" aria-label={name} title={name}
    onClick={event => {
      const bounds = event.currentTarget.getBoundingClientRect()
      onJump(event.detail === 0 ? current : {
        x: (event.clientX - bounds.left) * width / bounds.width,
        y: (event.clientY - bounds.top) * height / bounds.height,
      })
    }}>
    <svg viewBox={`0 0 ${width} ${height}`} aria-hidden="true" preserveAspectRatio="none">
      <image href={terrainAsset} width={width} height={height} />
      <circle className="atlas-mini-current" cx={current.x} cy={current.y} r="45" />
      <rect className="atlas-mini-window" x={camera.x - rectWidth / 2} y={camera.y - rectHeight / 2} width={rectWidth} height={rectHeight} />
    </svg>
  </button>
}
