// TypeScript mirrors of the backend Pydantic schemas.
//
// When a model in `commercepilot/schemas.py` changes, update the matching
// interface here in the same commit; `tsc` then points at every screen that
// needs to handle the new field.

export interface DemandSignal { label: string; value: string; evidence: string }

export interface ScoreFactor {
  factor: string
  weight: number
  raw_score: number | null
  contribution: number | null
  note: string
}

export interface Product {
  page_kind?: 'not_checked' | 'product' | 'collection' | 'needs_review'
  price_source?: string
  page_checked_at?: string | null
  extraction_note?: string
  availability?: string
  id: string
  title: string
  description: string
  category: string
  source: 'sample' | 'live' | 'merged' | 'manual'
  source_url: string | null
  observed_price: number | null
  currency: string | null
  estimated_cost: number | null
  observed_cost?: number | null
  cost_is_estimate: boolean
  demand_level: 'low' | 'medium' | 'high' | null
  demand_signals: DemandSignal[]
  competition: 'low' | 'medium' | 'high' | 'unknown'
  audience_fit: number | null
  price_suitability: number | null
  audience_tags: string[]
  score: number | null
  evidence_score: number | null
  evidence_coverage: number | null
  score_breakdown: ScoreFactor[]
  confidence: 'low' | 'medium' | 'high'
  ranking_reason: string
  is_sample_data: boolean
  margin_pct: number | null
  gross_profit: number | null
}

export interface ResearchRequest {
  currency?: string
  niche?: string
  market?: string
  audience?: string
  budget?: number
  price_min?: number | null
  price_max?: number | null
  constraints?: string[]
  categories?: string[]
  mode: 'sample' | 'live' | 'both'
  limit?: number
}

export interface ResearchResult {
  ai_summary?: string
  ai_model?: string
  ai_reviews?: Record<string, string>
  mode: string
  query: string
  products: Product[]
  is_sample_data: boolean
  contains_live_results: boolean
  sources: string[]
  warnings: string[]
  generated_at: string
  elapsed_ms: number
}

export interface BusinessBrief {
  business_name: string
  industry: string
  niche: string
  target_market: string
  target_audience: string
  currency: string
  budget: number
  brand_personality: string
  preferred_price_min: number | null
  preferred_price_max: number | null
  constraints: string[]
  notes: string
}

export interface NavItem { label: string; href: string }
export interface BenefitsItem { title: string; text: string; icon?: string }
export interface ReviewItemT { name: string; rating: number; text: string }
export interface FaqItemT { q: string; a: string }
export interface FooterColumn { title: string; links: string[] }

export interface HeaderSection { type: 'header'; visible: boolean; logo_text: string; nav: NavItem[]; cta_label: string; show_search: boolean }
export interface HeroSection {
  type: 'hero'; visible: boolean
  style: 'centered' | 'split' | 'editorial_split' | 'boxed' | 'minimal'
  badge: string; headline: string; subheadline: string
  cta_label: string; secondary_cta_label: string; image_style: string
}
export interface FeaturedSection { type: 'featured'; visible: boolean; title: string; show_catalog: boolean; catalog_filter: boolean }
export interface ProductDetailSection { type: 'product_detail'; visible: boolean; title: string; description: string; bullets: string[] }
export interface BenefitsSection { type: 'benefits'; visible: boolean; title: string; items: BenefitsItem[] }
export interface ReviewsSection { type: 'reviews'; visible: boolean; title: string; sample_label: string; items: ReviewItemT[] }
export interface FaqSection { type: 'faq'; visible: boolean; title: string; items: FaqItemT[] }
export interface FooterSection { type: 'footer'; visible: boolean; columns: FooterColumn[]; note: string }

export type Section =
  | HeaderSection | HeroSection | FeaturedSection | ProductDetailSection
  | BenefitsSection | ReviewsSection | FaqSection | FooterSection

export interface StoreDesign {
  primary_color: string
  accent_color: string
  background: string
  surface: string
  text_color: string
  radius: number
  density: 'compact' | 'comfortable' | 'airy'
  font_heading: 'serif' | 'sans' | 'display'
  font_body: 'sans' | 'serif' | 'system'
  hero_style: 'centered' | 'split' | 'editorial_split' | 'boxed' | 'minimal'
  card_style: 'minimal' | 'bordered' | 'elevated'
  animation: 'none' | 'subtle' | 'moderate'
}

export interface WebsiteSpec {
  version: number
  brand_name: string
  tagline: string
  personality: string
  industry: string
  design: StoreDesign
  sections: Section[]
  product: Product | null
  currency: string
  sample_catalog: Product[]
  generation_mode: 'template' | 'llm'
  edit_history: { at: string; change: string; prompt?: string }[]
}

export interface StoreEditResponse {
  spec: WebsiteSpec
  applied_changes: string[]
  unmatched: boolean
  message: string
}

export interface Allocation { label: string; amount: number; purpose: string }
export interface CreativeConcept { name: string; angle: string; headline: string; primary_text: string; cta: string }

export interface CampaignSimulation {
  label: string
  metric_source: string
  assumptions: { cpc: number; conversion_rate_pct: number; currency: string }
  rows: { label: string; spend: number; clicks: number; conversions: number; revenue: number; note?: string }[]
  totals: { spend: number; revenue: number; roas: number | null }
  disclaimer: string
}

export interface CampaignPlan {
  targeting?: CampaignTargeting
  objective: string
  objective_detail: string
  duration_days: number
  budget: number
  currency: string
  allocations: Allocation[]
  allocation_valid: boolean
  audience_hypotheses: string[]
  creatives: CreativeConcept[]
  testing_strategy: string[]
  kpis: string[]
  risks_and_assumptions: string[]
  estimates_are_illustrative: boolean
  status: 'draft' | 'demo_simulated'
  publication: string
  meta_connection: string
  generation_mode: 'template' | 'llm'
  created_at: string
  simulation?: CampaignSimulation
}

export interface ScenarioInput { clicks?: number; conversion_rate_pct?: number; cpc?: number }

export interface Scenario {
  assumptions?: { clicks: number; conversion_rate_pct: number; cpc: number }
  conversions?: number
  revenue?: number
  cogs?: number
  ad_cost?: number
  gross_profit?: number
  net_profit?: number
  roas?: number | null
  cpa?: number | null
  available: boolean
  reason?: string
  label?: string
}

export interface AnalysisResult {
  currency: string
  product: { id: string; title: string; is_sample_data: boolean }
  unit_economics: {
    selling_price: number | null
    product_cost: number | null
    cost_is_estimate: boolean
    currency: string
    gross_profit_per_unit: number | null
    gross_margin_pct: number | null
    break_even_roas: number | null
    break_even_ad_spend_per_unit: number | null
  }
  contribution_economics?: {
    shipping_cost_per_unit: number | null
    packaging_cost_per_unit: number | null
    transaction_fee_per_unit: number | null
    fixed_costs: number | null
    currency: string
    extra_unit_cost: number | null
    contribution_per_unit: number | null
    markup_pct: number | null
    break_even_units: number | null
  }
  budget_summary: {
    budget: number | null
    planned_spend: number | null
    reserve_held?: number | null
    expected_spend?: number | null
    remaining: number | null
    utilization_pct: number | null
    currency?: string
  }
  kpis: { cpa: number | null; conversion_rate_pct: number | null; roas: number | null; source: string; clicks?: number }
  scenarios: Record<string, Scenario>
  assumptions: Record<string, { clicks: number; conversion_rate_pct: number; cpc: number }>
  recommendations: string[]
  warnings: string[]
  errors: string[]
  formula_notes: Record<string, string>
  generated_at: string
  analysis_mode: string
}

export interface AgentExecution {
  id: string
  agent: string
  status: 'running' | 'success' | 'error' | 'skipped'
  started_at: string
  finished_at: string | null
  input_summary: string
  output_summary: string
  errors: string[]
  warnings: string[]
}

export interface StepState {
  id: string
  title: string
  status: 'pending' | 'running' | 'success' | 'error' | 'skipped' | 'waiting'
  message: string
  updated_at: string
}

export interface Report {
  project_id: string
  project_name: string
  generated_at: string
  sections: { title: string; items: string[] }[]
  next_actions: string[]
  data_provenance: string[]
  steps: Record<string, StepState>
  executions: AgentExecution[]
  warnings: string[]
}

export interface Project {
  saved_products?: Product[]
  market_intelligence?: MarketIntelligence
  id: string
  name: string
  created_at: string
  updated_at: string
  brief: BusinessBrief
  research: ResearchResult | null
  selected_product: Product | null
  store_spec: WebsiteSpec | null
  campaign: CampaignPlan | null
  analysis: AnalysisResult | null
  report: Report | null
  executions: AgentExecution[]
  steps: Record<string, StepState>
  is_example: boolean
  demo_labels: string[]
}

export interface CampaignTargeting {
  locations: string[]; languages: string[]; age_min: number; age_max: number
  placements: string[]; landing_url: string; optimization: string
}
export interface MarketIntelligence {
  recommendations?: { suggestion: string; evidence: string; source_index: number }[]
  query: string; checked_at: string; provider: string
  sources: { title: string; url: string; snippet: string }[]
  review_steps: string[]; limitations: string; warning?: string
}

export interface ProjectSummary {
  id: string
  name: string
  created_at: string
  updated_at: string
  is_example: boolean
  brief: BusinessBrief
  selected_product: string | null
  steps: Record<string, string>
  has_campaign: boolean
  has_analysis: boolean
}

export interface WorkflowResult {
  project_id: string
  steps: { id: string; status: string }[]
  error: { step: string; message: string } | null
  message?: string
  project?: Project
}

export interface IntegrationStatus {
  llm: { provider: string; status: string; model: string; detail: string; anthropic?: { model: string; status: string } | null; modules?: Record<string, { provider: string; model: string; status: string }> }
  web_search: { provider: string; status: string; detail: string }
  meta: {
    provider: string
    status: string
    capabilities_when_connected: string[]
    current_capabilities: string[]
    ad_account_id: string
    token_configured: boolean
    missing_configuration: string[]
    setup_instructions: string[]
    note: string
  }
  shopify: {
    provider: string
    status: string
    store_domain: string
    token_configured: boolean
    capabilities_when_connected: string[]
    current_capabilities: string[]
    missing_configuration: string[]
    setup_instructions: string[]
  }
  storage: { provider: string; status: string; detail: string }
}

export interface AssistantReply {
  intent: string
  reply: string
  applied?: string[]
  workflow?: WorkflowResult
  research?: { count: number; warnings: string[] }
}
