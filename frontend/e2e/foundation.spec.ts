import { expect, test } from '@playwright/test'
import type { Page } from '@playwright/test'
import { execFile } from 'node:child_process'
import { copyFile, mkdtemp, mkdir, readFile, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'
import { promisify } from 'node:util'

const root = resolve('..')
const run = promisify(execFile)
const python = process.env.QUEST_E2E_PYTHON ?? 'python'
const fixtureEnv = process.env.QUEST_E2E_FIXTURE === '1'
const codeNames: Record<string, string> = {
  'W01-L03-E1': 'setting.py', 'W01-L03-E2': 'fixture_counts.py',
  'W01-L04-E1': 'convert.py', 'W01-L04-E2': 'diagnostic.py', 'G-M0-E1': 'doctor.py',
  'W02-L01-E1': 'w02_l01_e1.py', 'W04-L01-E1': 'w04_l01_e1.py',
}
type QuizPack = { questions: { id: string; correct: string[]; options: { id: string }[] }[] }

async function screenshot(page: Page, file: string) {
  const folder = process.env.QUEST_E2E_EVIDENCE
  if (!folder) return
  await mkdir(folder, { recursive: true })
  await page.screenshot({ path: join(folder, file), animations: 'disabled' })
}

async function assertViewport(page: Page) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(
    page.viewportSize()?.width ?? 0,
  )
}

async function submitQuiz(page: Page, lesson: string, weak = false) {
  const pack = JSON.parse(await readFile(join(root, 'curriculum', 'packs', `${lesson}.json`), 'utf8')) as QuizPack
  for (const item of pack.questions) {
    const answer = weak ? item.options.filter(option => !item.correct.includes(option.id)).slice(0, 1).map(option => option.id) : item.correct
    for (const option of item.options) {
      const unchecked = page.locator(`input[type="checkbox"][name="${item.id}"][value="${option.id}"]`)
      if (!answer.includes(option.id) && await unchecked.count()) await unchecked.uncheck()
    }
    for (const option of answer) await page.locator(`input[name="${item.id}"][value="${option}"]`).check()
  }
  await page.getByRole('button', { name: 'Check answers' }).click()
  await expect(page.getByText(`Latest score ${weak ? 0 : pack.questions.length}/${pack.questions.length}`)).toBeVisible()
}

async function rubric(page: Page, id: string) {
  const exercise = page.locator('article.practice').filter({ hasText: id })
  await expect(exercise.getByRole('textbox')).toBeVisible()
  for (const checkbox of await exercise.getByRole('checkbox').all()) await checkbox.check()
  await exercise.getByRole('textbox').fill('Synthetic evidence. Recorded the run, its limits and a measurable follow-up on a new fixture.')
  await exercise.getByRole('button', { name: 'Record self-assessment' }).click()
  await expect(exercise.getByText('Evidence recorded', { exact: true })).toBeVisible()
}

async function runPractice(page: Page, token: string, workspace: string, id: string, mode: 'reference' | 'starters' | 'timeout') {
  const file = codeNames[id]
  if (!file) throw new Error(`Unknown practice ${id}`)
  const card = page.locator('article.practice').filter({ hasText: id })
  const latest = card.locator('.attempts li').first()
  const priorAttempt = await latest.count() ? await latest.locator('time').getAttribute('datetime') : null
  const command = card.locator('pre').filter({ hasText: /--challenge [a-f0-9-]+/ })
  const priorChallenge = await command.count() ? await command.textContent() : null
  if (mode === 'timeout') await writeFile(join(workspace, file), 'import time\ntime.sleep(5)\n')
  else await copyFile(join(root, 'curriculum', 'labs', mode, file), join(workspace, file))
  await card.getByRole('button', { name: 'Create test attempt' }).click()
  await expect(command).toBeVisible()
  if (priorChallenge) await expect(command).not.toHaveText(priorChallenge)
  const challenge = (await command.textContent())?.match(/--challenge ([a-f0-9-]+)/)?.[1]
  const url = new URL(page.url()).origin
  const args = ['-m', 'quest_runner', 'test', '--exercise', id, '--variant', 'v1', '--workspace', workspace,
    '--api', url, '--challenge', challenge ?? '', '--timeout', mode === 'timeout' ? '1' : '15']
  const output = await run(python, args, { env: { ...process.env, QUEST_RUNNER_TOKEN: token }, timeout: 25000 }).catch(
    (error: { code: number; stdout: string }) => {
      expect(error.code).toBe(1)
      return { stdout: error.stdout }
    },
  )
  const status = mode === 'reference' ? ['test_verified_local', 'Local tests passed'] :
    id.startsWith('W01-L04') && mode === 'starters' ? ['diagnostic_recorded', 'Diagnostic recorded'] : ['failed', 'Failed']
  expect(output.stdout).toContain(status[0])
  if (priorAttempt) await expect(latest.locator('time')).not.toHaveAttribute('datetime', priorAttempt)
  await expect(latest).toContainText(status[1] ?? '')
}

test('M0 in the browser with real local runner evidence and both locales', async ({ page }) => {
  test.skip(!fixtureEnv, 'Requires a fresh, isolated Compose fixture. Set QUEST_E2E_FIXTURE=1.')
  const failures: string[] = []
  page.on('pageerror', error => failures.push(error.message))
  page.on('console', message => { if (message.type() === 'error') failures.push(message.text()) })
  page.on('response', response => { if (response.status() >= 400) failures.push(`${response.status()} ${new URL(response.url()).pathname}`) })
  page.on('requestfailed', request => { if (request.failure()?.errorText !== 'net::ERR_ABORTED') failures.push(request.url()) })
  const workspace = await mkdtemp(join(tmpdir(), 'quest-browser-'))
  try {
    await page.goto('/')
    expect(new URL(page.url()).port).not.toBe('8000')
    const initial = await page.request.get('/api/v1/progress')
    expect((await initial.json()).revision).toBe(0)
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('Карта світу')
    await expect(page.locator('.atlas-stats dd').last()).toHaveText(/0\s*\/\s*\d+/)
    await page.keyboard.press('Tab')
    await expect(page.getByRole('link', { name: 'Перейти до змісту' })).toBeFocused()
    await page.keyboard.press('Enter')
    await expect(page.locator('main')).toBeFocused()
    await page.evaluate(() => window.scrollTo(0, 0))
    await assertViewport(page)
    await screenshot(page, 'desktop-uk-roadmap.png')
    await page.getByRole('link', { name: 'Відкрити етап' }).click()
    await expect(page.locator('.entry-list').first().getByRole('link')).toHaveCount(4)
    await page.locator('a[href="/lessons/W01-L01"]').click()
    await page.getByRole('button', { name: 'Позначити прочитаним' }).click()
    await expect(page.getByText('Прочитання записано')).toBeVisible()
    const first = page.locator('#quiz input').first()
    const draft = await first.getAttribute('value')
    const draftQuestion = await first.getAttribute('name')
    await first.check()
    await page.getByRole('button', { name: 'English' }).click()
    await expect(page.getByRole('heading', { level: 1 })).toContainText('AI landscape')
    await expect(page.locator(`input[name="${draftQuestion}"][value="${draft}"]`)).toBeChecked()
    await page.reload()
    await expect(page.getByRole('button', { name: 'English' })).toHaveAttribute('aria-pressed', 'true')
    await expect(page.getByText('Read recorded')).toBeVisible()
    await page.locator('#theory summary').click()
    await expect(page.locator('#theory details')).toHaveAttribute('open', '')
    await page.evaluate(() => window.scrollTo(0, 0))
    await screenshot(page, 'desktop-en-lesson.png')
    await submitQuiz(page, 'W01-L01', true)
    await submitQuiz(page, 'W01-L01')
    await rubric(page, 'W01-L01-E1')
    await rubric(page, 'W01-L01-E2')
    await expect(page.getByText('Mastered', { exact: true })).toBeVisible()

    await page.getByRole('link', { name: 'Settings' }).click()
    await page.getByRole('button', { name: 'Generate token' }).click()
    const secret = page.locator('div[role="status"] .code-block pre')
    await expect(secret).toBeVisible()
    const token = (await secret.textContent())?.trim() ?? ''
    expect(/^[A-Za-z0-9_-]{43}$/.test(token)).toBe(true)

    await page.goto('/stages/W02')
    await page.locator('a[href="/lessons/W02-L01"]').click()
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
    await expect(page.getByRole('link', { name: 'Module gate 0 · Environment and gap plan' })).toBeVisible()
    await page.getByRole('button', { name: 'Mark as read' }).click()
    await submitQuiz(page, 'W02-L01')
    await expect(page.getByText('Evidence saved.', { exact: false })).toBeVisible()
    await rubric(page, 'W02-L01-E2')
    await runPractice(page, token, workspace, 'W02-L01-E1', 'reference')
    await expect(page.getByText('Prerequisites pending', { exact: true })).toBeVisible()
    await page.evaluate(() => window.scrollTo(0, 0))
    await screenshot(page, 'desktop-en-python-provisional.png')

    await page.goto('/stages/W04')
    await page.getByRole('link', { name: 'Project milestones' }).click()
    await expect(page).toHaveURL(/\/projects\/A#W04$/)
    await expect(page.locator('article.panel')).toHaveCount(3)
    await page.getByRole('button', { name: 'Українська' }).click()
    await expect(page.getByRole('heading', { level: 1 })).toContainText('API обробки документів')
    await page.evaluate(() => window.scrollTo(0, 0))
    await screenshot(page, 'desktop-uk-project-a.png')
    await page.getByRole('button', { name: 'English' }).click()
    await page.goto('/lessons/W04-L01')
    await runPractice(page, token, workspace, 'W04-L01-E1', 'reference')
    await expect(page.getByText('Evidence saved.', { exact: false })).toBeVisible()

    await page.goto('/lessons/W01-L04')
    await runPractice(page, token, workspace, 'W01-L04-E1', 'starters')
    await runPractice(page, token, workspace, 'W01-L04-E2', 'reference')
    await page.getByRole('button', { name: 'Mark as read' }).click()
    await submitQuiz(page, 'W01-L04')
    await expect(page.getByText('Prerequisites pending', { exact: true })).toBeVisible()

    await page.goto('/lessons/W01-L02')
    await page.getByRole('button', { name: 'Mark as read' }).click()
    await rubric(page, 'W01-L02-E1')
    await rubric(page, 'W01-L02-E2')
    await submitQuiz(page, 'W01-L02')
    await expect(page.getByText('Mastered', { exact: true })).toBeVisible()

    await page.goto('/lessons/W01-L03')
    await expect(page.locator('#examples code span[class^="syntax-"]').first()).toBeVisible()
    await page.getByRole('button', { name: 'Mark as read' }).click()
    await runPractice(page, token, workspace, 'W01-L03-E1', 'timeout')
    await runPractice(page, token, workspace, 'W01-L03-E1', 'starters')
    await runPractice(page, token, workspace, 'W01-L03-E1', 'reference')
    await runPractice(page, token, workspace, 'W01-L03-E2', 'reference')
    await submitQuiz(page, 'W01-L03')
    await expect(page.getByText('Mastered', { exact: true })).toBeVisible()

    await page.goto('/lessons/W01-L04')
    await expect(page.getByText('Mastered', { exact: true })).toBeVisible()
    await page.goto('/reviews/SR-W01')
    await rubric(page, 'SR-W01-E1')
    await submitQuiz(page, 'SR-W01')
    await expect(page.getByText('Mastered', { exact: true })).toBeVisible()
    await page.goto('/gates/G-M0')
    await runPractice(page, token, workspace, 'G-M0-E1', 'reference')
    await rubric(page, 'G-M0-E2')
    await submitQuiz(page, 'G-M0')
    await expect(page.getByText('Mastered', { exact: true })).toBeVisible()
    await page.evaluate(() => window.scrollTo(0, 0))
    await screenshot(page, 'desktop-en-gate.png')

    await page.setViewportSize({ width: 390, height: 844 })
    await page.getByRole('button', { name: 'Українська' }).click()
    await expect(page.getByText('Засвоєно', { exact: true })).toBeVisible()
    await expect(page.getByRole('heading', { level: 1 })).toContainText(/Середовище|середовище/)
    await assertViewport(page)
    await screenshot(page, 'mobile-uk-gate.png')
    await page.getByRole('link', { name: 'AI Engineering Quest' }).click()
    await expect(page.locator('.atlas-stats dd').last()).toHaveText(/5\s*\/\s*24/)
    await expect(page.locator('[data-atlas-marker="W01"]')).toHaveAttribute('data-state', 'mastered')
    await assertViewport(page)
    await screenshot(page, 'mobile-uk-roadmap.png')
    await page.getByRole('button', { name: 'Список регіонів' }).click()
    await page.locator('.atlas-list-group a[href="/stages/W07"]').click()
    await expect(page.locator('.entry-list').first().getByRole('link')).toHaveCount(0)
    await page.getByRole('button', { name: 'English' }).click()
    await expect(page.getByText('Planned stage outline')).toBeVisible()
    await assertViewport(page)
    await screenshot(page, 'mobile-en-planned-stage.png')
    await page.reload()
    await expect(page.getByRole('button', { name: 'English' })).toHaveAttribute('aria-pressed', 'true')
    expect(failures).toEqual([])
  } finally {
    await rm(workspace, { recursive: true, force: true })
  }
})

test('completed fixture survives a container restart', async ({ page }) => {
  test.skip(process.env.QUEST_E2E_RESTART !== '1', 'Run after completing the browser scenario and restarting both containers.')
  await page.goto('/gates/G-M0')
  await expect(page.getByRole('button', { name: 'English' })).toHaveAttribute('aria-pressed', 'true')
  await expect(page.getByText('Mastered', { exact: true })).toBeVisible()
  const progress = await page.request.get('/api/v1/progress')
  expect(progress.ok()).toBeTruthy()
  const state = await progress.json()
  expect(state.xp).toBe(950)
  expect(state.level).toBe(2)
  expect(state.items['W01-L04'].practices['W01-L04-E1'].history[0].verdict).toBe('diagnostic_recorded')
  expect(state.items['W02-L01'].state).toBe('mastered')
  expect(state.items['W04-L01'].provisionalEvidence).toBe(true)
  await screenshot(page, 'desktop-en-restarted.png')
  const evidence = page.locator('article.practice').filter({ hasText: 'G-M0-E1' }).locator('.attempts')
  await expect(evidence.getByText('v1 · Local tests passed')).toBeVisible()
  await evidence.scrollIntoViewIfNeeded()
  await screenshot(page, 'desktop-en-runner-proof.png')
})
