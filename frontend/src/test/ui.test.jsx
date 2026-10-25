import { describe, it, expect, vi } from 'vitest'
import React from 'react'
import { render, screen, fireEvent } from '@testing-library/react'
import {
  Button,
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  CardFooter,
  Skeleton,
  SkeletonCard,
  SkeletonTable,
  Modal,
  EmptyState,
  Slider,
} from '../components/ui/index.js'

describe('UI Primitives', () => {
  describe('Button', () => {
    it('renders text and handles clicks', () => {
      const handleClick = vi.fn()
      render(<Button onClick={handleClick}>Run Audit</Button>)
      const btn = screen.getByRole('button', { name: /run audit/i })
      expect(btn).toBeInTheDocument()
      fireEvent.click(btn)
      expect(handleClick).toHaveBeenCalledTimes(1)
    })

    it('displays loading state and disables button with aria-busy', () => {
      render(<Button loading>Auditing</Button>)
      const btn = screen.getByRole('button')
      expect(btn).toBeDisabled()
      expect(btn).toHaveAttribute('aria-busy', 'true')
    })

    it('applies variant classes correctly', () => {
      const { rerender } = render(<Button variant="primary">Primary</Button>)
      expect(screen.getByRole('button')).toHaveClass('bg-white text-black')

      rerender(<Button variant="danger">Danger</Button>)
      expect(screen.getByRole('button')).toHaveClass('text-[#fca5a5]')
    })
  })

  describe('Card', () => {
    it('renders composable card layout', () => {
      render(
        <Card data-testid="test-card">
          <CardHeader>
            <CardTitle>Schedule Statement</CardTitle>
          </CardHeader>
          <CardContent>Body details</CardContent>
          <CardFooter>Footer note</CardFooter>
        </Card>
      )
      expect(screen.getByTestId('test-card')).toBeInTheDocument()
      expect(screen.getByText('Schedule Statement')).toBeInTheDocument()
      expect(screen.getByText('Body details')).toBeInTheDocument()
      expect(screen.getByText('Footer note')).toBeInTheDocument()
    })
  })

  describe('Skeleton', () => {
    it('renders skeleton loaders with accessible attributes', () => {
      render(<SkeletonCard rows={2} />)
      const loader = screen.getByRole('status', { name: /loading panel/i })
      expect(loader).toHaveAttribute('aria-busy', 'true')

      render(<SkeletonTable rows={3} cols={4} />)
      const tableLoader = screen.getByRole('status', { name: /loading table/i })
      expect(tableLoader).toHaveAttribute('aria-busy', 'true')
    })
  })

  describe('Modal', () => {
    it('renders when open and responds to Escape key', () => {
      const handleClose = vi.fn()
      render(
        <Modal isOpen={true} onClose={handleClose} title="K-Smart Export">
          <div>Export content payload</div>
        </Modal>
      )

      expect(screen.getByRole('dialog', { name: /k-smart export/i })).toBeInTheDocument()
      expect(screen.getByText('Export content payload')).toBeInTheDocument()

      fireEvent.keyDown(window, { key: 'Escape' })
      expect(handleClose).toHaveBeenCalledTimes(1)
    })

    it('triggers onClose when clicking backdrop', () => {
      const handleClose = vi.fn()
      render(
        <Modal isOpen={true} onClose={handleClose} title="Title">
          <div>Content</div>
        </Modal>
      )
      const backdrop = screen.getByTestId('modal-backdrop')
      fireEvent.click(backdrop)
      expect(handleClose).toHaveBeenCalledTimes(1)
    })

    it('does not render when isOpen is false', () => {
      render(
        <Modal isOpen={false} title="Title">
          <div>Content</div>
        </Modal>
      )
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    })
  })

  describe('EmptyState', () => {
    it('renders technical empty state and triggers action', () => {
      const handleAction = vi.fn()
      render(
        <EmptyState
          title="No Active Audits"
          description="Submit a blueprint to begin"
          actionLabel="Start Audit"
          onAction={handleAction}
        />
      )
      expect(screen.getByRole('status')).toBeInTheDocument()
      expect(screen.getByText('No Active Audits')).toBeInTheDocument()

      const btn = screen.getByRole('button', { name: /start audit/i })
      fireEvent.click(btn)
      expect(handleAction).toHaveBeenCalledTimes(1)
    })
  })

  describe('Slider', () => {
    it('renders range slider with accessible values', () => {
      const handleChange = vi.fn()
      render(
        <Slider
          label="Front Setback"
          value={3.5}
          min={1.0}
          max={6.0}
          step={0.1}
          unit="m"
          onChange={handleChange}
        />
      )
      const slider = screen.getByRole('slider', { name: /front setback/i })
      expect(slider).toHaveAttribute('aria-valuenow', '3.5')
      expect(slider).toHaveAttribute('aria-valuemin', '1')
      expect(slider).toHaveAttribute('aria-valuemax', '6')

      fireEvent.change(slider, { target: { value: '4.2' } })
      expect(handleChange).toHaveBeenCalledWith(4.2)
    })
  })
})
