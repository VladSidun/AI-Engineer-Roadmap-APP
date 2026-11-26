import { useQueryClient } from '@tanstack/react-query'
import { ArrowRight, Compass, Crosshair, Flag, List, Map as MapIcon, Maximize, Minus, Network, Plus, Search } from 'lucide-react'
import { useMemo, useRef, useState } from 'react'
import type { KeyboardEvent } from 'react'
import { Link } from 'react-router-dom'
import { contentPath } from '../../lib/api'
import type { Camera, Locale, Progress, Roadmap, Viewport } from '../../lib/api'
import { entryLabel, entryName, entryNumber } from '../../lib/entryLabels'
import { labels } from '../../lib/messages'
import { StateBadge } from '../../lib/ui'
import { fitCamera, fitZoom } from './camera'
import { mapLabels } from './mapMessages'
import { MapTerrain, Minimap } from './MapTerrain'
import { useCamera } from './useCamera'
import { writeViewport } from './viewport'
import { currentActivity, destinations } from './worldData'
import type { Destination, MapState } from './worldData'
import './worldMap.css'

const legend: MapState[] = ['available', 'in_progress', 'pending_prerequisites', 'mastered', 'planned']

function IconButton({ name, disabled, pressed, onClick, children }: {
  name: string; disabled?: boolean; pressed?: boolean; onClick: () => void; children: React.ReactNode
}) {
  return <button type="button" className="atlas-tool" title={name} aria-label={name} disabled={disabled}
    aria-pressed={pressed} onClick={onClick}>{children}</button>
}

export function WorldMap({ roadmap, progress, viewport, locale }: {
  roadmap: Roadmap; progress: Progress; viewport: Viewport; locale: Locale
}) {
  const t = labels(locale)
  const m = mapLabels(locale)
  const client = useQueryClient()
  const entries = useMemo(() => destinations(roadmap, progress), [roadmap, progress])
  const start = entries.find(node => node.entry.id === 'W01')!
  const activity = useMemo(() => currentActivity(roadmap.modules, progress, viewport),
    [roadmap.modules, progress, viewport])
  const current = entries.find(node => node.entry.id === (activity?.stage?.id ?? activity?.entry.id)) ?? start
  const initialSelection = viewport.camera?.selection ?? current.entry.id
  const [selectedId, setSelectedId] = useState(initialSelection)
  const selected = entries.find(node => node.entry.id === selectedId) ?? current
  const selection = useRef(initialSelection)
  const [saveError, setSaveError] = useState(false)
  const [showDependencies, setShowDependencies] = useState(false)
  const [showList, setShowList] = useState(false)
  const markerElements = useRef(new Map<string, SVGGElement>())
  const layout = roadmap.layout
  const world = useMemo(() => ({ width: layout.worldWidth, height: layout.worldHeight }), [layout.worldWidth, layout.worldHeight])
  const opening = viewport.camera ?? { x: current.x + 155, y: current.y - 120, zoom: .76 }
  const surface = useRef<HTMLDivElement>(null)
  const { size, camera, update, dragging, handlers } = useCamera(surface, opening, world, save)
  const detailLocales = locale === 'uk' ? 'uk-UA' : 'en-US'
  const mastered = roadmap.modules.flatMap(region => region.stages)
    .flatMap(stage => stage.lessons).filter(entry => progress.items[entry.id]?.state === 'mastered').length
  const published = roadmap.modules.flatMap(region => region.stages)
    .flatMap(stage => stage.lessons).filter(entry => entry.availability === 'published').length
  const titles = useMemo(() => new Map(roadmap.modules.flatMap(module => [module, module.gate,
    ...module.stages.flatMap(stage => [stage, stage.review, ...stage.lessons])]).map(entry => [entry.id, entry])), [roadmap.modules])
  const zoom = (factor: number) => update(previous => ({ ...previous, zoom: previous.zoom * factor }))
  const prerequisitePath = (id: string) => {
    const stage = id.startsWith('SR-') && entries.find(entry => entry.entry.id === id.slice(3))
    return stage && stage.state === 'planned' ? stage.path : contentPath(id)
  }

  function save(nextCamera: Camera) {
    void writeViewport(client, { camera: { ...nextCamera, selection: selection.current } })
      .then(() => setSaveError(false), () => setSaveError(true))
  }

  function select(item: Destination, center = false) {
    selection.current = item.entry.id
    setSelectedId(item.entry.id)
    if (center) {
      update(previous => ({ x: item.x, y: item.y, zoom: Math.max(previous.zoom, .9) }))
    } else {
      update(previous => previous, 'instant')
    }
  }

  function handleKey(event: KeyboardEvent<HTMLDivElement>) {
    if (event.target !== event.currentTarget || event.ctrlKey || event.metaKey || event.altKey) return
    const moves: Record<string, readonly [number, number]> = {
      ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1],
    }
    const direction = moves[event.key]
    if (direction) update(previous => {
      const offset = (event.shiftKey ? 178 : 80) / previous.zoom
      return { ...previous, x: previous.x + direction[0] * offset, y: previous.y + direction[1] * offset }
    })
    else if (event.key === '+' || event.key === '=') zoom(1.25)
    else if (event.key === '-') zoom(.8)
    else if (event.key === '0') update(fitCamera(size, world))
    else if (event.key === 'Home') select(current, true)
    else if (event.key === 'Enter') {
      select(selected, true)
      markerElements.current.get(selected.entry.id)?.focus({ preventScroll: true })
    } else return
    event.preventDefault()
  }

  function handleMarkerKey(event: KeyboardEvent<SVGGElement>, id: string) {
    const index = entries.findIndex(entry => entry.entry.id === id)
    const direction = event.key === 'ArrowLeft' || event.key === 'ArrowUp' ? -1 :
      event.key === 'ArrowRight' || event.key === 'ArrowDown' ? 1 : 0
    if (direction) {
      event.preventDefault()
      const target = entries[(index + direction + entries.length) % entries.length]!
      select(target, true)
      markerElements.current.get(target.entry.id)?.focus({ preventScroll: true })
    } else if (event.key === ' ' || event.key === 'Enter') {
      event.preventDefault()
      select(entries[index]!)
    }
  }

  return <div className="world-page">
    <header className="atlas-header">
      <div className="atlas-title">
        <p className="eyebrow"><Compass size={15} aria-hidden="true" />{t.campaign}</p>
        <h1>{m.title}</h1>
      </div>
      <dl className="atlas-stats" aria-label={m.progress}>
        <div><dt>{m.regionList}</dt><dd>{roadmap.modules.length}</dd></div>
        <div><dt>{t.stages}</dt><dd>{layout.nodes.filter(node => node.kind === 'stage').length}</dd></div>
        <div><dt>{t.masteredLessons}</dt><dd>{mastered}<span> / {published}</span></dd></div>
      </dl>
    </header>
    <div className="atlas-modes" role="group" aria-label={m.controls}>
      <button type="button" aria-pressed={!showList} onClick={() => setShowList(false)}><MapIcon size={17} aria-hidden="true" />{m.map}</button>
      <button type="button" aria-pressed={showList} onClick={() => setShowList(true)}><List size={17} aria-hidden="true" />{m.list}</button>
    </div>
    <div className={`atlas-grid${showList ? ' atlas-list-mode' : ''}`}>
      <aside className="atlas-inspector atlas-resume" aria-labelledby="atlas-resume-title">
        <h2 id="atlas-resume-title">{m.currentStep}</h2>
        {activity ? <>
          <div className="atlas-resume-context">
            <Link to={`/regions/${activity.module.id}`}>{entryLabel(activity.module, locale)}</Link>
            {activity.stage && <Link to={`/stages/${activity.stage.id}`}>{entryLabel(activity.stage, locale)}</Link>}
          </div>
          <div className="atlas-resume-step">
            <p className="eyebrow">{entryNumber(activity.entry.id, locale)}</p>
            {entryName(activity.entry) && <h3>{entryName(activity.entry)}</h3>}
          </div>
          <Link className="atlas-open" to={contentPath(activity.entry.id)}>{t.resume}<ArrowRight size={17} aria-hidden="true" /></Link>
        </> : <p>{m.allPublished}</p>}
      </aside>
      <div className="atlas-frame" hidden={showList}>
        <div className={`atlas-surface${dragging ? ' atlas-dragging' : ''}`} tabIndex={0}
          ref={surface} role="region" aria-label={m.map} aria-describedby="atlas-key-help atlas-touch-help"
          onKeyDown={handleKey} onClick={event => {
            if (selected !== current && event.target instanceof Element && !event.target.closest('[data-atlas-marker]')) {
              select(current, true)
            }
          }} data-camera-x={camera.x.toFixed(3)} data-camera-y={camera.y.toFixed(3)}
          data-camera-zoom={camera.zoom.toFixed(5)} {...handlers}>
          <MapTerrain layout={layout} destinations={entries} camera={camera} screen={size} selected={selected}
            currentId={activity ? current.entry.id : undefined} showDependencies={showDependencies} locale={locale}
            onSelect={select} onMarkerKey={handleMarkerKey} markerElements={markerElements} />
        </div>
        <div className="atlas-tools" role="group" aria-label={m.controls}>
          <IconButton name={m.zoomIn} disabled={camera.zoom >= 2} onClick={() => zoom(1.25)}><Plus size={19} aria-hidden="true" /></IconButton>
          <IconButton name={m.zoomOut} disabled={camera.zoom <= Math.min(.45, fitZoom(size, world))} onClick={() => zoom(.8)}><Minus size={19} aria-hidden="true" /></IconButton>
          <IconButton name={m.fit} onClick={() => update(fitCamera(size, world))}><Maximize size={17} aria-hidden="true" /></IconButton>
          <IconButton name={m.center} onClick={() => select(current, true)}><Crosshair size={18} aria-hidden="true" /></IconButton>
          <IconButton name={m.dependencies} pressed={showDependencies} onClick={() => setShowDependencies(!showDependencies)}><Network size={18} aria-hidden="true" /></IconButton>
        </div>
        <Minimap layout={layout} camera={camera} screen={size} current={current} name={m.minimap}
          onJump={point => update(previous => ({ ...point, zoom: Math.max(previous.zoom, .8) }))} />
        <div className="atlas-scale" aria-hidden="true"><span />{new Intl.NumberFormat(detailLocales, { style: 'percent' }).format(camera.zoom)}</div>
      </div>
      <aside className="atlas-inspector" aria-label={m.selected} hidden={showList}>
        <div className="atlas-selected" aria-live="polite">
          <p className="eyebrow"><Flag size={15} aria-hidden="true" />{entryNumber(selected.entry.id, locale)}</p>
          {selected.kind !== 'region' && <Link className="atlas-region-link" to={`/regions/${selected.region.id}`}>{entryLabel(selected.region, locale)}</Link>}
          <h2>{entryName(selected.entry)}</h2>
          <div className="atlas-status">
            <StateBadge entry={selected.entry} state={selected.state === 'planned' ? undefined : selected.state} locale={locale} />
            {selected.reviewDue && <span>{t.attention}</span>}
          </div>
          <p className="atlas-estimate">{new Intl.NumberFormat(detailLocales, { maximumFractionDigits: 1 }).format(selected.entry.estimateMinutes / 60)} {m.hours}</p>
          <Link className="atlas-open" to={selected.path}>
            {selected.state === 'planned' ? m.planned : selected.kind === 'stage' ? m.openStage :
              selected.kind === 'gate' ? m.openGate : m.openRegion}<ArrowRight size={17} aria-hidden="true" />
          </Link>
        </div>
        {showDependencies && <div className="atlas-requirements">
          <h3>{m.needs}</h3>
          {selected.missing.length ? <ul>{selected.missing.map(id => <li key={id}><Link to={prerequisitePath(id)}>{entryLabel(titles.get(id)!, locale)}</Link></li>)}</ul>
            : <p>{m.requirements}</p>}
          {selected.state !== 'planned' && <p>{m.access}</p>}
        </div>}
      </aside>
      {showList && <RegionList entries={entries} locale={locale} />}
    </div>
    {!showList && <div className="atlas-caption">
      <ul className="atlas-legend">{legend.map(state => <li key={state}><i className={`atlas-state-${state}`} aria-hidden="true" />{t[state]}</li>)}</ul>
      <p id="atlas-key-help">{m.keyHelp}</p><p id="atlas-touch-help">{m.touchHelp}</p>
    </div>}
    {saveError && <p className="atlas-save-error" role="status">{m.saveError} <button type="button" onClick={() => save(camera)}>{t.tryAgain}</button></p>}
  </div>
}

function RegionList({ entries, locale }: { entries: Destination[]; locale: Locale }) {
  const [filter, setFilter] = useState('')
  const m = mapLabels(locale)
  const regions = entries.filter(entry => entry.kind === 'region')
  const needle = filter.trim().toLocaleLowerCase(locale)
  const matches = (item: Destination) => `${item.entry.id} ${entryLabel(item.entry, locale)}`.toLocaleLowerCase(locale).includes(needle)
  const groups = regions.map(region => ({
    region, items: entries.filter(item => item.kind !== 'region' && item.region === region.region && (matches(region) || matches(item))),
  })).filter(group => matches(group.region) || group.items.length > 0)
  return <section className="atlas-list" aria-label={m.regionList}>
    <label className="atlas-search"><span>{m.search}</span><span><Search size={18} aria-hidden="true" />
      <input type="search" value={filter} placeholder={m.searchHelp} onChange={event => setFilter(event.target.value)} />
    </span></label>
    {!groups.length && <p role="status">{m.noMatches}</p>}
    <div className="atlas-list-groups">
      {groups.map(({ region, items }) => <section key={region.entry.id} className="atlas-list-group">
        <h2><Link to={region.path}><span><small>{entryNumber(region.entry.id, locale)}</small>{entryName(region.entry)}</span><ArrowRight size={17} aria-hidden="true" /></Link></h2>
        <ul>{items.map(item => <li key={item.entry.id}>
          <Link to={item.path}>
            <span><small>{entryNumber(item.entry.id, locale)}</small>{entryName(item.entry)}</span>
            <StateBadge entry={item.entry} state={item.state === 'planned' ? undefined : item.state} locale={locale} />
          </Link>
        </li>)}</ul>
      </section>)}
    </div>
  </section>
}
