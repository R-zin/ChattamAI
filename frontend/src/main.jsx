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
import Settings from './pages/Settings.jsx'
import Login from './pages/Login.jsx'
import Register from './pages/Register.jsx'
import VisualWorkbench from './pages/VisualWorkbench.jsx'
import { isAuthed } from './data.js'

// Unauthenticated visits to any protected page redirect to /login; an expired
// token redirects via the data layer's 401 handling.
function RequireAuth({ children }) {
  if (!isAuthed()) return <Navigate to="/login" replace />
  return children
}

export default function App() {
  return (
    <BrowserRouter>
      <ToastHost />
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route
          path="/*"
          element={
            <RequireAuth>
              <AppShell>
                <Routes>
                  <Route path="/" element={<Dashboard />} />
                  <Route path="/new-check" element={<NewCheck />} />
                  <Route path="/workbench" element={<VisualWorkbench />} />
                  <Route path="/analysis" element={<Analysis />} />
                  <Route path="/results" element={<Results />} />
                  <Route path="/results/insufficient" element={<Insufficient />} />
                  <Route path="/results/:id" element={<Results />} />
                  <Route path="/kbr" element={<Knowledge />} />
                  <Route path="/reports" element={<Reports />} />
                  <Route path="/settings" element={<Settings />} />
                  <Route path="*" element={<Navigate to="/" replace />} />
                </Routes>
              </AppShell>
            </RequireAuth>
          }
        />
      </Routes>
    </BrowserRouter>
  )
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)
