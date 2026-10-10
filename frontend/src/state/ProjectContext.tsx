import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { api, errorText } from '../services/api'
import type { IntegrationStatus, Project, ProjectSummary } from '../types'

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
  createProject: (payload: { name?: string; example?: boolean }) => Promise<Project>
  removeProject: (id: string) => Promise<void>
  run: (label: string, fn: () => Promise<unknown>) => Promise<boolean>
  clearError: () => void
}

const Ctx = createContext<ProjectContextValue | null>(null)
const STORAGE_KEY = 'commercepilot.currentProject'

export function ProjectProvider({ children }: { children: ReactNode }) {
  const [projects, setProjects] = useState<ProjectSummary[]>([])
  const [project, setProject] = useState<Project | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [integrations, setIntegrations] = useState<IntegrationStatus | null>(null)

  const refreshProjects = useCallback(async () => {
    const res = await api.listProjects()
    setProjects(res.projects)
    return undefined
  }, [])

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

  const refreshProject = useCallback(async () => {
    if (!project) return
    try {
      setProject(await api.getProject(project.id))
    } catch (err) {
      setError(errorText(err))
    }
  }, [project])

  const createProject = useCallback(
    async (payload: { name?: string; example?: boolean }) => {
      const p = await api.createProject(payload)
      setProject(p)
      localStorage.setItem(STORAGE_KEY, p.id)
      await refreshProjects()
      return p
    },
    [refreshProjects],
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

  // initial load: integrations + projects + last selected project
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
      refreshProjects, selectProject, refreshProject, createProject, removeProject, run,
      clearError: () => setError(null),
    }),
    [projects, project, loading, busy, error, integrations, refreshProjects, selectProject, refreshProject, createProject, removeProject, run],
  )

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useProject() {
  const ctx = useContext(Ctx)
  if (!ctx) throw new Error('useProject must be used inside ProjectProvider')
  return ctx
}
