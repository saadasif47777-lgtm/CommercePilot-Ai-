// Application root: routing, page transitions and the persistent shell.
//
// The sidebar/top bar stay mounted while only the page body animates, which
// makes navigation feel instant and keeps the project switcher stable.

import { Component, lazy, Suspense, useEffect, useState, type ReactNode } from 'react'
import { request } from './services/api'
import { BrowserRouter, Route, Routes, useLocation } from 'react-router-dom'
import { motion, MotionConfig } from 'framer-motion'
import { ProjectProvider, useProject } from './state/ProjectContext'
import { Sidebar, TopBar } from './components/Layout'
const OverviewPage = lazy(() => import('./pages/Overview').then(m => ({ default: m.OverviewPage })))
const AssistantPage = lazy(() => import('./pages/AssistantPage').then(m => ({ default: m.AssistantPage })))
const ProductHunterPage = lazy(() => import('./pages/ProductHunterPage').then(m => ({ default: m.ProductHunterPage })))
const StoreArchitectPage = lazy(() => import('./pages/StoreArchitectPage').then(m => ({ default: m.StoreArchitectPage })))
const MarketingPage = lazy(() => import('./pages/MarketingPage').then(m => ({ default: m.MarketingPage })))
const AnalyticsPage = lazy(() => import('./pages/AnalyticsPage').then(m => ({ default: m.AnalyticsPage })))
const HistoryPage = lazy(() => import('./pages/HistoryPage').then(m => ({ default: m.HistoryPage })))
const SettingsPage = lazy(() => import('./pages/SettingsPage').then(m => ({ default: m.SettingsPage })))
const BusinessPage = lazy(() => import('./pages/BusinessPage').then(m => ({ default: m.BusinessPage })))
const CustomerSupportPage = lazy(() => import('./pages/CustomerSupportPage').then(m => ({ default: m.CustomerSupportPage })))

// Shell = sidebar + header + animated page area + footer.
function Shell() {
  const [menuOpen, setMenuOpen] = useState(false)
  const location = useLocation()
  const { project } = useProject()

  return (
    <div className="min-h-screen bg-mist">
      <Sidebar open={menuOpen} onClose={() => setMenuOpen(false)} />
      <div data-workspace-content className="lg:pl-[248px]">
        <TopBar onMenu={() => setMenuOpen(true)} />
        <main className="px-4 py-6 lg:px-7 lg:py-7">
          {/* Keying the motion wrapper by pathname replays the fade/slide
              transition whenever the route changes. */}
            <motion.div
              key={location.pathname + ':' + (project?.id ?? '')}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.22, ease: 'easeOut' }}
            >
              {/* One route per workspace step; unknown URLs fall back to the
                  Overview instead of showing a blank screen. */}
              <RouteBoundary key={location.pathname}><Suspense fallback={<p role="status">Opening your workspace…</p>}><Routes location={location}>
                <Route path="/" element={<OverviewPage />} />
                <Route path="/assistant" element={<AssistantPage />} />
                <Route path="/products" element={<ProductHunterPage />} />
                <Route path="/store" element={<StoreArchitectPage />} />
                <Route path="/marketing" element={<MarketingPage />} />
                <Route path="/analytics" element={<AnalyticsPage />} />
                <Route path="/history" element={<HistoryPage />} />
                <Route path="/settings" element={<SettingsPage />} />
                <Route path="/business" element={<BusinessPage />} />
                <Route path="/support" element={<CustomerSupportPage />} />
                <Route path="*" element={<OverviewPage />} />
              </Routes></Suspense></RouteBoundary>
            </motion.div>
        </main>
        <footer className="px-6 pb-6 pt-2 text-center text-[11px] text-muted">
          CommercePilot AI · Your business, products and campaign planning workspace.
        </footer>
      </div>
    </div>
  )
}

// ProjectProvider wraps the shell so every page shares the open project.
export default function App() {
  return (
    <MotionConfig reducedMotion="user"><BrowserRouter>
      <SignIn><ProjectProvider><Shell /></ProjectProvider></SignIn>
    </BrowserRouter></MotionConfig>
  )
}

class RouteBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false }
  static getDerivedStateFromError() { return { failed: true } }
  render() { return this.state.failed ? <div role="alert">This page could not load. <button onClick={() => window.location.reload()}>Try again</button></div> : this.props.children }
}

function SignIn({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<{ required: boolean; authenticated: boolean; setup_error?: string } | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => { request<{ required: boolean; authenticated: boolean; setup_error?: string }>('/api/auth/session').then(setSession).catch((error: unknown) => setError(error instanceof Error ? error.message : 'The workspace service is unavailable. Please try again.')) }, [])
  if (error) return <main className="mx-auto max-w-lg p-10"><h1>We couldn't open your workspace</h1><p role="alert" className="my-4 text-muted">{error}</p><button className="rounded-xl bg-brand px-5 py-3 text-white" onClick={() => window.location.reload()}>Try again</button></main>
  if (!session) return <p role="status" className="p-10">Opening CommercePilot…</p>
  if (session.setup_error) return <main className="mx-auto max-w-lg px-6 py-24"><p className="text-brand">CommercePilot</p><h1 className="mt-4 text-3xl">Your workspace needs one more setup step</h1><p role="alert" className="my-6 text-muted">{session.setup_error}</p><p className="mb-6 text-muted">The site owner needs to update this deployment’s environment settings, then redeploy. Your saved workspace stays protected.</p><button className="rounded-xl bg-brand px-5 py-3 text-white" onClick={() => window.location.reload()}>Check again</button></main>
  if (session.required && !session.authenticated) return <main className="mx-auto max-w-lg px-6 py-24"><p className="text-brand">CommercePilot</p><h1 className="mt-4 text-4xl">A little clarity for your next big idea.</h1><p className="my-6 text-muted">Your products, plans and store — together in your private workspace.</p><a className="inline-block rounded-xl bg-brand px-6 py-3 text-white" href="/api/auth/login">Continue with Google</a></main>
  return <>{session.required && <button className="fixed bottom-3 right-3 z-40 rounded-lg border border-line bg-paper px-3 py-2 text-sm" onClick={async () => { await request('/api/auth/logout', { method: 'POST' }); localStorage.removeItem('commercepilot.currentProject'); window.location.reload() }}>Sign out</button>}{children}</>
}
