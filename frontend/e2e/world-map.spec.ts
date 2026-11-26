import { expect, test } from '@playwright/test'
import type { Locator, Page } from '@playwright/test'
import { mkdir } from 'node:fs/promises'
import { join } from 'node:path'
import { contentPath } from '../src/lib/api'
import type { Entry, Roadmap } from '../src/lib/api'

test.skip(process.env.QUEST_E2E_MAP !== '1', 'Requires an isolated local profile. Set QUEST_E2E_MAP=1.')

function errors(page: Page) {
  const failures: string[] = []
  page.on('pageerror', error => failures.push(error.message))
  page.on('console', message => { if (message.type() === 'error') failures.push(message.text()) })
  page.on('response', response => { if (response.status() >= 400) failures.push(`${response.status()} ${new URL(response.url()).pathname}`) })
  page.on('requestfailed', request => { if (request.failure()?.errorText !== 'net::ERR_ABORTED') failures.push(request.url()) })
  return failures
}

async function screenshot(page: Page, filename: string) {
  const target = process.env.QUEST_E2E_EVIDENCE
  if (!target) return
  await mkdir(target, { recursive: true })
  await page.screenshot({ path: join(target, filename), animations: 'disabled' })
}

async function camera(surface: Locator) {
  return surface.evaluate(node => ({
    x: Number(node.getAttribute('data-camera-x')), y: Number(node.getAttribute('data-camera-y')),
    zoom: Number(node.getAttribute('data-camera-zoom')),
  }))
}

function waitForSave(page: Page) {
  return page.waitForResponse(response => response.url().endsWith('/api/v1/viewport/main')
    && response.request().method() === 'PUT' && response.ok())
}

async function moveCamera(page: Page, move: () => Promise<void>) {
  const saved = waitForSave(page)
  await move()
  await saved
}

async function openLessonAndReturn(page: Page, id: string) {
  await page.goto(`/lessons/${id}`)
  await expect(page.locator('main h1')).toBeVisible()
  await expect.poll(async () => (await (await page.request.get('/api/v1/viewport/main')).json()).lastActivityId).toBe(id)
  await page.goto('/')
}

async function checkRegionLabels(surface: Locator) {
  const collisions = await surface.evaluate(node => {
    const names = [...node.querySelectorAll('.atlas-region-title')]
    const markers = [...node.querySelectorAll('.atlas-node-shape')]
    const overlaps = (left: DOMRect, right: DOMRect) =>
      left.left < right.right && left.right > right.left && left.top < right.bottom && left.bottom > right.top
    return names.flatMap(label => markers.filter(marker => overlaps(label.getBoundingClientRect(), marker.getBoundingClientRect()))
      .map(marker => [label.textContent, marker.closest('[data-atlas-marker]')?.getAttribute('data-atlas-marker')]))
  })
  expect(collisions).toEqual([])
  await expect(surface.locator('.atlas-region:has(.atlas-region-title)')).toHaveCount(10)
}

test('desktop world map supports pan, cursor zoom, fit, keyboard, routes and reload', async ({ page }) => {
  const failures = errors(page)
  await openLessonAndReturn(page, 'W01-L02')
  const surface = page.locator('.atlas-surface')
  await expect(surface).toBeVisible()
  await expect(surface.locator('[data-atlas-marker]')).toHaveCount(40)
  await expect(surface.locator('.atlas-gate')).toHaveCount(10)
  await expect(surface.locator('.atlas-route')).toHaveCount(29)
  await page.getByRole('button', { name: 'Українська' }).click()
  await moveCamera(page, () => page.getByRole('button', { name: 'Показати весь світ' }).click())
  await checkRegionLabels(surface)
  await screenshot(page, 'desktop-uk-world-fit.png')
  await moveCamera(page, () => page.getByRole('button', { name: 'Центрувати на поточній активності' }).click())
  await expect(surface.locator('[data-atlas-marker="W01"] .atlas-node-caption')).toContainText('Етап 1')
  await expect(surface.locator('[data-atlas-marker="W01"] .atlas-node-caption')).toContainText('Карта ШІ')
  await screenshot(page, 'desktop-uk-world.png')
  const box = (await surface.boundingBox())!
  const start = await camera(surface)
  await page.mouse.move(box.x + box.width * .60, box.y + box.height * .54)
  await page.mouse.down()
  await page.mouse.move(box.x + box.width * .50, box.y + box.height * .37, { steps: 10 })
  const pan = waitForSave(page)
  await page.mouse.up()
  await pan
  const panned = await camera(surface)
  expect(panned.x).toBeGreaterThan(start.x + 30)
  expect(panned.y).toBeGreaterThan(start.y + 30)
  expect(panned.zoom).toBe(start.zoom)

  await surface.focus()
  const anchor = { x: box.width * .66, y: box.height * .44 }
  await page.mouse.move(box.x + anchor.x, box.y + anchor.y)
  const wheel = waitForSave(page)
  await page.mouse.wheel(0, -170)
  await wheel
  const closer = await camera(surface)
  expect(closer.zoom).toBeGreaterThan(panned.zoom)
  const worldX = (state: typeof closer) => state.x + (anchor.x - box.width / 2) / state.zoom
  const worldY = (state: typeof closer) => state.y + (anchor.y - box.height / 2) / state.zoom
  expect(Math.abs(worldX(panned) - worldX(closer))).toBeLessThan(1)
  expect(Math.abs(worldY(panned) - worldY(closer))).toBeLessThan(1)
  await page.getByRole('button', { name: 'English' }).click()
  await expect(page.getByRole('heading', { level: 1, name: 'World map' })).toBeVisible()
  expect(await camera(surface)).toEqual(closer)
  await page.reload()
  await expect(surface).toHaveAttribute('data-camera-zoom', closer.zoom.toFixed(5))
  expect(await camera(surface)).toEqual(closer)

  await moveCamera(page, () => page.getByRole('button', { name: 'Fit world to view' }).click())
  await checkRegionLabels(surface)
  expect((await camera(surface)).zoom).toBeLessThan(.4)
  await screenshot(page, 'desktop-en-world-fit.png')
  await surface.locator('[data-atlas-marker="W07"] .atlas-node-shape').click()
  await page.getByRole('button', { name: 'Show prerequisites' }).click()
  await expect(surface.locator('.atlas-route-required')).toHaveCount(1)
  await expect(page.getByRole('link', { name: 'Module gate 2 · Backend Engineering', exact: true })).toHaveAttribute('href', '/gates/G-M2')
  await page.getByRole('button', { name: 'Show prerequisites' }).click()
  await page.setViewportSize({ width: 1920, height: 1080 })
  await moveCamera(page, () => page.getByRole('button', { name: 'Fit world to view' }).click())
  await checkRegionLabels(surface)
  await screenshot(page, 'wide-en-world-fit.png')
  await page.setViewportSize({ width: 1440, height: 900 })
  await moveCamera(page, () => page.getByRole('button', { name: 'Fit world to view' }).click())
  const overview = page.getByRole('button', { name: 'World overview' })
  await moveCamera(page, () => overview.click({ position: { x: 120, y: 30 } }))
  expect((await camera(surface)).zoom).toBeGreaterThan(.6)
  await surface.focus()
  const beforeKey = await camera(surface)
  await moveCamera(page, () => surface.press('ArrowLeft'))
  expect((await camera(surface)).x).toBeLessThan(beforeKey.x)
  await moveCamera(page, () => surface.press('Home'))
  const plannedDrag = surface.locator('[data-atlas-marker="G-M0"] .atlas-node-shape')
  const dragBox = (await plannedDrag.boundingBox())!
  await page.mouse.move(dragBox.x + dragBox.width / 2, dragBox.y + dragBox.height / 2)
  await page.mouse.down()
  await page.mouse.move(dragBox.x - 15, dragBox.y + 70, { steps: 5 })
  await page.mouse.up()
  await expect(surface.locator('[data-atlas-marker="G-M0"]')).toHaveAttribute('aria-pressed', 'false')
  await moveCamera(page, () => surface.press('Home'))
  await surface.press('Enter')
  const current = surface.locator('[aria-current="step"]')
  await expect(current).toBeFocused()
  await current.press('ArrowRight')
  await expect(surface.locator('[data-atlas-marker="G-M0"]')).toBeFocused()
  await page.getByRole('link', { name: 'Open challenge' }).click()
  await expect(page).toHaveURL(/\/gates\/G-M0$/)
  await page.goBack()
  await expect(surface.locator('[data-atlas-marker="G-M0"]')).toHaveAttribute('aria-pressed', 'true')
  await page.getByRole('button', { name: 'Region list' }).click()
  await page.getByRole('searchbox').fill('W07')
  await page.getByRole('link', { name: /Stage 7.*Machine learning fundamentals.*Planned/s }).click()
  await expect(page.getByText('Planned stage outline')).toBeVisible()
  await expect(page.locator('.entry-list').first().getByRole('link')).toHaveCount(0)
  await expect.poll(async () => {
    const response = await page.request.get('/api/v1/viewport/main')
    return (await response.json()).lastStageId
  }).toBe('W07')
  await page.goto('/gates/G-M3')
  await expect(page.getByRole('heading', { name: 'Stages' })).toBeVisible()
  await expect(page.locator('.section').getByRole('link')).toHaveCount(2)
  expect(failures).toEqual([])
})

test.describe('mobile world map', () => {
  test.use({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true })

  test('supports one-finger pan, two-finger zoom, taps and the region list', async ({ page, context }) => {
    const failures = errors(page)
    await openLessonAndReturn(page, 'W01-L01')
    const surface = page.locator('.atlas-surface')
    await expect(surface).toBeVisible()
    await page.getByRole('button', { name: 'Українська' }).tap()
    await moveCamera(page, () => page.getByRole('button', { name: 'Показати весь світ' }).tap())
    await moveCamera(page, () => page.getByRole('button', { name: 'Центрувати на поточній активності' }).tap())
    await screenshot(page, 'mobile-uk-world.png')
    await surface.scrollIntoViewIfNeeded()
    const box = (await surface.boundingBox())!
    const session = await context.newCDPSession(page)
    const touch = (type: 'touchStart' | 'touchMove' | 'touchEnd', points: [number, number][]) =>
      session.send('Input.dispatchTouchEvent', { type, touchPoints: points.map(([x, y], id) => ({ x: box.x + x, y: box.y + y, id })) })
    const initial = await camera(surface)
    await touch('touchStart', [[170, 130]])
    await touch('touchMove', [[120, 170]])
    await touch('touchMove', [[95, 205]])
    await touch('touchEnd', [])
    expect((await camera(surface)).x).toBeGreaterThan(initial.x)
    expect((await camera(surface)).y).toBeLessThan(initial.y)
    await touch('touchStart', [[134, 143], [220, 143]])
    await touch('touchMove', [[101, 127], [259, 156]])
    await touch('touchEnd', [])
    expect((await camera(surface)).zoom).toBeGreaterThan(initial.zoom * 1.3)
    await session.detach()
    await moveCamera(page, () => page.getByRole('button', { name: 'Показати весь світ' }).tap())
    await moveCamera(page, () => page.getByRole('button', { name: 'Центрувати на поточній активності' }).tap())
    const marker = surface.locator('[data-atlas-marker="M0"] .atlas-hit')
    await marker.tap()
    await expect(surface.locator('[data-atlas-marker="M0"]')).toHaveAttribute('aria-pressed', 'true')
    await expect(page.getByRole('link', { name: 'Відкрити регіон' })).toBeVisible()
    await moveCamera(page, () => surface.tap({ position: { x: 74, y: 115 } }))
    await expect(surface.locator('[data-atlas-marker="W01"]')).toHaveAttribute('aria-pressed', 'true')
    await page.getByRole('button', { name: 'English' }).tap()
    await page.getByRole('button', { name: 'Region list' }).tap()
    await expect(page.locator('.atlas-list-group')).toHaveCount(10)
    await page.getByRole('searchbox').fill('W01')
    await screenshot(page, 'mobile-en-region-list.png')
    await page.locator('.atlas-list a[href="/stages/W01"]').tap()
    await page.locator('a[href="/lessons/W01-L01"]').tap()
    await expect(page.getByRole('heading', { level: 1 })).toContainText('AI landscape')
    await expect(page.locator('html')).toHaveAttribute('lang', 'en')
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390)
    expect(failures).toEqual([])
  })
})

test('the current step and its named navigation remain available while browsing the map', async ({ page }) => {
  const failures = errors(page)
  await openLessonAndReturn(page, 'W02-L03')
  await page.getByRole('button', { name: 'English' }).click()
  const pane = page.getByRole('complementary', { name: 'Current step' })
  const resume = pane.getByRole('link', { name: 'Continue learning' })
  const surface = page.locator('.atlas-surface')
  await expect(resume).toHaveAttribute('href', '/lessons/W02-L03')
  await expect(pane.getByRole('link', { name: 'Module 1 · Professional Python' })).toBeVisible()
  await expect(pane.getByRole('link', { name: 'Stage 2 · Maintainable Python' })).toBeVisible()
  expect((await pane.boundingBox())!.x).toBeLessThan((await surface.boundingBox())!.x)
  await moveCamera(page, () => page.getByRole('button', { name: 'Fit world to view' }).click())
  await surface.locator('[data-atlas-marker="W07"] .atlas-node-shape').click()
  await expect(surface.locator('[data-atlas-marker="W07"]')).toHaveAttribute('aria-pressed', 'true')
  await expect(resume).toHaveAttribute('href', '/lessons/W02-L03')
  await moveCamera(page, () => surface.click({ position: { x: 92, y: 87 } }))
  await expect(surface.locator('[data-atlas-marker="W02"]')).toHaveAttribute('aria-pressed', 'true')
  await expect.poll(async () => (await camera(surface)).zoom).toBeGreaterThanOrEqual(.9)
  await page.reload()
  await expect(resume).toHaveAttribute('href', '/lessons/W02-L03')
  await screenshot(page, 'desktop-en-current-step.png')
  await resume.click()
  const breadcrumbs = page.locator('.breadcrumbs')
  await expect(breadcrumbs.getByRole('link', { name: 'Module 1 · Professional Python' })).toBeVisible()
  await expect(breadcrumbs.getByRole('link', { name: 'Stage 2 · Maintainable Python' })).toBeVisible()
  await expect(breadcrumbs.locator('[aria-current="page"]')).toContainText('Lesson 3')
  expect(failures).toEqual([])
})

test('all published packs render in both languages without blocking future lessons', async ({ page }) => {
  test.setTimeout(120_000)
  const failures = errors(page)
  for (const locale of [{ key: 'uk', button: 'Українська' }, { key: 'en', button: 'English' }]) {
    await page.goto('/')
    await page.getByRole('button', { name: locale.button }).click()
    await expect(page.locator('html')).toHaveAttribute('lang', locale.key)
    const response = await page.request.get(`/api/v1/campaigns/main/map?locale=${locale.key}`)
    const roadmap = await response.json() as Roadmap
    const entries: Entry[] = roadmap.modules.flatMap(region => [
      ...region.stages.flatMap(stage => [...stage.lessons, stage.review]), region.gate,
    ]).filter(entry => entry.availability === 'published')
    expect(entries).toHaveLength(33)
    for (const entry of entries) {
      await page.goto(contentPath(entry.id))
      await expect(page.getByRole('heading', { name: entry.title, level: 1, exact: true })).toBeVisible()
      await expect(page.locator('#overview .prose, #overview')).toHaveCount(1)
      await expect(page.locator('#practice article.practice').first()).toBeVisible()
      await expect(page.locator('#quiz .quiz-question').first()).toBeVisible()
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(1440)
    }
  }
  expect(failures).toEqual([])
})
