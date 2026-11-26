import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Terminal } from 'lucide-react'
import { useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { useSettings } from '../app/queries'
import { api, apiPath, withLocale } from '../lib/api'
import type { Exercise, Locale, Practice, Variant } from '../lib/api'
import { labels } from '../lib/messages'
import { Code, ProblemPanel, SafeMarkdown } from '../lib/ui'

type Challenge = { challengeId: string; expiresAt: string }

function RunnerTask({ exercise, variant, locale, history, onChallenge }: {
  exercise: Exercise; variant: Variant; locale: Locale; history: Practice['history']; onChallenge: () => void
}) {
  const t = labels(locale)
  const client = useQueryClient()
  const settings = useSettings()
  const [prior, setPrior] = useState<string | undefined>()
  const create = useMutation({
    mutationFn: () => api<Challenge>(`/exercises/${exercise.id}/challenges`, 'POST', { variantId: variant.id }),
    onSuccess: () => { setPrior(history.find(attempt => attempt.variantId === variant.id)?.id); onChallenge() },
  })
  const current = history.find(attempt => attempt.variantId === variant.id)
  const pending = create.isSuccess && prior === current?.id
  const runnerApi = settings.data?.runnerApi ?? window.location.origin
  const command = `quest-runner test --exercise ${exercise.id} --variant ${variant.id} --workspace "./my-labs" --api ${runnerApi}`
  return <div className="task-body">
    <p>{t.runHelp} <Link to="/settings">{t.runnerSetup}</Link></p>
    <p className="muted">{t.safeLocal}</p>
    <div className="actions">
      <a className="secondary" href={apiPath(`/exercises/${exercise.id}/starter/${variant.id}`)}>{t.starter} · {variant.suite?.starter}</a>
      <button className="secondary" type="button" disabled={create.isPending} onClick={() => create.mutate()}>{t.challenge}</button>
    </div>
    {create.error && <ProblemPanel error={create.error} locale={locale} />}
    <p className="muted">{t.local} · <code>{variant.suite?.id}</code> · v{variant.suite?.contentVersion}</p>
    <Code key={create.data?.challengeId ?? variant.id} content={command + (create.data ? ` --challenge ${create.data.challengeId}` : '')} locale={locale} />
    {pending && <div className="notice" role="status">
      <p>{t.awaitingRunner} <time dateTime={create.data.expiresAt}>{new Date(create.data.expiresAt).toLocaleString(locale)}</time></p>
      <p>{t.retryRunner}</p>
      <Code content={`quest-runner submit --report "./.quest-reports/<report-id>.json" --api ${runnerApi}`} locale={locale} />
    </div>}
    <button className="secondary" onClick={() => { void client.invalidateQueries({ queryKey: ['progress'] }) }}>{t.refresh}</button>
  </div>
}

function RubricTask({ exercise, variant, locale }: { exercise: Exercise; variant: Variant; locale: Locale }) {
  const t = labels(locale)
  const client = useQueryClient()
  const [criteria, setCriteria] = useState<string[]>([])
  const [note, setNote] = useState('')
  const previous = useRef<{ fingerprint: string; id: string }>(undefined)
  const submit = useMutation({
    mutationFn: (submissionId: string) => api(`/exercises/${exercise.id}/manual-evidence`, 'POST',
      { variantId: variant.id, criteria, note, submissionId }),
    onSuccess: () => client.invalidateQueries({ queryKey: ['progress'] }),
  })
  return <form className="task-body" onSubmit={event => {
    event.preventDefault()
    const fingerprint = JSON.stringify([[...criteria].sort(), note.trim()])
    if (previous.current?.fingerprint !== fingerprint) previous.current = { fingerprint, id: crypto.randomUUID() }
    submit.mutate(previous.current.id)
  }}>
    <fieldset>
      <legend>{t.rubric}</legend>
      {exercise.criteria.map(criterion => <label key={criterion.id} className="choice">
        <input type="checkbox" checked={criteria.includes(criterion.id)}
          onChange={event => setCriteria(old => event.target.checked ? [...old, criterion.id] : old.filter(x => x !== criterion.id))} />
        {criterion.title}
      </label>)}
    </fieldset>
    <label className="note-label">{t.note}
      <textarea required minLength={20} maxLength={3000} value={note} onChange={event => setNote(event.target.value)} rows={4} />
    </label>
    <button className="primary" disabled={submit.isPending || note.trim().length < 20 || criteria.length === 0}>{t.submitEvidence}</button>
    {submit.error && <ProblemPanel error={submit.error} locale={locale} />}
    {submit.isSuccess && <p role="status">{t.attempts} ↓</p>}
  </form>
}

export function PracticeCard({ exercise, locale, practice, onChallenge }: {
  exercise: Exercise; locale: Locale; practice: Practice; onChallenge: () => void
}) {
  const t = labels(locale)
  const client = useQueryClient()
  const [variantId, setVariantId] = useState('v1')
  const variant = exercise.variants.find(option => option.id === variantId) ?? exercise.variants[0]
  const guide = useMutation({
    mutationFn: ({ path, variantId }: { path: string; variantId: string }) =>
      api(withLocale(`/exercises/${exercise.id}/${path}`, locale), 'POST', { variantId }),
    onSuccess: async () => {
      await Promise.all([
        client.invalidateQueries({ queryKey: ['content'] }),
        client.invalidateQueries({ queryKey: ['progress'] }),
      ])
    },
  })
  if (!variant) return null
  return <article className="panel practice">
    <header className="practice-heading">
      <div><p className="eyebrow"><Terminal size={16} aria-hidden="true" /> {exercise.id} · {exercise.estimateMinutes} {t.estimated}</p>
        <h3>{exercise.title}</h3></div>
      <span className={`badge ${practice.accepted ? 'badge-mastered' : 'badge-planned'}`}>{practice.accepted ? t.accepted : t.notYet}</span>
    </header>
    {exercise.diagnostic && <p className="notice">{t.diagnostic}</p>}
    {exercise.variants.length > 1 && <label className="variant-select">{t.variant}
      <select value={variant.id} onChange={event => { setVariantId(event.target.value); guide.reset() }}>
        {exercise.variants.map(option => <option value={option.id} key={option.id}>{option.title}</option>)}
      </select>
    </label>}
    <div className="prose"><SafeMarkdown text={variant.prompt} /></div>
    <details><summary>{t.acceptable}</summary><div className="prose"><SafeMarkdown text={exercise.example} /></div></details>
    <div className="guidance">
      {variant.hints.length > 0 && <ol>{variant.hints.map((hint, index) => <li key={index}><SafeMarkdown text={hint} /></li>)}</ol>}
      {variant.solution && <div className="notice"><strong>{t.revealed}</strong><SafeMarkdown text={variant.solution} /></div>}
      <div className="actions">
        {variant.hints.length < 3 && <button className="secondary" disabled={guide.isPending} onClick={() =>
          guide.mutate({ path: `hints/${variant.hints.length + 1}`, variantId: variant.id })}>{t.tip}</button>}
        {!variant.solution && <button className="secondary" aria-describedby={`guide-${exercise.id}`} disabled={guide.isPending}
          onClick={() => guide.mutate({ path: 'reveal', variantId: variant.id })}>{t.reveal}</button>}
      </div>
      {!variant.solution && <p className="muted small" id={`guide-${exercise.id}`}>{t.guideText}</p>}
      {guide.error && <ProblemPanel error={guide.error} locale={locale} />}
    </div>
    {exercise.kind === 'code' ? <RunnerTask key={variant.id} exercise={exercise} variant={variant} locale={locale} history={practice.history} onChallenge={onChallenge} />
      : <RubricTask key={variant.id} exercise={exercise} variant={variant} locale={locale} />}
    <div className="attempts">
      <h4>{t.attempts}</h4>
      <div aria-live="polite">{practice.history.length === 0 ? <p>{t.noAttempts}</p> : <ul>
        {practice.history.map(attempt => <li key={attempt.id}>
          <span>{attempt.variantId} · {t[attempt.verdict]}</span>
          <time dateTime={attempt.createdAt}>{new Date(attempt.createdAt).toLocaleString(locale)}</time>
        </li>)}
      </ul>}</div>
    </div>
  </article>
}
