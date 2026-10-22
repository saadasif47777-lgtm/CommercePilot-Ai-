// Global workspace state.
//
// One project is "open" at a time; every page reads it from here instead of
// fetching on its own, so selecting a product on Product Hunter is immediately
// visible on the Store and Analytics pages. The last opened project id is kept
// in localStorage so a page refresh restores the same workspace.

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { api, errorText } from '../services/api'
import type { BusinessBrief, IntegrationStatus, Project, ProjectSummary } from '../types'

interface ProjectContextValue {
  projects: ProjectSummary[]
  project: Project | null
  loading: boolean
  busy: string | null
  error: string | null
  integrations: IntegrationStatus | null
  refreshProjects: () => Promise<void>
  selectProject: (id: string) => Promise<void>
  refreshProject: () => Promise<void>
  createProject: (payload: { name?: string; example?: boolean; brief?: BusinessBrief }) => Promise<Project>
  createBlankProject: (name?: string) => Promise<Project>
  removeProject: (id: string) => Promise<void>
  run: (label: string, fn: () => Promise<unknown>) => Promise<boolean>
  clearError: () => void
}

const Ctx = createContext<ProjectContextValue | null>(null)
const STORAGE_KEY = 'commercepilot.currentProject'

// Placeholder name for a brand-new project. The backend requires a non-empty
// business_name, so this becomes the project name until the user saves their
// own business brief in Settings. No example data is seeded.
export const BLANK_PROJECT_NAME = 'New Project'

// An empty brief: only the placeholder name is filled in, every business
// detail is left for the user. Matches the backend's BusinessBrief defaults.
export function blankBrief(name: string): BusinessBrief {
  return {
    business_name: name,
    industry: '',
    niche: '',
    target_market: 'Pakistan',
    target_audience: '',
    currency: 'PKR',
    budget: 0,
    brand_personality: '',
    preferred_price_min: null,
    preferred_price_max: null,
    constraints: [],
    notes: '',
  }
}

export function ProjectProvider({ children }: { children: ReactNode }) {
  const [projects, setProjects] = useState<ProjectSummary[]>([])
  const [project, setProject] = useState<Project | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [integrations, setIntegrations] = useState<IntegrationStatus | null>(null)

  // Reload the sidebar list of projects (cheap; called after create/delete).
  const refreshProjects = useCallback(async () => {
    const res = await api.listProjects()
    setProjects(res.projects)
    return undefined
  }, [])

  // Open a project and remember it. On failure the selection is cleared rather
  // than leaving a half-loaded workspace on screen.
  const selectProject = useCallback(async (id: string) => {
    setLoading(true)
    try {
      const p = await api.getProject(id)
      setProject(p)
      localStorage.setItem(STORAGE_KEY, id)
    } catch (err) {
      setError(errorText(err))
      setProject(null)
      localStorage.removeItem(STORAGE_KEY)
    } finally {
      setLoading(false)
    }
  }, [])

  // Re-read the open project after an action the backend performed on it.
  const refreshProject = useCallback(async () => {
    if (!project) return
    try {
      setProject(await api.getProject(project.id))
    } catch (err) {
      setError(errorText(err))
    }
  }, [project])

  const createProject = useCallback(
    async (payload: { name?: string; example?: boolean; brief?: BusinessBrief }) => {
      const p = await api.createProject(payload)
      setProject(p)
      localStorage.setItem(STORAGE_KEY, p.id)
      await refreshProjects()
      return p
    },
    [refreshProjects],
  )

  // Real (non-example) project: created empty and immediately made active, so
  // the caller can send the user straight to the business brief in Settings.
  const createBlankProject = useCallback(
    async (name: string = BLANK_PROJECT_NAME) => createProject({ name, brief: blankBrief(name) }),
    [createProject],
  )

  const removeProject = useCallback(
    async (id: string) => {
      await api.deleteProject(id)
      if (project?.id === id) {
        setProject(null)
        localStorage.removeItem(STORAGE_KEY)
      }
      await refreshProjects()
    },
    [project, refreshProjects],
  )

  // Wrapper for user actions: sets the busy label for spinners, clears the old
  // error, and converts any thrown API error into a readable banner message.
  const run = useCallback(
    async (label: string, fn: () => Promise<unknown>) => {
      setBusy(label)
      setError(null)
      try {
        await fn()
        return true
      } catch (err) {
        setError(errorText(err))
        return false
      } finally {
        setBusy(null)
      }
    },
    [],
  )

  // Initial load: integrations status, project list, then the last open
  // project. Running them together keeps first paint fast.
  useEffect(() => {
    ;(async () => {
      try {
        const [integ] = await Promise.all([api.integrations(), refreshProjects()])
        setIntegrations(integ)
        const last = localStorage.getItem(STORAGE_KEY)
        if (last) await selectProject(last)
      } catch (err) {
        setError(errorText(err))
      } finally {
        setLoading(false)
      }
    })()
  }, [refreshProjects, selectProject])

  const value = useMemo<ProjectContextValue>(
    () => ({
      projects, project, loading, busy, error, integrations,
      refreshProjects, selectProject, refreshProject, createProject, createBlankProject, removeProject, run,
      clearError: () => setError(null),
    }),
    [projects, project, loading, busy, error, integrations, refreshProjects, selectProject, refreshProject, createProject, createBlankProject, removeProject, run],
  )

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useProject() {
  const ctx = useContext(Ctx)
  if (!ctx) throw new Error('useProject must be used inside ProjectProvider')
  return ctx
}
