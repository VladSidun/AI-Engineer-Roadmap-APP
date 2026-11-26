import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Clock3 } from 'lucide-react'
import { useState } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'
import { useLocalized, useProgress } from '../app/queries'
import { api, apiPath, contentPath } from '../lib/api'
import type { Entry, Locale, Pack, Stage } from '../lib/api'
import { entryLabel, entryNumber } from '../lib/entryLabels'
import { labels } from '../lib/messages'
import { Code, ProblemPanel, SafeMarkdown, StateBadge } from '../lib/ui'
import { PracticeCard } from './practice'
import { Quiz } from './quiz'
import { Breadcrumbs } from './roadmap'
import { useRecordPosition } from './map/viewport'

type PlannedGate = Entry & { module: Entry; stages: Stage[] }

export function LearningPage({ kind, locale }: { kind: 'lesson' | 'review' | 'gate'; locale: Locale }) {
  const { id = '' } = useParams()
  const path = contentPath(id)
  const query = useLocalized<Pack | PlannedGate>(path, locale, true)
  const published = query.data && 'stageId' in query.data ? query.data : undefined
  useRecordPosition(published?.stageId, published?.id)
  const [poll, setPoll] = useState(false)
  const progress = useProgress(poll)
  const location = useLocation()
  const client = useQueryClient()
  const t = labels(locale)
  const mark = useMutation({
    mutationFn: () => api(`${path}/read`, 'POST'),
    onSuccess: () => client.invalidateQueries({ queryKey: ['progress'] }),
  })
  if (location.pathname !== path) return <h1>{t.missingPage}</h1>
  if (query.isError || (!progress.data && progress.isError)) return <ProblemPanel error={query.error ?? progress.error}
    locale={locale} retry={() => { void query.refetch(); void progress.refetch() }} />
  if (!query.data || !progress.data) return <p role="status">{t.waiting}</p>
  const pack = query.data
  const moduleLink = { to: `/regions/${pack.module.id}`, title: entryLabel(pack.module, locale) }
  if ('stages' in pack) return <>
    <Breadcrumbs locale={locale} links={[moduleLink]} current={entryLabel(pack, locale)} />
    <header className="page-header">
      <p className="eyebrow">{entryNumber(pack.id, locale)}</p>
      <h1>{pack.title}</h1>
      <StateBadge entry={pack} locale={locale} />
      <p>{t.plannedItem}</p>
    </header>
    <section className="section">
      <h2>{t.stages}</h2>
      <ul>{pack.stages.map(stage => <li key={stage.id}><Link to={`/stages/${stage.id}`}>{entryLabel(stage, locale)}</Link></li>)}</ul>
    </section>
  </>
  const item = progress.data.items[id]
  if (!item) return <h1>{t.missingPage}</h1>
  const breadcrumbs = pack.stage ? [moduleLink, { to: `/stages/${pack.stage.id}`, title: entryLabel(pack.stage, locale) }] : [moduleLink]
  const sections = [
    { id: 'overview', label: t.overview }, { id: 'theory', label: t.theory },
    ...(pack.examples.length ? [{ id: 'examples', label: t.examples }] : []),
    { id: 'practice', label: t.exercise }, { id: 'quiz', label: t.quiz }, { id: 'recap', label: t.recap },
  ]
  const outstanding = [
    ...(kind === 'lesson' && !item.read ? [t.requiredRead] : []),
    ...(!item.quizPassed ? [t.requiredQuiz] : []),
    ...(pack.exercises.some(exercise => !item.practices[exercise.id]?.accepted) ? [t.requiredPractice] : []),
  ]
  return <>
    <Breadcrumbs locale={locale} links={breadcrumbs} current={entryLabel(pack, locale)} />
    <header className="page-header lesson-header">
      <p className="eyebrow">{entryNumber(pack.id, locale)}</p>
      <h1>{pack.title}</h1>
      <div className="actions"><StateBadge state={item.state} locale={locale} />
        <span className="duration"><Clock3 size={17} aria-hidden="true" /> {pack.estimateMinutes} {t.estimated}</span>
        {item.reviewDue && <span className="badge badge-in_progress">{t.attention}</span>}
      </div>
    </header>
    <div className="lesson-grid">
      <aside>
        <nav className="panel toc" aria-label={t.contents}><h2>{t.contents}</h2>
          <ul>{sections.map(section => <li key={section.id}><a href={`#${section.id}`}>{section.label}</a></li>)}</ul>
        </nav>
      </aside>
      <div className="lesson-body" aria-busy={query.isPlaceholderData}>
        <section className="panel requirements">
          <h2>{outstanding.length || item.missing.length ? t.awaiting : t.allEvidence}</h2>
          {outstanding.length > 0 && <ul>{outstanding.map(requirement => <li key={requirement}>{requirement}</li>)}</ul>}
          {item.missing.length > 0 && <><p>{t.needs}</p><ul>{pack.prerequisiteEntries.filter(entry => item.missing.includes(entry.id)).map(entry =>
            <li key={entry.id}><Link className="prereq-link" to={contentPath(entry.id)}>{entryLabel(entry, locale)}</Link></li>)}</ul></>}
          {item.provisionalEvidence && <p role="status">{t.provisional}</p>}
        </section>
        <section id="overview" className="section prose">
          <h2>{t.overview}</h2><SafeMarkdown text={pack.overview} />
          <h3>{t.objectives}</h3><ul>{pack.objectives.map(objective => <li key={objective}>{objective}</li>)}</ul>
          {kind === 'lesson' && <div className="actions">
            {item.read ? <span className="badge badge-mastered" role="status">{t.readDone}</span>
              : <button className="primary" disabled={mark.isPending} onClick={() => mark.mutate()}>{t.read}</button>}
            {mark.error && <ProblemPanel error={mark.error} locale={locale} />}
          </div>}
        </section>
        <section id="theory" className="section prose">
          <details><summary><h2>{t.theory}</h2></summary><SafeMarkdown text={pack.theory} /></details>
        </section>
        {pack.examples.length > 0 && <section id="examples" className="section prose">
          <h2>{t.examples}</h2>
          {pack.examples.map(example => <article key={example.file}>
            <h3><code>{example.file}</code></h3><SafeMarkdown text={example.explanation} />
            <p><a href={apiPath(`/examples/${pack.id}/${example.file}`)}>{t.download} · {example.file}</a></p>
            <Code content={`python ${example.file}`} locale={locale} />
            <Code content={example.code} locale={locale} python />
            <h4>{t.expected}</h4><pre>{example.expected}</pre>
            <h4>{t.errorCase}</h4><SafeMarkdown text={example.error} />
          </article>)}
        </section>}
        <section id="practice" className="section">
          <h2>{t.exercise}</h2>
          {pack.exercises.map(exercise => <PracticeCard key={exercise.id} exercise={exercise} locale={locale}
            practice={item.practices[exercise.id] ?? { accepted: false, history: [] }} onChallenge={() => setPoll(true)} />)}
          {progress.isError && <ProblemPanel error={progress.error} locale={locale} retry={() => { void progress.refetch() }} />}
        </section>
        <Quiz id={pack.id} questions={pack.questions} locale={locale} latest={item.latestQuiz?.id} />
        <section id="recap" className="section prose">
          <h2>{t.recap}</h2><SafeMarkdown text={pack.recap} />
          <h3>{t.interview}</h3>
          <ul lang="en">{pack.interview.map(prompt => <li key={prompt}>{prompt}</li>)}</ul>
          <SafeMarkdown text={pack.interviewGuide} />
          <h3>{t.sources}</h3>
          <ul>{pack.sources.map(source => <li key={source.url}><a href={source.url}>{source.title}</a> · {source.version} · {source.checked}</li>)}</ul>
          <h3>{t.related}</h3>
          <ul>{pack.crosslinks.map(entry => <li key={entry.id}>
            {entry.availability === 'published' ? <Link to={contentPath(entry.id)}>{entryLabel(entry, locale)}</Link> : `${entryLabel(entry, locale)} · ${t.planned}`}
          </li>)}</ul>
        </section>
      </div>
    </div>
  </>
}
