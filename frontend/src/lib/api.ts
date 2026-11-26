export type Locale = 'uk' | 'en'

export type Entry = {
  id: string
  title: string
  estimateMinutes: number
  availability: 'planned' | 'published'
  prerequisites: string[]
}

export type Stage = Entry & { review: Entry; lessons: Entry[] }
export type Region = Entry & { gate: Entry; stages: Stage[] }
export type Point = { x: number; y: number }
export type MapLayout = {
  worldWidth: number
  worldHeight: number
  regions: (Point & { id: string; polygon: [number, number][] })[]
  nodes: (Point & { id: string; kind: 'stage' | 'gate' })[]
  edges: { from: string; to: string; waypoints: [number, number][] }[]
}
export type Roadmap = { id: string; modules: Region[]; layout: MapLayout }
export type Camera = Point & { zoom: number }
export type Viewport = {
  camera: (Camera & { selection: string }) | null
  lastStageId: string | null
  lastActivityId: string | null
}

export type QuizAttempt = { id: string; correct: number; total: number; passed: boolean; createdAt: string }
export type Verdict = 'guided' | 'diagnostic_recorded' | 'self_assessed' | 'failed' | 'test_verified_local'
export type ExerciseAttempt = { id: string; variantId: string; verdict: Verdict; accepted: boolean; createdAt: string }
export type Practice = { accepted: boolean; history: ExerciseAttempt[] }
export type ItemState = {
  id: string
  state: 'available' | 'in_progress' | 'pending_prerequisites' | 'mastered'
  read: boolean
  missing: string[]
  reviewDue: boolean
  quizPassed: boolean
  provisionalEvidence: boolean
  latestQuiz: QuizAttempt | null
  practices: Record<string, Practice>
}
export type Progress = {
  locale: Locale
  revision: number
  xp: number
  level: number
  items: Record<string, ItemState>
}
export type Settings = { locale: Locale; runnerTokenActive: boolean; runnerApi: string; revision: number }

export type Choice = { id: string; title: string }
export type Question = { id: string; prompt: string; multiple: boolean; options: Choice[] }
export type Answers = Record<string, string[]>
export type QuizResult = {
  attempt: QuizAttempt
  feedback: { id: string; correct: boolean; options: { id: string; correct: boolean; explanation: string }[] }[]
}
export type Suite = { id: string; digest: string; contentVersion: number; starter: string; testIds: string[] }
export type Variant = Choice & { prompt: string; hints: string[]; solution: string | null; suite: Suite | null }
export type Exercise = Choice & {
  kind: 'code' | 'rubric'
  diagnostic: boolean
  example: string
  estimateMinutes: number
  criteria: Choice[]
  variants: Variant[]
}
export type Pack = Entry & {
  stageId: string | null
  stage: Entry | null
  module: Entry
  prerequisiteEntries: Entry[]
  contentVersion: number
  overview: string
  theory: string
  recap: string
  objectives: string[]
  exercises: Exercise[]
  questions: Question[]
  interview: string[]
  interviewGuide: string
  sources: { title: string; url: string; checked: string; version: string }[]
  crosslinks: Entry[]
  examples: { file: string; code: string; expected: string; explanation: string; error: string }[]
}

export class ApiError extends Error {
  constructor(public readonly code: string) {
    super(code)
  }
}

export const apiPath = (path: string) => `/api/v1${path}`
export const contentPath = (id: string) => id.startsWith('G-') ? `/gates/${id}` :
  id.startsWith('SR-') ? `/reviews/${id}` : `/lessons/${id}`
export const withLocale = (path: string, locale: Locale) => `${path}?locale=${locale}`

export async function api<T>(path: string, method = 'GET', body?: unknown, keepalive = false): Promise<T> {
  const response = await fetch(apiPath(path), {
    method,
    keepalive,
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!response.ok) {
    const payload: unknown = await response.json().catch(() => null)
    throw new ApiError(
      payload !== null && typeof payload === 'object' && 'code' in payload && typeof payload.code === 'string'
        ? payload.code : 'request_rejected',
    )
  }
  return response.json() as Promise<T>
}
