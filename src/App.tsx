// src/App.tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/dashboard/Layout'
import DashboardPage from './pages/DashboardPage'
import TendersPage from './pages/TendersPage'
import MorePortalsPage from './pages/MorePortalsPage'
import Login from './pages/Login'
import { useAuth } from './hooks/useAuth'
import HospitalPage from './pages/HospitalPage'
import ArchivePage from './pages/ArchivePage'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 60_000, retry: 2, refetchOnWindowFocus: false },
  },
})

function AuthGate() {
  const { user, loading } = useAuth()

  if (loading) return <div style={{ background: '#020810', height: '100vh' }} />
  if (!user) return <Login />

  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/tenders" element={<TendersPage />} />
        <Route path="/more-portals" element={<MorePortalsPage />} />
        <Route path="/hospitals" element={<HospitalPage />} />
        <Route path="/archive" element={<ArchivePage />} />
      </Route>
    </Routes>
  )
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthGate />
      </BrowserRouter>
    </QueryClientProvider>
  )
}