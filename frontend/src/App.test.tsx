import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { App } from './App.tsx'

describe('App', () => {
  it('shows the project name as the page heading', () => {
    render(<App />)
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('pitwall')
  })

  it('credits OpenF1 with a link', () => {
    render(<App />)
    expect(screen.getByRole('link', { name: 'OpenF1' })).toHaveAttribute(
      'href',
      'https://openf1.org',
    )
  })
})
