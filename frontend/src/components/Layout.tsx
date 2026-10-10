import { useState } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import { useProject } from '../state/ProjectContext'
import { Badge, Button } from './ui'

const NAV = [
  { to: '/', label: 'Overview', icon: 'M4 6h16M4 12h16M4 18h10', end: true },
  { to: '/assistant', label: 'AI Commerce Assistant', icon: 'M12 3l2.2 5.3L20 10l-5.8 1.7L12 17l-2.2-5.3L4 10l5.8-1.7z' },
  { to: '/products', label: 'Product Hunter', icon: 'M11 19a8 8 0 100-16 8 8 0 000 16zm10 2l-4.35-4.35' },
  { to: '/store', label: 'Store Architect', icon: 'M4 9l1-4h14l1 4M4 9v10h16V9M4 9h16M9 19v-6h6v6' },
  { to: '/marketing', label: 'Marketing Studio', icon: 'M3 11l18-6v14L3 13v-2zm0 0v3a2 2 0 002 2h1' },
  { to: '/analytics', label: 'Business Analytics', icon: 'M4 19V5m0 14h16M8 15V9m4 6V7m4 8v-4' },
  { to: '/history', label: 'Project History', icon: 'M12 8v4l3 2m6-2a9 9 0 11-18 0 9 9 0 0118 0z' },
  { to: '/settings', label: 'Settings & Integrations', icon: 'M10.3 4.3l.4 1.6 1.5.6 1.5-.9 1.4 1.4-.9 1.5.6 1.5 1.6.4v2l-1.6.4-.6 1.5.9 1.5-1.4 1.4-1.5-.9-1.5.6-.4 1.6h-2l-.4-1.6-1.5-.6-1.5.9-1.4-1.4.9-1.5-.6-1.5L2.3 13v-2l1.6-.4.6-1.5-.9-1.5 1.4-1.4 1.5.9 1.5-.6.4-1.6h2z' },
]

function Logo() {
  return (
    <div className="flex items-center gap-2.5 px-5 py-5">
      <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-brand">
        <svg viewBox="0 0 32 32" className="h-5 w-5" fill="none">
          <path d="M7 21l4.5-9 3.5 6 3.5-8L23 21" stroke="#2ECC71" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </span>
      <span>
        <span className="block font-display text-[17px] font-semibold leading-none text-ink">CommercePilot</span>
        <span className="text-[11px] font-semibold uppercase tracking-[0.2em] text-accent-dark">AI workspace</span>
      </span>
    </div>
  )
}

export function Sidebar({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { project } = useProject()
  const loc = useLocation()

  return (
    <>
      {/* mobile scrim */}
      <AnimatePresence>
        {open && (
          <motion.div
            className="fixed inset-0 z-30 bg-ink/30 lg:hidden"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
          />
        )}
      </AnimatePresence>

      <aside
        className={`fixed inset-y-0 left-0 z-40 w-[248px] border-r border-line bg-paper transition-transform lg:translate-x-0 ${
          open ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="flex h-full flex-col">
          <Logo />
          <nav className="flex-1 space-y-0.5 overflow-y-auto px-3 pb-4">
            {NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                onClick={onClose}
                className={({ isActive }) =>
                  `group flex items-center gap-3 rounded-lg px-3 py-2 text-[13.5px] font-medium transition-colors ${
                    isActive
                      ? 'bg-brand text-white shadow-soft'
                      : 'text-muted hover:bg-mist-2 hover:text-ink'
                  }`
                }
              >
                {({ isActive }: { isActive: boolean }) => (
                  <>
                    <svg viewBox="0 0 24 24" className={`h-4 w-4 shrink-0 ${isActive ? 'text-accent' : 'text-current'}`} fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                      <path d={item.icon} />
                    </svg>
                    {item.label}
                  </>
                )}
              </NavLink>
            ))}
          </nav>
          <div className="border-t border-line p-4">
            <div className="rounded-lg bg-mist p-3 text-xs text-muted">
              <p className="font-semibold text-ink">Prototype mode</p>
              <p className="mt-1 leading-relaxed">
                Demo/sample data is labelled throughout. Meta &amp; Shopify: not connected.
              </p>
              {project && (
                <div className="mt-2 flex flex-wrap gap-1">
                  {project.selected_product && <Badge tone="green">Product</Badge>}
                  {project.store_spec && <Badge tone="green">Store</Badge>}
                  {project.campaign && <Badge tone="green">Campaign</Badge>}
                  {project.analysis && <Badge tone="green">Analysis</Badge>}
                </div>
              )}
            </div>
          </div>
        </div>
      </aside>
    </>
  )
}

export function TopBar({ onMenu }: { onMenu: () => void }) {
  const { projects, project, selectProject, createProject, busy, run } = useProject()
  const [creating, setCreating] = useState(false)
  const loc = useLocation()

  const startExample = async () => {
    setCreating(true)
    await run('create-example', async () => {
      const p = await createProject({ example: true })
      await selectProject(p.id)
    })
    setCreating(false)
  }

  const title = NAV.find((n) => (n.end ? loc.pathname === n.to : loc.pathname.startsWith(n.to)))?.label ?? 'Overview'

  return (
    <header className="sticky top-0 z-20 border-b border-line bg-paper/90 backdrop-blur">
      <div className="flex h-16 items-center gap-3 px-4 lg:px-7">
        <button onClick={onMenu} className="rounded-lg p-2 text-muted hover:bg-mist-2 lg:hidden" aria-label="Open menu">
          <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 6h16M4 12h16M4 18h16" strokeLinecap="round" /></svg>
        </button>

        <div className="hidden min-w-0 sm:block">
          <p className="truncate text-sm font-semibold text-ink">{title}</p>
        </div>

        <div className="ml-auto flex items-center gap-2.5">
          {/* Project selector */}
          <div className="flex items-center gap-2">
            <span className="hidden text-xs font-semibold uppercase tracking-wide text-muted md:inline">Project</span>
            <select
              className="max-w-[220px] rounded-lg border border-line bg-paper px-3 py-1.5 text-sm text-ink focus:border-brand/40 focus:outline-none"
              value={project?.id ?? ''}
              onChange={(e) => e.target.value && selectProject(e.target.value)}
            >
              <option value="" disabled>
                {projects.length ? 'Select project…' : 'No projects yet'}
              </option>
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                  {p.is_example ? ' (example)' : ''}
                </option>
              ))}
            </select>
          </div>

          <Button size="sm" variant="accent" busy={creating} onClick={startExample}>
            Example Project
          </Button>

          <div className="hidden items-center gap-1.5 rounded-full border border-line bg-mist px-3 py-1.5 md:flex">
            <span className="dot-pulse h-1.5 w-1.5 rounded-full bg-accent" />
            <span className="text-xs font-medium text-muted">Demo data labelled</span>
          </div>
        </div>
      </div>
    </header>
  )
}
