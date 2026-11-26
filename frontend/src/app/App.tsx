import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Compass, Settings2 } from 'lucide-react'
import { useEffect, useRef } from 'react'
import { Link, Navigate, NavLink, Route, Routes, useLocation } from 'react-router-dom'
import { api } from '../lib/api'
import type { Locale, Settings } from '../lib/api'
import { labels } from '../lib/messages'
import { ProblemPanel } from '../lib/ui'
import { MapPage, RegionPage, StagePage, mapPath } from '../features/roadmap'
import { SettingsPage } from '../features/settings'
import { LearningPage } from '../features/learning'
import { ProjectPage } from '../features/project'
import { useSettings } from './queries'

export function App() {
  const settings = useSettings()
  const client = useQueryClient()
  const locale = settings.data?.locale ?? 'uk'
  const t = labels(locale)
  const { pathname } = useLocation()
  const content = useRef<HTMLElement>(null)
  const previousPath = useRef(pathname)
  const preference = useMutation({
    mutationFn: (next: Locale) => api<Settings>('/settings', 'PUT', { locale: next }),
    onSuccess: data => client.setQueryData(['settings'], data),
  })
  useEffect(() => { document.documentElement.lang = locale }, [locale])
  useEffect(() => {
    if (previousPath.current === pathname) return
    const openingRoadmap = previousPath.current === '/' && pathname === mapPath
    previousPath.current = pathname
    if (openingRoadmap) return
    window.scrollTo(0, 0)
    content.current?.focus()
  }, [pathname])
  return <>
    <a className="skip-link" href="#main">{t.skip}</a>
    <header className="site-header">
      <div className="shell header-inner">
        <Link className="brand" to={mapPath}>
          <img src="/assets/quest.svg" alt="" width="37" height="37" />
          <span>AI Engineering Quest</span>
        </Link>
        <nav className="main-nav" aria-label={t.campaign}>
          <NavLink to={mapPath}><Compass size={17} aria-hidden="true" />{t.roadmap}</NavLink>
          <NavLink to="/settings"><Settings2 size={17} aria-hidden="true" />{t.settings}</NavLink>
        </nav>
        <div className="languages" role="group" aria-label={t.language}>
          {(['uk', 'en'] as const).map(language => <button key={language} lang={language} aria-pressed={locale === language}
            aria-label={language === 'uk' ? 'Українська' : 'English'} disabled={!settings.data || preference.isPending}
            onClick={() => { if (language !== locale) preference.mutate(language) }}>{language === 'uk' ? 'UA' : 'EN'}</button>)}
        </div>
      </div>
    </header>
    <main ref={content} id="main" tabIndex={-1} className="shell main">
      {settings.error ? <ProblemPanel locale={locale} error={settings.error} retry={() => { void settings.refetch() }} />
        : !settings.data ? <p role="status">{t.waiting}</p>
        : <>
          {preference.error && <ProblemPanel error={preference.error} locale={locale} />}
          <Routes>
            <Route path="/" element={<Navigate to={mapPath} replace />} />
            <Route path={mapPath} element={<MapPage locale={locale} />} />
            <Route path="/regions/:id" element={<RegionPage locale={locale} />} />
            <Route path="/stages/:id" element={<StagePage locale={locale} />} />
            <Route path="/lessons/:id" element={<LearningPage key={pathname} kind="lesson" locale={locale} />} />
            <Route path="/reviews/:id" element={<LearningPage key={pathname} kind="review" locale={locale} />} />
            <Route path="/gates/:id" element={<LearningPage key={pathname} kind="gate" locale={locale} />} />
            <Route path="/projects/:id" element={<ProjectPage locale={locale} />} />
            <Route path="/settings" element={<SettingsPage locale={locale} />} />
            <Route path="*" element={<h1>{t.missingPage}</h1>} />
          </Routes>
        </>}
    </main>
    <footer className="site-footer"><div className="shell">AI Engineering Quest <span>·</span> {t.campaign}</div></footer>
  </>
}
