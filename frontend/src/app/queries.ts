import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { api, withLocale } from '../lib/api'
import type { Locale, Progress, Settings } from '../lib/api'

export function useLocalized<T>(path: string, locale: Locale, preserve = false) {
  return useQuery({ queryKey: ['content', path, locale], queryFn: () => api<T>(withLocale(path, locale)), placeholderData: preserve ? keepPreviousData : undefined })
}

export function useSettings() {
  return useQuery({ queryKey: ['settings'], queryFn: () => api<Settings>('/settings') })
}

export function useProgress(poll = false) {
  return useQuery({
    queryKey: ['progress'], queryFn: () => api<Progress>('/progress'), refetchInterval: poll ? 2500 : false,
  })
}
