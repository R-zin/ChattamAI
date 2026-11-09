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
import VerificationAuditBadge from '../components/VerificationAuditBadge.jsx'

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

  describe('VerificationAuditBadge', () => {
    it('returns null when verification prop is absent', () => {
      const { container } = render(<VerificationAuditBadge verification={null} />)
      expect(container.firstChild).toBeNull()
    })

    it('renders confirmed badge with model name and confidence', () => {
      const payload = {
        status: 'confirmed',
        verified_by_model: 'DeepSeek-R1',
        confidence_score: 0.98,
        cross_check_notes: 'All candidate violations verified against KBR 2019.',
        discrepancies: [],
      }
      render(<VerificationAuditBadge verification={payload} />)
      expect(
        screen.getByText(/double-checked & confirmed by deepseek-r1/i)
      ).toBeInTheDocument()
      expect(screen.getByText('98%')).toBeInTheDocument()
    })

    it('renders reconciled discrepancies badge with count', () => {
      const payload = {
        status: 'adjusted',
        verified_by_model: 'Qwen-2.5-32B',
        confidence_score: 0.94,
        discrepancies: [
          {
            rule_reference: 'Rule 27',
            type: 'false_positive',
            description: 'Rear setback complies with small-plot concession.',
            primary_finding: 'Rear setback violation',
            verifier_finding: 'Complies under Rule 27',
          },
        ],
      }
      render(<VerificationAuditBadge verification={payload} />)
      expect(
        screen.getByText(/discrepancies reconciled \(1 resolved\)/i)
      ).toBeInTheDocument()
    })

    it('renders skipped and offline error badges', () => {
      const { rerender } = render(
        <VerificationAuditBadge verification={{ status: 'skipped' }} />
      )
      expect(screen.getByText(/single model audited/i)).toBeInTheDocument()

      rerender(
        <VerificationAuditBadge
          verification={{ status: 'error', error: 'Endpoint timeout' }}
        />
      )
      expect(
        screen.getByText(/verifier offline \(using primary findings\)/i)
      ).toBeInTheDocument()
    })

    it('expands and collapses details drawer when clicked', () => {
      const payload = {
        status: 'flagged_discrepancy',
        verified_by_model: 'Nemotron-4',
        confidence_score: 0.92,
        cross_check_notes: 'Examiner cross-check indicates small-plot concession applicability.',
        primary_violations_count: 2,
        final_violations_count: 1,
        discrepancies: [
          {
            rule_reference: 'Rule 27(1)',
            type: 'false_positive',
            description: 'Concession under Rule 27 exempts rear setback deficit.',
            primary_finding: 'Deficit of 0.5m',
            verifier_finding: 'Exonerated under Rule 27',
          },
        ],
      }
      render(<VerificationAuditBadge verification={payload} />)

      // Initially collapsed
      expect(screen.queryByTestId('verification-details-card')).not.toBeInTheDocument()

      // Click badge button to expand
      const badgeBtn = screen.getByRole('button')
      fireEvent.click(badgeBtn)

      // Details card rendered
      expect(screen.getByTestId('verification-details-card')).toBeInTheDocument()
      expect(
        screen.getByText(/examiner cross-check indicates small-plot concession/i)
      ).toBeInTheDocument()
      expect(screen.getByText('FALSE POSITIVE')).toBeInTheDocument()
      expect(screen.getByText('Rule 27(1)')).toBeInTheDocument()
      expect(screen.getByText('Deficit of 0.5m')).toBeInTheDocument()
      expect(screen.getByText('Exonerated under Rule 27')).toBeInTheDocument()

      // Click again to collapse
      fireEvent.click(badgeBtn)
      expect(screen.queryByTestId('verification-details-card')).not.toBeInTheDocument()
    })
  })
})
