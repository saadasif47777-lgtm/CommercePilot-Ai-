import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { api, errorText, setCredentials } from '../services/api'
import { Button, Card, ErrorBanner, Field, Input } from './ui'

export function AuthGate({ children }: { children: ReactNode }) {
  const [signedIn, setSignedIn] = useState(false)
  const [username, setUsername] = useState('admin')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => {
    const reset = () => setSignedIn(false)
    window.addEventListener('workspace-signout', reset)
    return () => window.removeEventListener('workspace-signout', reset)
  }, [])
  if (signedIn) return children
  return <main className="flex min-h-screen items-center justify-center bg-mist p-6">
    <Card className="w-full max-w-md">
      <p className="text-xs font-semibold uppercase tracking-widest text-accent-dark">CommercePilot AI</p>
      <h1 className="mt-3 font-display text-2xl font-semibold">Sign in to your workspace</h1>
      <p className="mt-2 text-sm text-muted">Manage your business, products and connected accounts in one place.</p>
      {error && <div className="mt-4"><ErrorBanner message={error} onDismiss={() => setError('')} /></div>}
      <form className="mt-6 space-y-4" onSubmit={async e => {
        e.preventDefault(); setBusy(true); setError('')
        setCredentials(username, password)
        try { await api.listProjects(); setSignedIn(true); setPassword('') }
        catch (err) { setError(errorText(err)) }
        finally { setBusy(false) }
      }}>
        <Field label="Username"><Input required autoComplete="username" value={username} onChange={e => setUsername(e.target.value)} /></Field>
        <Field label="Password"><Input required type="password" autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)} /></Field>
        <Button type="submit" busy={busy} className="w-full">Sign in</Button>
      </form>
      <p className="mt-4 text-xs text-muted">Use the workspace credentials supplied by your administrator. Sign-in credentials remain in memory and are cleared when this page closes.</p>
    </Card>
  </main>
}
