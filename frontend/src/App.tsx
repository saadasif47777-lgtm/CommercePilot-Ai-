// Application root: routing, page transitions and the persistent shell.
//
// The sidebar/top bar stay mounted while only the page body animates, which
// makes navigation feel instant and keeps the project switcher stable.

import { useState } from 'react'
import { BrowserRouter, Route, Routes, useLocation } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import { ProjectProvider, useProject } from './state/ProjectContext'
import { Sidebar, TopBar } from './components/Layout'
import { OverviewPage } from './pages/Overview'
import { AssistantPage } from './pages/AssistantPage'
import { ProductHunterPage } from './pages/ProductHunterPage'
import { StoreArchitectPage } from './pages/StoreArchitectPage'
import { MarketingPage } from './pages/MarketingPage'
import { AnalyticsPage } from './pages/AnalyticsPage'
import { HistoryPage } from './pages/HistoryPage'
import { SettingsPage } from './pages/SettingsPage'
import { BusinessPage } from './pages/BusinessPage'
import { AuthGate } from './components/AuthGate'

// Shell = sidebar + header + animated page area + footer.
function Shell() {
  const [menuOpen, setMenuOpen] = useState(false)
  const location = useLocation()
  const { project } = useProject()

  return (
    <div className="min-h-screen bg-mist">
      <Sidebar open={menuOpen} onClose={() => setMenuOpen(false)} />
      <div className="lg:pl-[248px]">
        <TopBar onMenu={() => setMenuOpen(true)} />
        <main className="px-4 py-6 lg:px-7 lg:py-7">
          {/* Keying the motion wrapper by pathname replays the fade/slide
              transition whenever the route changes. */}
          <AnimatePresence mode="wait">
            <motion.div
              key={location.pathname + ':' + (project?.id ?? '')}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              transition={{ duration: 0.22, ease: 'easeOut' }}
            >
              {/* One route per workspace step; unknown URLs fall back to the
                  Overview instead of showing a blank screen. */}
              <Routes location={location}>
                <Route path="/" element={<OverviewPage />} />
                <Route path="/assistant" element={<AssistantPage />} />
                <Route path="/products" element={<ProductHunterPage />} />
                <Route path="/store" element={<StoreArchitectPage />} />
                <Route path="/marketing" element={<MarketingPage />} />
                <Route path="/analytics" element={<AnalyticsPage />} />
                <Route path="/history" element={<HistoryPage />} />
                <Route path="/settings" element={<SettingsPage />} />
                <Route path="/business" element={<BusinessPage />} />
                <Route path="*" element={<OverviewPage />} />
              </Routes>
            </motion.div>
          </AnimatePresence>
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
    <BrowserRouter>
      <AuthGate><ProjectProvider><Shell /></ProjectProvider></AuthGate>
    </BrowserRouter>
  )
}
