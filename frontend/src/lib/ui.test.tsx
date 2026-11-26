import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { SafeMarkdown, StateBadge } from './ui'

afterEach(cleanup)

describe('safe curriculum rendering', () => {
  it('shows text and HTTPS links while dropping active HTML and remote images', () => {
    const text = 'Read [source](https://example.org/docs) and [bad](javascript:confirm%281%29).\n\n' +
      '<iframe src="https://example.org"></iframe>\n\n![remote](https://example.org/a.png)'
    const { container } = render(<SafeMarkdown text={text} />)
    expect(screen.getByRole('link', { name: 'source' }).getAttribute('href')).toBe('https://example.org/docs')
    expect(screen.getByText('bad').getAttribute('href')).toBe('')
    expect(container.querySelector('iframe, img, script')).toBeNull()
  })

  it('renders planned state visibly in Ukrainian', () => {
    render(<StateBadge entry={{ id: 'W02', title: 'W02', availability: 'planned', prerequisites: [], estimateMinutes: 10 }} locale="uk" />)
    expect(screen.getByText('Заплановано')).toBeDefined()
  })
})
