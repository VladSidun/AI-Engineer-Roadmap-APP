import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { api, withLocale } from '../lib/api'
import type { Answers, Locale, Question, QuizResult } from '../lib/api'
import { labels } from '../lib/messages'
import { ProblemPanel } from '../lib/ui'

export function Quiz({ id, questions, locale, latest }: { id: string; questions: Question[]; locale: Locale; latest?: string }) {
  const t = labels(locale)
  const client = useQueryClient()
  const [answers, setAnswers] = useState<Answers>({})
  const [submission, setSubmission] = useState<{ id: string; answers: Answers }>()
  const path = `/assessments/${id}/attempts`
  const recent = useQuery({
    queryKey: ['quiz', id, latest, locale], enabled: Boolean(latest),
    queryFn: () => api<QuizResult>(withLocale(`${path}/${latest}`, locale)),
  })
  const submit = useMutation({
    mutationFn: (body: { submissionId: string; answers: Answers }) => api<QuizResult>(withLocale(path, locale), 'POST', body),
    onSuccess: async data => {
      client.setQueryData(['quiz', id, data.attempt.id, locale], data)
      await client.invalidateQueries({ queryKey: ['progress'] })
    },
  })
  function choose(question: Question, option: string, checked: boolean) {
    setAnswers(old => {
      const choices = old[question.id] ?? []
      return { ...old, [question.id]: question.multiple ?
        (checked ? [...choices, option] : choices.filter(value => value !== option)) : [option] }
    })
  }
  const result = recent.data
  return <section id="quiz" className="section">
    <h2>{t.quiz}</h2>
    <form onSubmit={event => {
      event.preventDefault()
      const submissionId = submission?.answers === answers ? submission.id : crypto.randomUUID()
      setSubmission({ id: submissionId, answers })
      submit.mutate({ submissionId, answers })
    }}>
      {questions.map(question => <fieldset key={question.id} className="quiz-question">
        <legend>{question.prompt}</legend>
        <p className="muted small">{question.multiple ? t.many : t.one}</p>
        {question.options.map(option => <label key={option.id} className="choice">
          <input type={question.multiple ? 'checkbox' : 'radio'} name={question.id} value={option.id} checked={Boolean(answers[question.id]?.includes(option.id))}
            onChange={event => choose(question, option.id, event.target.checked)} />
          {option.title}
        </label>)}
      </fieldset>)}
      <button className="primary" disabled={submit.isPending || !questions.every(question => answers[question.id]?.length)}>{t.checkAnswers}</button>
      {submit.error && <ProblemPanel error={submit.error} locale={locale} />}
    </form>
    {recent.error && <ProblemPanel error={recent.error} locale={locale} retry={() => { void recent.refetch() }} />}
    {result && <div className="panel feedback" aria-label={t.assessmentResult}>
      <p role="status"><strong>{t.score} {result.attempt.correct}/{result.attempt.total}</strong> · {result.attempt.passed ? t.checkPassed : t.checkFailed}</p>
      {result.feedback.map(feedback => <details key={feedback.id} open={!feedback.correct || undefined}>
        <summary>{questions.find(question => question.id === feedback.id)?.prompt} · {feedback.correct ? t.correct : t.incorrect}</summary>
        <ul>{feedback.options.map(option => <li key={option.id}>{option.explanation}</li>)}</ul>
      </details>)}
    </div>}
  </section>
}
