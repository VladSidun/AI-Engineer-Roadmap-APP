import { useQuery, useQueryClient } from '@tanstack/react-query'
import type { QueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'
import { api } from '../../lib/api'
import type { Viewport } from '../../lib/api'

const key = ['viewport', 'main']
const path = '/viewport/main'
const writes = new WeakMap<QueryClient, Promise<Viewport>>()

export function useViewport() {
  const client = useQueryClient()
  const read = () => api<Viewport>(path)
  return useQuery({ queryKey: key, queryFn: () => writes.get(client)?.catch(read) ?? read(), staleTime: 30_000 })
}

// Share the same ordered write queue between map gestures and direct stage links.
export function writeViewport(client: QueryClient, changes: Partial<Viewport>) {
  const send = () => api<Viewport>(path, 'PUT', changes, true)
  const previous = writes.get(client)
  const request = previous ? previous.then(send, send) : send()
  writes.set(client, request)
  client.setQueryData<Viewport>(key, viewport => viewport ? { ...viewport, ...changes } : undefined)
  const finish = (viewport?: Viewport) => {
    if (writes.get(client) !== request) return
    writes.delete(client)
    if (viewport) client.setQueryData(key, viewport)
  }
  void request.then(finish, () => finish())
  return request
}

export function useRecordPosition(stageId: string | null | undefined, activityId?: string) {
  const client = useQueryClient()
  useEffect(() => {
    const saved = client.getQueryData<Viewport>(key)
    const changes: Partial<Viewport> = {}
    if (stageId && saved?.lastStageId !== stageId) changes.lastStageId = stageId
    if (activityId && saved?.lastActivityId !== activityId) changes.lastActivityId = activityId
    if (Object.keys(changes).length) {
      void writeViewport(client, changes).catch(() => { void client.invalidateQueries({ queryKey: key }) })
    }
  }, [client, stageId, activityId])
}
