import { describe, expect, it } from 'vitest'
import { boundCamera, fitCamera, project, worldAt, zoomAt } from './camera'

const screen = { width: 900, height: 600 }
const world = { width: 3200, height: 2240 }

describe('world map camera', () => {
  it('keeps the world coordinate under an off-center cursor when zooming', () => {
    const start = { x: 1400, y: 1000, zoom: .85 }
    const cursor = { x: 390, y: 235 }
    const anchor = worldAt(start, screen, cursor)
    const next = zoomAt(start, screen, world, cursor, cursor, 1.4)
    const pixel = project(next, screen, anchor)
    expect(pixel.x).toBeCloseTo(cursor.x)
    expect(pixel.y).toBeCloseTo(cursor.y)
  })

  it('supports pinch translation and scale around the original midpoint', () => {
    const start = { x: 1500, y: 1100, zoom: 1 }
    const from = { x: 450, y: 300 }
    const to = { x: 480, y: 241 }
    const next = zoomAt(start, screen, world, from, to, 1.3)
    const pixel = project(next, screen, worldAt(start, screen, from))
    expect(next.zoom).toBe(1.3)
    expect(pixel.x).toBeCloseTo(to.x)
    expect(pixel.y).toBeCloseTo(to.y)
  })

  it('fits and bounds both axes independently across desktop and mobile', () => {
    for (const viewport of [screen, { width: 360, height: 400 }]) {
      const fit = fitCamera(viewport, world)
      const corner = project(fit, viewport, { x: 0, y: 0 })
      expect(corner.x).toBeGreaterThanOrEqual(12)
      expect(corner.y).toBeGreaterThanOrEqual(12)
      const clamped = boundCamera({ x: -1, y: 9000, zoom: 15 }, viewport, world)
      expect(clamped).toEqual({ x: viewport.width / 4, y: world.height - viewport.height / 4, zoom: 2 })
      expect(boundCamera(fit, viewport, world)).toEqual(fit)
    }
  })
})
