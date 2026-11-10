import { describe, it, expect, vi, beforeEach } from 'vitest'
import React from 'react'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import VisualWorkbench from '../pages/VisualWorkbench.jsx'
import Reports from '../pages/Reports.jsx'
import Projects from '../pages/Projects.jsx'
import Dashboard from '../pages/Dashboard.jsx'
import Login from '../pages/Login.jsx'

const routerFuture = { v7_startTransition: true, v7_relativeSplatPath: true }

describe('Application Pages', () => {
  describe('Login', () => {
    it('renders login form and Google OAuth button', () => {
      render(
        <BrowserRouter future={routerFuture}>
          <Login />
        </BrowserRouter>
      )
      expect(screen.getByRole('button', { name: /sign in with google/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /sign in with password/i })).toBeInTheDocument()
      expect(screen.getByPlaceholderText(/admin@chattamai.com/i)).toBeInTheDocument()
    })

    it('renders accessible labels linked to input fields with htmlFor and id', () => {
      render(
        <BrowserRouter future={routerFuture}>
          <Login />
        </BrowserRouter>
      )
      const emailLabel = screen.getByText('Email')
      expect(emailLabel).toHaveAttribute('for', 'field-email')
      const emailInput = screen.getByPlaceholderText(/admin@chattamai.com/i)
      expect(emailInput).toHaveAttribute('id', 'field-email')
    })
  })
  describe('VisualWorkbench', () => {
    it('renders header, drop zone, and empty state initially', () => {
      render(
        <BrowserRouter future={routerFuture}>
          <VisualWorkbench />
        </BrowserRouter>
      )
      expect(screen.getByText('PDF Visual Workbench')).toBeInTheDocument()
      expect(
        screen.getByRole('button', { name: /upload architectural drawing pdf/i })
      ).toBeInTheDocument()
      expect(screen.getByText(/awaiting architectural blueprint/i)).toBeInTheDocument()
    })

    it('validates non-PDF file selection and displays error', async () => {
      render(
        <BrowserRouter future={routerFuture}>
          <VisualWorkbench />
        </BrowserRouter>
      )
      const input = screen.getByLabelText(/upload architectural drawing pdf/i).querySelector('input[type="file"]')
      const invalidFile = new File(['hello'], 'document.docx', { type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' })

      fireEvent.change(input, { target: { files: [invalidFile] } })

      expect(screen.getByText(/please upload a valid architectural drawing pdf/i)).toBeInTheDocument()
    })

    it('loads sample file when clicking sample action button and enables audit', async () => {
      render(
        <BrowserRouter future={routerFuture}>
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
        <BrowserRouter future={routerFuture}>
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
        <BrowserRouter future={routerFuture}>
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
        <BrowserRouter future={routerFuture}>
          <Dashboard />
        </BrowserRouter>
      )
      expect(screen.getByText('TOTAL ASSESSMENTS')).toBeInTheDocument()
      expect(screen.getByText('COMPLIANCE RATE')).toBeInTheDocument()
      expect(screen.getByText('Recent Plan Assessments')).toBeInTheDocument()
    })
  })
})
