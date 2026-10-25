// Small, dependency-light design system shared by every page.
//
// Keeping buttons, cards, form controls and empty/loading states here means the
// whole app looks consistent and a visual change is one edit rather than twenty.
// Colours come from the Tailwind theme tokens defined in `index.css`.

import type { ReactNode, InputHTMLAttributes, SelectHTMLAttributes, TextareaHTMLAttributes } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

/* ------------------------------------------------------------------ Badge */
// Pill used for provenance and status labels ("SAMPLE", "LIVE", "DEMO").
export function Badge({
  children,
  tone = 'neutral',
  pulse = false,
}: {
  children: ReactNode
  tone?: 'neutral' | 'green' | 'amber' | 'red' | 'ink' | 'blue'
  pulse?: boolean
}) {
  const tones: Record<string, string> = {
    neutral: 'bg-mist-2 text-muted border-line',
    green: 'bg-accent/10 text-brand border-accent/30',
    amber: 'bg-amber-50 text-warn border-amber-200',
    red: 'bg-red-50 text-danger border-red-200',
    ink: 'bg-ink text-white border-ink',
    blue: 'bg-sky-50 text-sky-800 border-sky-200',
  }
  return (
    <span data-ui="badge" className={`inline-flex w-fit max-w-full shrink-0 items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-left text-[11px] font-medium leading-5 tracking-wide ${tones[tone]}`}>
      {pulse && <span className="dot-pulse h-1.5 w-1.5 shrink-0 rounded-full bg-current" />}
      <span className="min-w-0 whitespace-normal [overflow-wrap:anywhere]">{children}</span>
    </span>
  )
}

/* ------------------------------------------------------------------- Card */
// The standard content container: white surface, hairline border, soft shadow.
export function Card({
  children,
  className = '',
  padded = true,
  hover = false,
}: {
  children: ReactNode
  className?: string
  padded?: boolean
  hover?: boolean
}) {
  return (
    <div
      className={`rounded-xl border border-line bg-paper ${padded ? 'p-5' : ''} ${
        hover ? 'transition-shadow hover:shadow-lift' : 'shadow-soft'
      } ${className}`}
    >
      {children}
    </div>
  )
}

export function SectionTitle({ title, subtitle, right }: { title: string; subtitle?: string; right?: ReactNode }) {
  return (
    <div className="mb-4 flex flex-wrap items-start justify-between gap-x-5 gap-y-3">
      <div className="min-w-0 flex-1 basis-[260px]">
        <h2 className="text-lg font-semibold text-ink">{title}</h2>
        {subtitle && <p className="mt-1 text-sm leading-relaxed text-muted">{subtitle}</p>}
      </div>
      {right && <div className="flex max-w-full flex-wrap items-center gap-2">{right}</div>}
    </div>
  )
}

/* ----------------------------------------------------------------- Button */
// One button with variants and sizes; `busy` both disables it and shows a
// spinner, which prevents double submissions on slow requests.
export function Button({
  children,
  onClick,
  variant = 'primary',
  size = 'md',
  disabled = false,
  busy = false,
  type = 'button',
  className = '',
  title,
}: {
  children: ReactNode
  onClick?: () => void
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger' | 'accent'
  size?: 'sm' | 'md' | 'lg'
  disabled?: boolean
  busy?: boolean
  type?: 'button' | 'submit'
  className?: string
  title?: string
}) {
  const variants: Record<string, string> = {
    primary: 'bg-brand text-white hover:bg-brand-700 disabled:bg-brand/40',
    accent: 'bg-accent text-brand hover:bg-accent-dark hover:text-white disabled:opacity-50',
    secondary: 'border border-line bg-paper text-ink hover:border-brand/40 hover:bg-mist disabled:opacity-50',
    ghost: 'text-muted hover:bg-mist-2 hover:text-ink disabled:opacity-40',
    danger: 'border border-red-200 bg-paper text-danger hover:bg-red-50 disabled:opacity-50',
  }
  const sizes: Record<string, string> = {
    sm: 'min-h-9 px-2.5 py-1 text-xs',
    md: 'min-h-10 px-3.5 py-2 text-sm',
    lg: 'min-h-11 px-5 py-2.5 text-[15px]',
  }
  return (
    <button
      type={type}
      title={title}
      disabled={disabled || busy}
      onClick={onClick}
      className={`inline-flex shrink-0 items-center justify-center gap-2 rounded-lg text-center font-medium leading-5 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/60 disabled:cursor-not-allowed ${variants[variant]} ${sizes[size]} ${className}`}
    >
      {busy && <Spinner />}
      {children}
    </button>
  )
}

export function Spinner({ className = 'h-3.5 w-3.5' }: { className?: string }) {
  return (
    <svg className={`animate-spin ${className}`} viewBox="0 0 24 24" fill="none" aria-hidden>
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-90" fill="currentColor" d="M4 12a8 8 0 018-8v3a5 5 0 00-5 5H4z" />
    </svg>
  )
}

/* ------------------------------------------------------------------ Forms */
// Field + Input/Textarea/Select share one input style so forms line up.
export function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <label className="form-field">
      <span className="form-field-label text-xs font-semibold uppercase tracking-wide text-muted">{label}</span>
      {children}
      {hint && <span className="form-field-hint text-xs text-muted">{hint}</span>}
    </label>
  )
}

const inputBase =
  'w-full rounded-lg border border-line bg-paper px-3 py-2 text-sm text-ink placeholder:text-muted/60 focus:border-brand/40 focus:outline-none focus:ring-2 focus:ring-accent/25'

export function Input(props: InputHTMLAttributes<HTMLInputElement>) {
  const { className = '', ...rest } = props
  return <input {...rest} className={`h-10 leading-5 ${inputBase} ${className}`} />
}

export function Textarea(props: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  const { className = '', ...rest } = props
  return <textarea {...rest} className={`${inputBase} min-h-[80px] leading-relaxed ${className}`} />
}

export function Select(props: SelectHTMLAttributes<HTMLSelectElement>) {
  const { className = '', children, ...rest } = props
  return (
    <select {...rest} className={`h-10 leading-5 ${inputBase} ${className}`}>
      {children}
    </select>
  )
}

export function Toggle({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label?: string }) {
  return (
    <button
      type="button"
      onClick={() => onChange(!checked)}
      className="flex items-center gap-2 text-sm text-ink"
      aria-pressed={checked}
    >
      <span className={`relative h-5 w-9 rounded-full transition-colors ${checked ? 'bg-accent' : 'bg-mist-2 border border-line'}`}>
        <span className={`absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-all ${checked ? 'left-4' : 'left-0.5'}`} />
      </span>
      {label && <span>{label}</span>}
    </button>
  )
}

/* ----------------------------------------------------------------- States */
// Loading skeletons, empty states and errors: every page handles the same three
// non-happy paths with these components instead of inventing its own.
export function Skeleton({ className = 'h-4 w-full' }: { className?: string }) {
  return <div className={`skeleton rounded ${className}`} />
}

export function SkeletonCards({ count = 3 }: { count?: number }) {
  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="rounded-xl border border-line bg-paper p-5">
          <Skeleton className="h-3 w-20" />
          <Skeleton className="mt-3 h-5 w-4/5" />
          <Skeleton className="mt-2 h-3 w-full" />
          <Skeleton className="mt-1.5 h-3 w-3/5" />
          <div className="mt-4 flex gap-2">
            <Skeleton className="h-7 w-16 rounded-lg" />
            <Skeleton className="h-7 w-24 rounded-lg" />
          </div>
        </div>
      ))}
    </div>
  )
}

export function EmptyState({ title, body, action }: { title: string; body: string; action?: ReactNode }) {
  return (
    <div className="rounded-xl border border-dashed border-line bg-paper/60 px-6 py-12 text-center">
      <div className="mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-mist-2 text-brand">
        <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.8">
          <path d="M4 7h16M4 12h10M4 17h7" strokeLinecap="round" />
        </svg>
      </div>
      <h3 className="text-base font-semibold">{title}</h3>
      <p className="mx-auto mt-1 max-w-md text-sm text-muted">{body}</p>
      {action && <div className="mt-4 flex justify-center">{action}</div>}
    </div>
  )
}

export function ErrorBanner({ message, onRetry, onDismiss }: { message: string; onRetry?: () => void; onDismiss?: () => void }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: -6 }}
      animate={{ opacity: 1, y: 0 }}
      className="mb-4 flex items-start justify-between gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-danger"
    >
      <div className="flex items-start gap-2">
        <svg viewBox="0 0 24 24" className="mt-0.5 h-4 w-4 shrink-0" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="9" /><path d="M12 8v5M12 16h.01" strokeLinecap="round" />
        </svg>
        <span>{message}</span>
      </div>
      <div className="flex shrink-0 gap-2">
        {onRetry && (
          <button onClick={onRetry} className="font-semibold underline underline-offset-2">Retry</button>
        )}
        {onDismiss && (
          <button onClick={onDismiss} className="text-danger/70 hover:text-danger" aria-label="Dismiss">✕</button>
        )}
      </div>
    </motion.div>
  )
}

export function WarningList({ items, title = 'Warnings' }: { items: string[]; title?: string }) {
  if (!items.length) return null
  return (
    <div className="rounded-lg border border-amber-200 bg-amber-50/60 px-4 py-3 text-[13px] text-warn">
      <p className="mb-1 text-xs font-semibold uppercase tracking-wide">{title}</p>
      <ul className="list-disc space-y-0.5 pl-4">
        {items.map((w, i) => (
          <li key={i}>{w}</li>
        ))}
      </ul>
    </div>
  )
}

/* ------------------------------------------------------------------ misc */
// Small presentation helpers used across pages.
export function Stat({ label, value, sub, tone }: { label: string; value: ReactNode; sub?: string; tone?: 'good' | 'bad' | 'neutral' }) {
  const color = tone === 'good' ? 'text-brand' : tone === 'bad' ? 'text-danger' : 'text-ink'
  return (
    <div className="rounded-xl border border-line bg-paper p-4">
      <p className="stat-label text-xs font-semibold uppercase tracking-wide text-muted">{label}</p>
      <p className={`stat-value mt-2 font-display text-xl font-semibold sm:text-2xl ${color}`}>{value}</p>
      {sub && <p className="mt-2 text-xs leading-relaxed text-muted">{sub}</p>}
    </div>
  )
}

export function PageHeader({ eyebrow, title, body, actions }: { eyebrow?: string; title: string; body?: string; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
      <div className="min-w-0 max-w-2xl flex-1 basis-[320px]">
        {eyebrow && <p className="mb-1 text-xs font-semibold uppercase tracking-[0.14em] text-accent-dark">{eyebrow}</p>}
        <h1 className="font-display text-2xl font-semibold leading-tight text-ink md:text-[28px]">{title}</h1>
        {body && <p className="mt-1.5 text-sm leading-relaxed text-muted">{body}</p>}
      </div>
      {actions && <div className={`flex max-w-full flex-wrap items-center gap-2 ${eyebrow ? 'sm:pt-5' : ''}`}>{actions}</div>}
    </div>
  )
}

export function FadeIn({ children, delay = 0, className = '' }: { children: ReactNode; delay?: number; className?: string }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay, ease: [0.22, 1, 0.36, 1] }}
      className={className}
    >
      {children}
    </motion.div>
  )
}

export function Modal({ open, onClose, title, children }: { open: boolean; onClose: () => void; title: string; children: ReactNode }) {
  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 p-4"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.97, y: 8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.98 }}
            transition={{ duration: 0.2 }}
            className="max-h-[85vh] w-full max-w-lg overflow-y-auto rounded-2xl bg-paper p-6 shadow-lift"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-lg font-semibold">{title}</h3>
              <button onClick={onClose} className="rounded-lg p-1 text-muted hover:bg-mist-2" aria-label="Close">✕</button>
            </div>
            {children}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
