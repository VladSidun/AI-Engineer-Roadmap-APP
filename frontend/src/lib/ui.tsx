import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import Markdown from 'react-markdown'
import type { Entry, ItemState, Locale } from './api'
import { errorMessage, labels } from './messages'

export function StateBadge({ entry, state: recordedState, locale }: {
  entry?: Entry; state?: ItemState['state']; locale: Locale
}) {
  const state = entry?.availability === 'planned' ? 'planned' : recordedState ?? 'available'
  return <span className={`badge badge-${state}`}>{labels(locale)[state]}</span>
}

export function ProblemPanel({ error, locale, retry }: { error: unknown; locale: Locale; retry?: () => void }) {
  return <div className="problem" role="alert">
    <span>{errorMessage(error, locale)}</span>
    {retry && <button className="secondary" onClick={retry}>{labels(locale).tryAgain}</button>}
  </div>
}

export function SafeMarkdown({ text }: { text: string }) {
  return <Markdown
    skipHtml
    disallowedElements={['img']}
    urlTransform={(url) => url.startsWith('https://') || /^#[a-zA-Z][\w-]*$/.test(url) ? url : ''}
  >{text}</Markdown>
}

export function Code({ content, locale, python = false }: { content: string; locale: Locale; python?: boolean }) {
  const [copied, setCopied] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const tokens = useQuery({
    queryKey: ['python-tokens', python ? content : ''],
    enabled: python,
    queryFn: async () => (await import('./pythonSyntax')).pythonTokens(content),
    staleTime: Infinity,
  })
  const t = labels(locale)
  return <div className="code-block">
    <button className="secondary" onClick={async () => {
      try { await navigator.clipboard.writeText(content); setCopied(true); setError(null) }
      catch (problem) { setError(problem) }
    }}>{copied ? t.copied : t.copy}</button>
    <pre><code>{tokens.data ? tokens.data.map((line, index) => <span key={index}>
      {index > 0 ? '\n' : ''}{line.map(token =>
        <span key={token.offset} className={`syntax-${token.color?.slice(1).toLowerCase() ?? 'plain'}`}>{token.content}</span>
      )}
    </span>) : content}</code></pre>
    {error !== null && <ProblemPanel error={error} locale={locale} />}
  </div>
}
