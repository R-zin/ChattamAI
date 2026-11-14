import { describe, it, expect } from 'vitest'
import React from 'react'
import { render, screen, fireEvent, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import AppShell, { Header } from '../components/AppShell.jsx'
import Pill from '../components/Pill.jsx'
import AuthLayout from '../components/AuthLayout.jsx'

const NAV = [
  ['Dashboard', '/'],
  ['PDF Visual Workbench', '/workbench'],
  ['New Compliance Check', '/new-check'],
  ['Projects', '/projects'],
  ['Reports', '/reports'],
  ['KBR Knowledge Base', '/kbr'],
  ['Activity', '/activity'],
  ['Settings', '/settings'],
]

const renderShell = (path = '/') =>
  render(
    <MemoryRouter initialEntries={[path]}>
      <AppShell>
        <p>page body</p>
      </AppShell>
    </MemoryRouter>
  )

describe('AppShell', () => {
  it('keeps every navigation destination', () => {
    renderShell()
    const nav = screen.getByRole('navigation')
    for (const [label, href] of NAV) {
      expect(within(nav).getByRole('link', { name: label })).toHaveAttribute('href', href)
    }
  })

  it.each(NAV)('marks %s as the current page on %s', (label, href) => {
    renderShell(href)
    const links = within(screen.getByRole('navigation')).getAllByRole('link')
    const current = links.filter((l) => l.querySelector('[aria-current="page"]'))
    expect(current).toHaveLength(1)
    expect(current[0]).toHaveTextContent(label)
  })

  it('renders content in a main landmark with a skip link', () => {
    renderShell()
    expect(screen.getByRole('main')).toHaveTextContent('page body')
    expect(screen.getByRole('link', { name: /skip to content/i })).toHaveAttribute('href', '#main-content')
  })

  it('exposes the theme switch and the engine status', () => {
    renderShell()
    expect(screen.getAllByRole('button', { name: /switch to (dark|light) theme/i }).length).toBeGreaterThan(0)
    expect(screen.getByText('ONLINE')).toBeInTheDocument()
  })

  it('opens and closes the mobile menu, including with Escape', () => {
    renderShell()
    const toggle = screen.getByRole('button', { name: /open navigation menu/i })
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    fireEvent.click(toggle)
    expect(screen.getByRole('button', { name: /close navigation menu/i })).toHaveAttribute('aria-expanded', 'true')
    fireEvent.keyDown(window, { key: 'Escape' })
    expect(screen.getByRole('button', { name: /open navigation menu/i })).toHaveAttribute('aria-expanded', 'false')
  })
})

describe('Header', () => {
  it('renders eyebrow, a single h1 title, subtitle and action', () => {
    render(
      <MemoryRouter>
        <Header eyebrow="EYEBROW" title="Page Title" subtitle="A line" action={<button>Go</button>} backLink="/reports" />
      </MemoryRouter>
    )
    expect(screen.getByRole('heading', { level: 1, name: 'Page Title' })).toBeInTheDocument()
    expect(screen.getByText('EYEBROW')).toBeInTheDocument()
    expect(screen.getByText('A line')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Go' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /return to previous page/i })).toHaveAttribute('href', '/reports')
  })
})

describe('Pill', () => {
  it('shows a text label with a decorative glyph, never colour alone', () => {
    const { container } = render(<Pill kind="pill-danger">Violation</Pill>)
    expect(screen.getByText('Violation')).toBeInTheDocument()
    const chip = container.querySelector('.status-pill')
    expect(chip).toHaveClass('pill-danger')
    expect(chip.querySelector('[aria-hidden="true"]')).not.toBeNull()
  })

  it('can omit the glyph', () => {
    const { container } = render(<Pill dot={false}>Plain</Pill>)
    expect(container.querySelector('[aria-hidden="true"]')).toBeNull()
  })
})

describe('AuthLayout', () => {
  it('puts the title in the only h1 and renders its children', () => {
    render(
      <AuthLayout title="Sign In" subtitle="sub">
        <button>Submit</button>
      </AuthLayout>
    )
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1)
    expect(screen.getByRole('heading', { level: 1, name: 'Sign In' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Submit' })).toBeInTheDocument()
    expect(screen.getByRole('main')).toBeInTheDocument()
  })
})
