import { describe, it, expect, vi, beforeEach } from 'vitest'
import React from 'react'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import VisualWorkbench from '../pages/VisualWorkbench.jsx'
import Reports from '../pages/Reports.jsx'
import Projects from '../pages/Projects.jsx'
import Dashboard from '../pages/Dashboard.jsx'
import Login from '../pages/Login.jsx'

describe('Application Pages', () => {
  describe('Login', () => {
    it('renders login form and Google OAuth button', () => {
      render(
        <BrowserRouter>
          <Login />
        </BrowserRouter>
      )
      expect(screen.getByRole('button', { name: /sign in with google/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /sign in with password/i })).toBeInTheDocument()
      expect(screen.getByPlaceholderText(/admin@chattamai.com/i)).toBeInTheDocument()
    })
  })
  describe('VisualWorkbench', () => {
    it('renders header, drop zone, and empty state initially', () => {
      render(
        <BrowserRouter>
          <VisualWorkbench />
        </BrowserRouter>
      )
      expect(screen.getByText('PDF Visual Workbench')).toBeInTheDocument()
      expect(
        screen.getByRole('button', { name: /upload architectural drawing pdf/i })
      ).toBeInTheDocument()
      expect(screen.getByText(/awaiting architectural blueprint/i)).toBeInTheDocument()
    })

    it('loads sample file when clicking sample action button and enables audit', async () => {
      render(
        <BrowserRouter>
          <VisualWorkbench />
        </BrowserRouter>
      )
      const sampleBtn = screen.getByRole('button', {
        name: /select sample pdf drawing/i,
      })
      fireEvent.click(sampleBtn)

      expect(screen.getByText(/Kakkanad_Residential_Plan_v2.pdf/i)).toBeInTheDocument()
      const auditBtn = screen.getByRole('button', { name: /run deep audit/i })
      expect(auditBtn).toBeEnabled()

      fireEvent.click(auditBtn)

      await waitFor(
        () => {
          expect(screen.getByText(/Certified Area Schedule Data/i)).toBeInTheDocument()
        },
        { timeout: 3000 }
      )
      expect(screen.getByText(/Interactive Parameter Simulator/i)).toBeInTheDocument()
    })
  })

  describe('Reports', () => {
    it('renders reports table after loading', async () => {
      render(
        <BrowserRouter>
          <Reports />
        </BrowserRouter>
      )
      await waitFor(() => {
        expect(screen.getByText(/Assessment Archive & Review Records/i)).toBeInTheDocument()
      })
      expect(screen.getByRole('button', { name: /export latest pdf/i })).toBeInTheDocument()
    })
  })

  describe('Projects', () => {
    it('filters projects by category tab', () => {
      render(
        <BrowserRouter>
          <Projects />
        </BrowserRouter>
      )
      expect(screen.getByText(/Residential Building — Kakkanad/i)).toBeInTheDocument()

      const violationTab = screen.getByRole('tab', { name: /violation/i })
      fireEvent.click(violationTab)

      // Commercial Complex — Kochi has 1 · VIOLATION
      expect(screen.getByText(/Commercial Complex — Kochi/i)).toBeInTheDocument()
    })
  })

  describe('Dashboard', () => {
    it('renders metric cards and recent assessments', () => {
      render(
        <BrowserRouter>
          <Dashboard />
        </BrowserRouter>
      )
      expect(screen.getByText('TOTAL ASSESSMENTS')).toBeInTheDocument()
      expect(screen.getByText('COMPLIANCE RATE')).toBeInTheDocument()
      expect(screen.getByText('Recent Plan Assessments')).toBeInTheDocument()
    })
  })
})
