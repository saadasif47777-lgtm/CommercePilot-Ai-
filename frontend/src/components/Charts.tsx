// Analytics charts built with Recharts.
//
// These are presentation only: every value comes from the backend analysis, so a
// chart can never disagree with the numbers printed next to it. All charts fill
// their container width, which keeps them readable on phones.

import {
  Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, Pie, PieChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import type { AnalysisResult, Product } from '../types'

// Shared chart styling: muted axes and faint grid lines so data stays dominant.
const AXIS = { stroke: '#9aa19a', fontSize: 11 }
const GRID = '#eceeed'

type TipValue = string | number | ReadonlyArray<string | number> | undefined
const moneyFmt =
  (currency: string) =>
  (v: TipValue): string =>
    `${currency} ${Number(v ?? 0).toLocaleString()}`

export function ScenarioChart({ analysis }: { analysis: AnalysisResult }) {
  const rows = ['conservative', 'base', 'best']
    .map((k) => analysis.scenarios[k])
    .filter(Boolean)
    .map((s) => ({
      name: s.label ?? 'scenario',
      'Revenue': s.revenue ?? 0,
      'Net profit': s.net_profit ?? 0,
      'Ad cost': s.ad_cost ?? 0,
    }))
  if (!rows.length) return null
  return (
    <ResponsiveContainer width="100%" height={260}>
      <BarChart data={rows} margin={{ top: 8, right: 8, left: -8, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={GRID} vertical={false} />
        <XAxis dataKey="name" tick={AXIS} tickLine={false} axisLine={false} />
        <YAxis tick={AXIS} tickLine={false} axisLine={false} />
        <Tooltip formatter={moneyFmt(analysis.currency)} />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        <Bar dataKey="Revenue" fill="#0F3D2E" radius={[4, 4, 0, 0]} />
        <Bar dataKey="Ad cost" fill="#c9a227" radius={[4, 4, 0, 0]} />
        <Bar dataKey="Net profit" fill="#2ECC71" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  )
}

export function BudgetDonut({ allocations, currency }: { allocations: { label: string; amount: number }[]; currency: string }) {
  const COLORS = ['#0F3D2E', '#2ECC71', '#C9A227', '#4C7DF0', '#B08968', '#6B7280']
  const rows = allocations.filter((a) => a.amount > 0).map((a, i) => ({ name: a.label, value: a.amount, fill: COLORS[i % COLORS.length] }))
  if (!rows.length) return null
  return (
    <ResponsiveContainer width="100%" height={220}>
      <PieChart>
        <Pie data={rows} dataKey="value" nameKey="name" innerRadius={54} outerRadius={84} paddingAngle={2}>
          {rows.map((r) => (<Cell key={r.name} fill={r.fill} stroke="none" />))}
        </Pie>
        <Tooltip formatter={moneyFmt(currency)} />
        <Legend wrapperStyle={{ fontSize: 12 }} />
      </PieChart>
    </ResponsiveContainer>
  )
}

export function ProductComparisonChart({ products, currency }: { products: Product[]; currency: string }) {
  const rows = products
    .filter((p) => p.observed_price && p.estimated_cost)
    .slice(0, 8)
    .map((p) => ({
      name: p.title.length > 22 ? `${p.title.slice(0, 21)}…` : p.title,
      'Selling price': p.observed_price ?? 0,
      'Est. cost': p.estimated_cost ?? 0,
      'Gross profit': p.gross_profit ?? 0,
    }))
  if (!rows.length) return null
  return (
    <ResponsiveContainer width="100%" height={280}>
      <BarChart data={rows} margin={{ top: 8, right: 8, left: -4, bottom: 40 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={GRID} vertical={false} />
        <XAxis dataKey="name" tick={{ ...AXIS, fontSize: 10 }} tickLine={false} axisLine={false} angle={-18} interval={0} />
        <YAxis tick={AXIS} tickLine={false} axisLine={false} />
        <Tooltip formatter={moneyFmt(currency)} />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        <Bar dataKey="Selling price" fill="#0F3D2E" radius={[4, 4, 0, 0]} />
        <Bar dataKey="Est. cost" fill="#C9A227" radius={[4, 4, 0, 0]} />
        <Bar dataKey="Gross profit" fill="#2ECC71" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  )
}

export function SpendLine({ analysis }: { analysis: AnalysisResult }) {
  const base = analysis.scenarios.base
  if (!base?.available || !base.assumptions) return null
  const { clicks, conversion_rate_pct, cpc } = base.assumptions
  const price = analysis.unit_economics.selling_price ?? 0
  const cost = analysis.unit_economics.product_cost ?? 0
  const rows = Array.from({ length: 9 }, (_, i) => {
    const spent = (cpc * clicks * i) / 8
    const conv = (spent / cpc) * (conversion_rate_pct / 100)
    return { step: `${Math.round(spent)}`, revenue: conv * price, profit: conv * (price - cost) - spent }
  })
  return (
    <ResponsiveContainer width="100%" height={240}>
      <LineChart data={rows} margin={{ top: 8, right: 8, left: -4, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={GRID} vertical={false} />
        <XAxis dataKey="step" tick={AXIS} tickLine={false} axisLine={false} label={{ value: `Ad spend (${analysis.currency})`, position: 'insideBottomRight', fontSize: 11, fill: '#6b7280' }} />
        <YAxis tick={AXIS} tickLine={false} axisLine={false} />
        <Tooltip formatter={moneyFmt(analysis.currency)} />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        <Line type="monotone" dataKey="revenue" stroke="#0F3D2E" strokeWidth={2} dot={false} name="Revenue" />
        <Line type="monotone" dataKey="profit" stroke="#2ECC71" strokeWidth={2} dot={false} name="Gross profit after ads" />
      </LineChart>
    </ResponsiveContainer>
  )
}

export function SimulationChart({ rows, currency }: { rows: { label: string; spend: number; revenue: number }[]; currency: string }) {
  const data = rows.filter((r) => r.spend > 0).map((r) => ({ name: r.label, Spend: r.spend, 'Simulated revenue': r.revenue }))
  if (!data.length) return null
  return (
    <ResponsiveContainer width="100%" height={230}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: -4, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={GRID} vertical={false} />
        <XAxis dataKey="name" tick={{ ...AXIS, fontSize: 10 }} tickLine={false} axisLine={false} />
        <YAxis tick={AXIS} tickLine={false} axisLine={false} />
        <Tooltip formatter={moneyFmt(currency)} />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        <Bar dataKey="Spend" fill="#C9A227" radius={[4, 4, 0, 0]} />
        <Bar dataKey="Simulated revenue" fill="#0F3D2E" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  )
}
