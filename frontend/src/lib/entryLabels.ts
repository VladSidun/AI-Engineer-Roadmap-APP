import type { Entry, Locale } from './api'
import { labels } from './messages'

export function entryNumber(id: string, locale: Locale): string {
  const t = labels(locale)
  if (id.startsWith('G-M')) return `${t.moduleGate} ${Number(id.slice(3))}`
  if (id.startsWith('SR-W')) return locale === 'uk' ? `Перевірка етапу ${Number(id.slice(4))}` : `Stage ${Number(id.slice(4))} review`
  const lesson = /^W\d+-L(\d+)$/.exec(id)
  if (lesson) return `${t.lesson} ${Number(lesson[1])}`
  if (/^W\d+$/.test(id)) return `${t.stage} ${Number(id.slice(1))}`
  if (/^M\d+$/.test(id)) return `${t.module} ${Number(id.slice(1))}`
  return ''
}

export function entryName(entry: Pick<Entry, 'id' | 'title'>): string {
  if (entry.id.startsWith('G-M')) return entry.title.replace(/^(?:Module challenge|Випробування модуля) · /, '')
  if (entry.id.startsWith('SR-W') && ['Stage review', 'Перевірка етапу'].includes(entry.title)) return ''
  return entry.title
}

export function entryLabel(entry: Pick<Entry, 'id' | 'title'>, locale: Locale): string {
  return [entryNumber(entry.id, locale), entryName(entry)].filter(Boolean).join(' · ')
}
