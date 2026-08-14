import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import './index.css'
import AppShell from './components/AppShell.jsx'
import { ToastHost } from './components/Toast.jsx'
import Dashboard from './pages/Dashboard.jsx'
import NewCheck from './pages/NewCheck.jsx'
import Analysis from './pages/Analysis.jsx'
import Results from './pages/Results.jsx'
import Insufficient from './pages/Insufficient.jsx'
import Knowledge from './pages/Knowledge.jsx'
import Reports from './pages/Reports.jsx'
import Projects from './pages/Projects.jsx'
import Activity from './pages/Activity.jsx'
import Settings from './pages/Settings.jsx'

export default function App() {
  return (
    <BrowserRouter>
      <ToastHost />
      <AppShell>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/new-check" element={<NewCheck />} />
          <Route path="/analysis" element={<Analysis />} />
          <Route path="/results/demo" element={<Results />} />
          <Route path="/results/insufficient" element={<Insufficient />} />
          <Route path="/kbr" element={<Knowledge />} />
          <Route path="/reports" element={<Reports />} />
          <Route path="/projects" element={<Projects />} />
          <Route path="/activity" element={<Activity />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AppShell>
    </BrowserRouter>
  )
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)
