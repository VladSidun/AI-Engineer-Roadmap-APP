import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Breadcrumbs } from './roadmap'
import { useSettings } from '../app/queries'
import { api } from '../lib/api'
import type { Locale, Settings } from '../lib/api'
import { labels } from '../lib/messages'
import { Code, ProblemPanel } from '../lib/ui'

export function SettingsPage({ locale }: { locale: Locale }) {
  const [token, setToken] = useState('')
  const settings = useSettings()
  const client = useQueryClient()
  const t = labels(locale)
  const updateToken = useMutation({
    mutationFn: (method: 'POST' | 'DELETE') => api<Settings & { token?: string }>('/settings/runner-token', method),
    onSuccess: ({ token: issued, ...prefs }) => {
      setToken(issued ?? '')
      client.setQueryData(['settings'], prefs)
    },
  })
  return <>
    <Breadcrumbs locale={locale} current={t.settings} />
    <header className="page-header"><h1>{t.settings}</h1></header>
    <section className="panel prose">
      <h2>{t.runner}</h2><p>{t.tokenInfo}</p>
      <p role="status">{settings.data?.runnerTokenActive ? t.runnerActive : t.runnerInactive}</p>
      <div className="actions">
        <button className="primary" disabled={updateToken.isPending} onClick={() => updateToken.mutate('POST')}>
          {settings.data?.runnerTokenActive ? t.rotate : t.generate}
        </button>
        {settings.data?.runnerTokenActive && <button className="secondary" disabled={updateToken.isPending}
          onClick={() => updateToken.mutate('DELETE')}>{t.revoke}</button>}
      </div>
      {updateToken.error && <ProblemPanel error={updateToken.error} locale={locale} />}
      {token && <div role="status"><p>{t.tokenOnce}</p><Code key={token} content={token} locale={locale} /></div>}
      <p>{t.install}</p><Code content="python -m pip install --require-hashes -r runner/requirements.lock&#10;python -m pip install --no-build-isolation --no-deps ./runner" locale={locale} />
      <p>{t.useToken}</p><Code content={'$env:QUEST_RUNNER_TOKEN = Read-Host -MaskInput "Quest Runner token"\n# Bash: read -rs QUEST_RUNNER_TOKEN && export QUEST_RUNNER_TOKEN'} locale={locale} />
    </section>
  </>
}
