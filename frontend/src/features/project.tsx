import { ArrowRight, FolderGit2 } from 'lucide-react'
import { useEffect } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'
import { useLocalized } from '../app/queries'
import { contentPath } from '../lib/api'
import type { Entry, ItemState, Locale } from '../lib/api'
import { entryLabel } from '../lib/entryLabels'
import { labels } from '../lib/messages'
import { ProblemPanel, StateBadge } from '../lib/ui'
import { Breadcrumbs } from './roadmap'

type Milestone = {
  id: string; title: string; stageId: string; stage: Entry; evidenceId: string; artifacts: string[]; evidence: ItemState
}
type Project = { id: string; title: string; milestones: Milestone[] }

export function ProjectPage({ locale }: { locale: Locale }) {
  const { id = '' } = useParams()
  const { hash } = useLocation()
  const { data, error, refetch } = useLocalized<Project>(`/projects/${id}`, locale, true)
  const t = labels(locale)
  useEffect(() => {
    if (data && hash) document.getElementById(hash.slice(1))?.scrollIntoView()
  }, [data, hash])
  if (error) return <ProblemPanel error={error} locale={locale} retry={() => { void refetch() }} />
  if (!data) return <p role="status">{t.waiting}</p>
  return <>
    <Breadcrumbs locale={locale} current={`Project ${data.id}`} />
    <header className="page-header">
      <p className="eyebrow"><FolderGit2 size={17} aria-hidden="true" />Project {data.id}</p>
      <h1>{data.title}</h1>
      <p>{t.projectIntro}</p>
    </header>
    <section className="section">
      <h2>{t.projectMilestones}</h2>
      {data.milestones.map(milestone => <article className="panel section" key={milestone.id} id={milestone.stageId}>
        <p className="eyebrow"><Link to={`/stages/${milestone.stageId}`}>{entryLabel(milestone.stage, locale)}</Link></p>
        <h3>{milestone.title}</h3>
        <StateBadge state={milestone.evidence.state} locale={locale} />
        {milestone.evidence.provisionalEvidence && <p>{t.provisional}</p>}
        <ul>{milestone.artifacts.map(artifact => <li key={artifact}>{artifact}</li>)}</ul>
        <Link className="secondary" to={contentPath(milestone.evidenceId)}>{t.projectEvidence}<ArrowRight size={17} aria-hidden="true" /></Link>
      </article>)}
    </section>
  </>
}
