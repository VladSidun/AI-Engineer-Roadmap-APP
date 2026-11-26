import type { Camera, Point } from '../../lib/api'

export type Size = { width: number; height: number }
const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value))

export function fitZoom(screen: Size, world: Size) {
  return clamp(Math.min((screen.width - 24) / world.width, (screen.height - 24) / world.height), .05, 2)
}

export function fitCamera(screen: Size, world: Size): Camera {
  return { x: world.width / 2, y: world.height / 2, zoom: fitZoom(screen, world) }
}

export function boundCamera(camera: Camera, screen: Size, world: Size): Camera {
  const zoom = clamp(camera.zoom, Math.min(.45, fitZoom(screen, world)), 2)
  const axis = (position: number, viewport: number, total: number) => {
    const half = Math.min(total / 2, viewport / (2 * zoom))
    return clamp(position, half, total - half)
  }
  return { x: axis(camera.x, screen.width, world.width), y: axis(camera.y, screen.height, world.height), zoom }
}

export function worldAt(camera: Camera, screen: Size, point: Point): Point {
  return {
    x: camera.x + (point.x - screen.width / 2) / camera.zoom,
    y: camera.y + (point.y - screen.height / 2) / camera.zoom,
  }
}

export function zoomAt(camera: Camera, screen: Size, world: Size, from: Point, to: Point, factor: number): Camera {
  const anchor = worldAt(camera, screen, from)
  const { zoom } = boundCamera({ ...camera, zoom: camera.zoom * factor }, screen, world)
  return boundCamera({
    x: anchor.x - (to.x - screen.width / 2) / zoom,
    y: anchor.y - (to.y - screen.height / 2) / zoom,
    zoom,
  }, screen, world)
}

export function project(camera: Camera, screen: Size, point: Point): Point {
  return {
    x: (point.x - camera.x) * camera.zoom + screen.width / 2,
    y: (point.y - camera.y) * camera.zoom + screen.height / 2,
  }
}
