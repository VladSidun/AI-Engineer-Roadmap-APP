import { ArrowRight } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'
import { useLocalized, useProgress } from '../app/queries'
import { contentPath } from '../lib/api'
import type { Entry, Locale, Progress, Region, Roadmap, Stage } from '../lib/api'
import { entryLabel, entryName, entryNumber } from '../lib/entryLabels'
import { labels } from '../lib/messages'
import { ProblemPanel, StateBadge } from '../lib/ui'
import { WorldMap } from './map/WorldMap'
import { useRecordPosition, useViewport } from './map/viewport'
import { regionPath, stagePath, stageState } from './map/worldData'

export const mapPath = '/campaign/main/map'

export function Breadcrumbs({ locale, links = [], current }: {
  locale: Locale; links?: { to: string; title: string }[]; current: string
}) {
  return <nav className="breadcrumbs" aria-label={labels(locale).roadmap}>
    <ol>
      <li><Link to={mapPath}>{labels(locale).roadmap}</Link></li>
      {links.map(link => <li key={link.to}><Link to={link.to}>{link.title}</Link></li>)}
      <li aria-current="page">{current}</li>
    </ol>
  </nav>
}

function EntryRow({ entry, locale, progress, path }: { entry: Entry | Stage; locale: Locale; progress: Progress; path?: string }) {
  const details = <>
    <span className="entry-title min-w-0"><small className="entry-key">{entryNumber(entry.id, locale)}</small>{entryName(entry)}</span>
    <StateBadge entry={entry} state={'lessons' in entry ? stageState(entry, progress) : progress.items[entry.id]?.state} locale={locale} />
    {path && <ArrowRight size={17} aria-hidden="true" />}
  </>
  return <li>{path ? <Link className="entry-row" to={path}>{details}</Link> : <div className="entry-row">{details}</div>}</li>
}

export function MapPage({ locale }: { locale: Locale }) {
  const query = useLocalized<Roadmap>('/campaigns/main/map', locale, true)
  const progress = useProgress()
  const viewport = useViewport()
  const t = labels(locale)
  if (query.isError || progress.isError || viewport.isError) return <ProblemPanel error={query.error ?? progress.error ?? viewport.error} locale={locale}
    retry={() => { void query.refetch(); void progress.refetch(); void viewport.refetch() }} />
  if (!query.data || !progress.data || !viewport.data) return <p role="status">{t.waiting}</p>
  return <WorldMap roadmap={query.data} progress={progress.data} viewport={viewport.data} locale={locale} />
}

export function RegionPage({ locale }: { locale: Locale }) {
  const { id = '' } = useParams()
  const query = useLocalized<Region>(regionPath(id), locale)
  const progress = useProgress()
  const t = labels(locale)
  if (query.isError || progress.isError) return <ProblemPanel error={query.error ?? progress.error} locale={locale}
    retry={() => { void query.refetch(); void progress.refetch() }} />
  if (!query.data || !progress.data) return <p role="status">{t.waiting}</p>
  const region = query.data
  const state = progress.data
  return <>
    <Breadcrumbs locale={locale} current={entryLabel(region, locale)} />
    <header className="page-header">
      <p className="eyebrow">{entryNumber(region.id, locale)}</p>
      <h1>{region.title}</h1>
      <StateBadge entry={region} state={state.items[region.gate.id]?.state} locale={locale} />
      {region.availability === 'planned' && <p>{t.plannedItem}</p>}
    </header>
    <section className="section">
      <h2>{t.stages}</h2>
      <ul className="entry-list">
        {region.stages.map(stage => <EntryRow key={stage.id} entry={stage} locale={locale} progress={state} path={stagePath(stage.id)} />)}
      </ul>
    </section>
    <section className="section">
      <h2>{t.moduleGate}</h2>
      <ul className="entry-list"><EntryRow entry={region.gate} locale={locale} progress={state}
        path={contentPath(region.gate.id)} /></ul>
    </section>
  </>
}

export function StagePage({ locale }: { locale: Locale }) {
  const { id = '' } = useParams()
  const query = useLocalized<Stage & { module: Entry; projectId: string | null }>(stagePath(id), locale)
  const progress = useProgress()
  useRecordPosition(query.data?.id)
  const t = labels(locale)
  if (query.isError || progress.isError) return <ProblemPanel error={query.error ?? progress.error} locale={locale}
    retry={() => { void query.refetch(); void progress.refetch() }} />
  if (!query.data || !progress.data) return <p role="status">{t.waiting}</p>
  const stage = query.data
  const state = progress.data
  const published = stage.availability === 'published'
  return <>
    <Breadcrumbs locale={locale} links={[{ to: regionPath(stage.module.id), title: entryLabel(stage.module, locale) }]} current={entryLabel(stage, locale)} />
    <header className="page-header">
      <p className="eyebrow">{entryNumber(stage.id, locale)}</p>
      <h1>{stage.title}</h1>
      <StateBadge entry={stage} state={stageState(stage, state)} locale={locale} />
      {!published && <p><strong>{t.plannedStage}.</strong> {t.plannedItem}</p>}
    </header>
    <section className="section">
      <h2>{t.lessons}</h2>
      <ul className="entry-list">
        {stage.lessons.map(entry => <EntryRow key={entry.id} entry={entry} locale={locale} progress={state}
          path={published ? contentPath(entry.id) : undefined} />)}
      </ul>
    </section>
    <section className="section">
      <h2>{t.review}</h2>
      <ul className="entry-list"><EntryRow entry={stage.review} locale={locale} progress={state}
        path={published ? contentPath(stage.review.id) : undefined} /></ul>
    </section>
    {stage.projectId && <section className="section">
      <h2>Project {stage.projectId}</h2>
      <Link className="secondary" to={`/projects/${stage.projectId}#${stage.id}`}>{t.projectMilestones}<ArrowRight size={17} aria-hidden="true" /></Link>
    </section>}
  </>
}
