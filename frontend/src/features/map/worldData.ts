import type { Entry, ItemState, Point, Progress, Region, Roadmap, Stage, Viewport } from '../../lib/api'

export type MapState = ItemState['state'] | 'planned'
export type Destination = Point & {
  entry: Entry
  region: Region
  path: string
  kind: 'region' | 'stage' | 'gate'
  state: MapState
  reviewDue: boolean
  missing: string[]
}

export const regionPath = (id: string) => `/regions/${id}`
export const stagePath = (id: string) => `/stages/${id}`

export function stageState(stage: Stage, progress: Progress): ItemState['state'] {
  const review = progress.items[stage.review.id]?.state
  if (review && review !== 'available') return review
  const states = stage.lessons.map(lesson => progress.items[lesson.id])
  if (states.some(state => state?.provisionalEvidence)) return 'pending_prerequisites'
  return states.some(state => state && state.state !== 'available') ? 'in_progress' : 'available'
}

export function destinations(roadmap: Roadmap, progress: Progress): Destination[] {
  const locations = new Map([...roadmap.layout.regions, ...roadmap.layout.nodes].map(node => [node.id, node]))
  const result: Destination[] = []
  function add(entry: Entry, region: Region, kind: Destination['kind'], path: string, state?: ItemState['state'], reviewDue = false) {
    const point = locations.get(entry.id)
    if (!point) throw new Error(`Missing map location for ${entry.id}`)
    result.push({
      x: point.x, y: point.y, entry, region, kind, path,
      state: entry.availability === 'planned' ? 'planned' : state ?? 'available',
      reviewDue, missing: entry.prerequisites.filter(key => progress.items[key]?.state !== 'mastered'),
    })
  }
  for (const region of roadmap.modules) {
    const gate = progress.items[region.gate.id]
    const states = region.stages.map(stage => stageState(stage, progress))
    const regionState = gate?.state === 'mastered' ? 'mastered' : gate?.state === 'pending_prerequisites'
      ? 'pending_prerequisites' : states.some(state => state !== 'available') || gate?.state === 'in_progress'
        ? 'in_progress' : 'available'
    add(region, region, 'region', regionPath(region.id), regionState)
    for (const stage of region.stages) {
      const reviewDue = [...stage.lessons, stage.review].some(item => progress.items[item.id]?.reviewDue)
      add(stage, region, 'stage', stagePath(stage.id), stageState(stage, progress), reviewDue)
    }
    add(region.gate, region, 'gate', `/gates/${region.gate.id}`,
      gate?.provisionalEvidence ? 'pending_prerequisites' : gate?.state, gate?.reviewDue)
  }
  return result
}

export function currentActivity(modules: Region[], progress: Progress, viewport: Viewport) {
  const published = modules.filter(module => module.availability === 'published').flatMap(module => [
    ...module.stages.flatMap(stage => [...stage.lessons, stage.review].map(entry => ({ entry, module, stage }))),
    { entry: module.gate, module, stage: null },
  ])
  const unfinished = published.filter(({ entry }) => progress.items[entry.id]?.state !== 'mastered')
  return published.find(({ entry }) => entry.id === viewport.lastActivityId)
    ?? unfinished.find(({ stage }) => stage?.id === viewport.lastStageId)
    ?? unfinished[0]
    ?? null
}
