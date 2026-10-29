import { test, expect } from '@playwright/test'

test('settings shows module routes and verifies Claude separately from the default model', async ({ page, request }) => {
  const status = await (await request.get('/api/integrations/status')).json()
  status.llm.modules = Object.fromEntries(['marketing', 'store_architect', 'product_hunting'].map(name => [name, { provider: 'anthropic', model: 'claude-sonnet-5-5', status: 'configured_unverified' }]))
  await page.route('**/api/integrations/status', route => route.fulfill({ json: status }))
  let claudeProbes = 0
  await page.route('**/api/integrations/llm/verify?provider=anthropic', route => {
    claudeProbes++
    return route.fulfill({ json: { verified: true, model: 'claude-sonnet-5-5' } })
  })
  await page.goto('/settings')
  await expect(page.getByText('anthropic · claude-sonnet-5-5', { exact: true })).toHaveCount(3)
  await page.getByRole('button', { name: 'Verify Claude connection', exact: true }).click()
  await expect(page.getByRole('status')).toContainText('Claude connection verified: claude-sonnet-5-5')
  expect(claudeProbes).toBe(1)
  await page.setViewportSize({ width: 390, height: 844 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true)
})

test('execution statuses never overlap long summaries in Overview or Project History', async ({ page, request }) => {
  const name = 'Handmade ceramic decorative vases and home accessories studio'
  const created = await (await request.post('/api/projects', { data: { brief: { business_name: name, niche: 'ceramics', budget: 10000 } } })).json()
  const populated = await (await request.get(`/api/projects/${created.id}`)).json()
  const longSummary = "11 ranked candidates, query 'Handmade ceramic decorative vases product price Lahore and Islamabad, Pakistan price 1500-5000'"
  populated.executions = ['success', 'error', 'skipped', 'running', 'success'].map((status, i) => ({
    id: `layout-${i}`, agent: i % 2 ? 'Product Hunter' : 'Business Analyst', status,
    started_at: new Date().toISOString(), finished_at: null,
    input_summary: i % 2 ? "mode=live, niche='Handmade ceramic decorative vases'" : 'Economics',
    output_summary: i % 2 ? longSummary : `Source https://brand.example/products/${'handcrafted-ceramics-'.repeat(12)}`,
    warnings: ['Product pages are inspected where permitted. Collection pages are discovery sources, not products. Prices are source observations, not supplier quotes. Enter your own cost to calculate margin; sales demand remains unverified.'],
    errors: status === 'error' ? ['The provider could not complete this request. Please retry.'] : [],
  }))
  for (const step of Object.values(populated.steps) as { status: string }[]) step.status = 'success'
  populated.steps.store.status = 'pending'
  populated.steps.store.title = `Store Architect storefront: ${'Handcrafted ceramic collections '.repeat(8)}`
  await page.route(`**/api/projects/${created.id}`, route => route.fulfill({ json: populated }))
  await page.reload()
  await page.getByLabel('Active project', { exact: true }).selectOption(created.id)
  await expect(page.getByRole('heading', { name, exact: true })).toBeVisible()
  for (const width of [320, 390, 768, 1280, 1600]) {
    await page.setViewportSize({ width, height: 900 })
    for (const route of ['/', '/history']) {
      await page.goto(route)
      await expect(page.getByTestId('execution-row')).toHaveCount(5)
      const rows = await page.getByTestId('execution-row').evaluateAll(elements => elements.map(row => {
        const badge = row.querySelector('[data-ui="badge"]')!.getBoundingClientRect()
        const content = row.querySelector('[data-testid="execution-content"]')!.getBoundingClientRect()
        return { badgeRight: badge.right, badgeBottom: badge.bottom, contentLeft: content.left, contentTop: content.top }
      }))
      for (const row of rows) {
        if (width >= 640) {
          expect(row.contentLeft - row.badgeRight).toBeGreaterThanOrEqual(11)
          expect(Math.abs(row.contentLeft - rows[0].contentLeft)).toBeLessThan(1)
        } else {
          expect(row.contentTop - row.badgeBottom).toBeGreaterThanOrEqual(3)
        }
      }
      const clippedBadges = await page.locator('[data-ui="badge"]').evaluateAll(elements => elements.filter(el => el.scrollWidth > el.clientWidth + 1).map(el => el.textContent))
      expect(clippedBadges).toEqual([])
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true)
    }
  }
})

test('text, product metrics and actions remain aligned at mobile tablet and desktop widths', async ({ page, request }) => {
  const created = await (await request.post('/api/projects', { data: { brief: { business_name: 'Alignment QA', niche: 'lighting', budget: 10000 } } })).json()
  for (const title of ['Desk lamp', 'Handcrafted adjustable desk lighting for a comfortable reading corner', 'Ceramic lamp']) {
    await request.post(`/api/projects/${created.id}/products/manual`, { data: { title, observed_price: 3250, observed_cost: 1200 } })
  }
  const populated = await (await request.get(`/api/projects/${created.id}`)).json()
  populated.research.products = populated.research.products.map((p: Record<string, unknown>, i: number) => ({ ...p, source: 'live', page_kind: 'product', score: 9.5, page_checked_at: '2026-10-25T10:00:00Z', price_source: 'product structured offer', description: i === 0 ? '' : 'Product details with longer text to exercise wrapping and consistent card alignment.', extraction_note: i === 1 ? 'Confirm the selected variant and supplier quote before use.' : '', source_url: 'https://brand.example/products/lamp' }))
  populated.research.ai_summary = 'Check supplier quotes and packaging before testing these products.'
  populated.research.ai_model = 'claude-sonnet-5-5'
  populated.research.ai_reviews = { [populated.research.products[0].id]: 'Confirm dimensions and safe delivery packaging.' }
  await page.route(`**/api/projects/${created.id}`, route => route.fulfill({ json: populated }))
  await page.reload()
  await page.getByLabel('Active project', { exact: true }).selectOption(created.id)
  await expect(page.getByRole('heading', { name: 'Alignment QA', exact: true })).toBeVisible()
  await page.getByRole('link', { name: 'Product Hunter', exact: true }).click()
  await expect(page.getByTestId('product-card')).toHaveCount(3)
  await expect(page.getByRole('heading', { name: 'AI evidence review', exact: true })).toBeVisible()
  await page.getByText('Review guidance by product', { exact: true }).click()
  await expect(page.getByText('Confirm dimensions and safe delivery packaging.', { exact: true })).toBeVisible()
  for (const width of [390, 768, 1280, 1600]) {
    await page.setViewportSize({ width, height: 1000 })
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true)
    const cards = await page.getByTestId('product-card').evaluateAll(elements => elements.map(card => ({
      top: card.getBoundingClientRect().top,
      metrics: card.querySelector('[data-testid="product-metrics"]')!.getBoundingClientRect().top,
      actions: card.querySelector('[data-testid="product-actions"]')!.getBoundingClientRect().top,
      scoreHeight: card.querySelector('[data-testid="product-score"] span')!.getBoundingClientRect().height,
    })))
    for (const card of cards) expect(card.scoreHeight).toBeLessThanOrEqual(24)
    for (let i = 1; i < cards.length; i++) {
      if (Math.abs(cards[i].top - cards[i - 1].top) < 2) {
        expect(Math.abs(cards[i].metrics - cards[i - 1].metrics)).toBeLessThan(2)
        expect(Math.abs(cards[i].actions - cards[i - 1].actions)).toBeLessThan(2)
      }
    }
  }
  await page.setViewportSize({ width: 1280, height: 900 })
  const fields = [page.getByLabel(/^Niche/), page.getByLabel('Research source', { exact: true }), page.getByLabel('Price PKR min', { exact: true }), page.getByLabel('Price max', { exact: true })]
  const boxes = await Promise.all(fields.map(field => field.boundingBox()))
  for (const box of boxes) {
    expect(box).not.toBeNull()
    expect(Math.abs(box!.y - boxes[0]!.y)).toBeLessThan(2)
    expect(Math.abs(box!.height - 40)).toBeLessThan(2)
  }
  const constraintBox = await page.getByLabel(/^Constraints/).boundingBox()
  const actionBox = await page.getByRole('button', { name: 'Re-run research', exact: true }).boundingBox()
  expect(Math.abs(constraintBox!.y - actionBox!.y)).toBeLessThan(2)
})

test('imports an individual product URL and persists its page provenance in the library', async ({ page, request }) => {
  const created = await (await request.post('/api/projects', { data: { brief: { business_name: 'URL research QA', niche: 'lamps', budget: 10000 } } })).json()
  await page.reload()
  await page.getByLabel('Active project', { exact: true }).selectOption(created.id)
  await expect(page.getByRole('heading', { name: 'URL research QA', exact: true })).toBeVisible()
  await page.getByRole('link', { name: 'Product Hunter', exact: true }).click()
  await page.getByLabel('Individual product URL', { exact: true }).fill('https://brand.example/products/lamp')
  await page.getByRole('button', { name: 'Read & save product', exact: true }).click()
  await expect(page.getByText('Product details saved to your library.', { exact: false })).toBeVisible()
  await page.reload()
  await expect(page.getByText('Imported URL lamp', { exact: true })).toBeVisible()
  const saved = await (await request.get(`/api/projects/${created.id}/products/saved`)).json()
  expect(saved.products[0].price_source).toBe('product structured offer')
  expect(saved.products[0].observed_price).toBe(3000)
  expect(saved.products[0].estimated_cost).toBeNull()
})

test('mobile workspace stays within viewport and campaign delivery choices persist', async ({ page, request }) => {
  const created = await (await request.post('/api/projects', { data: { brief: { business_name: 'Mobile QA', niche: 'lamps', budget: 10000 } } })).json()
  await request.post(`/api/projects/${created.id}/products/manual`, { data: { title: 'Desk lamp', observed_price: 2000, observed_cost: 800 } })
  await page.reload()
  await page.getByLabel('Active project', { exact: true }).selectOption(created.id)
  await expect(page.getByRole('heading', { name: 'Mobile QA', exact: true })).toBeVisible()
  await page.setViewportSize({ width: 390, height: 844 })
  for (const route of ['/', '/business', '/products', '/marketing', '/analytics', '/settings', '/support', '/assistant']) {
    await page.goto(route)
    await expect(page.locator('main h1')).toBeVisible()
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true)
  }
  await page.goto('/marketing')
  await page.getByLabel(/^Target locations/).fill('Lahore, Islamabad')
  await page.getByLabel(/^Languages/).fill('Urdu, English')
  await page.getByLabel('Minimum age', { exact: true }).fill('25')
  await page.getByLabel('Maximum age', { exact: true }).fill('45')
  const generated = page.waitForResponse(response => response.url().endsWith('/generate-campaign') && response.request().method() === 'POST')
  await page.getByRole('button', { name: 'Generate campaign plan', exact: true }).click()
  const response = await generated
  expect(response.request().postDataJSON().targeting.locations).toEqual(['Lahore', 'Islamabad'])
  expect((await response.json()).targeting.locations).toEqual(['Lahore', 'Islamabad'])
  await expect(page.getByText('Creative concepts', { exact: true })).toBeVisible()
  await page.reload()
  await expect(page.getByLabel(/^Target locations/)).toHaveValue('Lahore,Islamabad')
  await expect(page.getByLabel('Minimum age', { exact: true })).toHaveValue('25')
})

test.beforeEach(async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('button', { name: 'Add New Project' }).first()).toBeVisible()
  await expect(page.getByRole('button', { name: 'Sign in', exact: true })).toHaveCount(0)
})

test('business, live research, costs, generation, analytics, report and saved history', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  let researchRequests = 0
  page.on('request', request => { if (request.url().endsWith('/research') && request.method() === 'POST') researchRequests++ })
  await page.getByRole('button', { name: 'Add New Project', exact: true }).first().click()
  await page.getByLabel('Business name', { exact: true }).fill('Client Lighting')
  await page.getByLabel('Industry', { exact: true }).fill('Home')
  await page.getByLabel('Products or niche', { exact: true }).fill('Desk lamps')
  await page.getByLabel('Target audience', { exact: true }).fill('Home office workers')
  await page.getByLabel('Campaign budget', { exact: true }).fill('10000')
  await page.getByRole('button', { name: 'Create business workspace' }).click()
  await expect(page.getByRole('button', { name: 'Save business information' })).toBeVisible()
  await page.getByRole('link', { name: 'Product Hunter', exact: true }).click()
  await page.getByRole('button', { name: 'Run Product Hunter', exact: true }).first().click()
  await expect(page.getByText('Desk lamp PKR 2000', { exact: true }).first()).toBeVisible()
  expect(researchRequests).toBe(1)
  await page.getByRole('button', { name: 'Add to Project', exact: true }).first().click()
  await page.getByLabel('Supplier cost per unit', { exact: true }).fill('800')
  await page.getByRole('button', { name: 'Save prices & costs' }).click()
  await page.getByRole('link', { name: 'Store Architect', exact: true }).click()
  await page.getByRole('button', { name: 'Generate storefront', exact: true }).first().click()
  await expect(page.getByText('Light your workspace', { exact: true })).toBeVisible()
  await page.getByRole('link', { name: 'Marketing Studio', exact: true }).click()
  await page.getByRole('button', { name: 'Generate campaign plan' }).click()
  await expect(page.getByText('Thoughtful desk lighting', { exact: true }).first()).toBeVisible()
  await page.getByRole('link', { name: 'Business Analytics', exact: true }).click()
  await page.getByRole('button', { name: 'Run analysis', exact: true }).first().click()
  await expect(page.getByText('Gross profit / unit', { exact: true })).toBeVisible()
  await page.getByRole('link', { name: 'Overview', exact: true }).click()
  await page.getByRole('button', { name: 'Prepare remaining results' }).click()
  await expect(page.getByText('Your results are ready.', { exact: true })).toBeVisible()
  await expect(page.getByText(/Prototype mode|Demo data labelled|competition prototype|Run simulated execution/)).toHaveCount(0)
  await page.getByRole('link', { name: 'AI Commerce Assistant', exact: true }).click()
  await page.getByRole('button', { name: 'Show me the report', exact: true }).click()
  await page.getByRole('button', { name: 'Build project report', exact: true }).click()
  await expect(page.getByText('Report rebuilt with the latest data.', { exact: false })).toBeVisible()
  await page.getByRole('link', { name: 'Overview', exact: true }).click()
  await page.reload()
  await expect(page.getByRole('heading', { name: 'Client Lighting', exact: true })).toBeVisible()
  expect(errors).toEqual([])
})

test('guides a new visitor, remembers a local business idea and calculates a mobile budget', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  await page.getByRole('link', { name: 'Ask AI where to start', exact: true }).click()
  await expect(page.getByLabel('Message AI assistant', { exact: true })).toBeEnabled()
  await page.getByRole('button', { name: 'How do I get started?', exact: true }).click()
  await expect(page.getByText('Marketing Studio creates campaign drafts', { exact: false })).toBeVisible()
  await page.getByLabel('Message AI assistant', { exact: true }).fill('I have PKR 50k for my whole business selling skincare in Lahore')
  await page.getByRole('button', { name: 'Send', exact: true }).click()
  await expect(page.getByLabel('Available budget', { exact: true })).toHaveValue('50000')
  await expect(page.getByLabel('Planning location', { exact: true })).toHaveValue('Lahore')
  await expect(page.getByRole('table', { name: 'Calculated budget allocation' })).toBeVisible()
  await expect(page.getByText('Risks & what to do', { exact: true })).toBeVisible()
  await page.getByLabel('Message AI assistant', { exact: true }).fill('What should I do next?')
  await page.getByRole('button', { name: 'Send', exact: true }).click()
  await expect(page.getByText('For skincare in Lahore', { exact: false }).last()).toBeVisible()
  await page.reload()
  await expect(page.getByLabel('Available budget', { exact: true })).toHaveValue('50000')
  await expect(page.getByText('What should I do next?', { exact: true })).toBeVisible()
  await page.getByText('Costs, readiness & optional scenario', { exact: true }).click()
  await page.getByLabel('Selling price per order', { exact: true }).fill('1000')
  await page.getByLabel('Product cost per order', { exact: true }).fill('900')
  await page.getByLabel('Other costs per order', { exact: true }).fill('200')
  await page.getByRole('button', { name: 'Review my plan', exact: true }).click()
  await expect(page.getByText('Prepare before ads', { exact: true })).toBeVisible()
  await page.setViewportSize({ width: 390, height: 844 })
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth)
  expect(overflow).toBe(false)
  await page.getByRole('button', { name: 'New conversation', exact: true }).click()
  await expect(page.getByLabel('Available budget', { exact: true })).toHaveValue('')
  await expect(page.getByText('What should I do next?', { exact: true })).toHaveCount(0)
  expect(errors).toEqual([])
})

test('integration forms remain visible after status failure', async ({ page }) => {
  await page.route('**/api/integrations/status', route => route.fulfill({ status: 503, json: { detail: 'Temporary status failure' } }))
  await page.getByRole('link', { name: 'Settings & Integrations', exact: true }).click()
  await page.getByRole('button', { name: 'Refresh status' }).click()
  await expect(page.getByLabel('Shop domain', { exact: true })).toBeVisible()
  await expect(page.getByLabel('Ad account ID', { exact: true })).toBeVisible()
})

test('connects Shopify and Meta, imports catalog and reads measured reporting', async ({ page }) => {
  await page.getByRole('button', { name: 'Add New Project', exact: true }).first().click()
  await page.getByLabel('Business name', { exact: true }).fill('Imported Catalog Client')
  await page.getByLabel('Industry', { exact: true }).fill('Home')
  await page.getByLabel('Products or niche', { exact: true }).fill('Desk lamps')
  await page.getByLabel('Target audience', { exact: true }).fill('Home office workers')
  await page.getByLabel('Campaign budget', { exact: true }).fill('10000')
  await page.getByRole('button', { name: 'Create business workspace' }).click()
  await expect(page.getByRole('button', { name: 'Save business information' })).toBeVisible()
  await page.getByRole('link', { name: 'Settings & Integrations', exact: true }).click()
  await page.getByLabel('Shop domain', { exact: true }).fill('test-store.myshopify.com')
  await page.getByLabel('Admin API access token').fill('browser-only-shopify-token')
  await page.getByRole('button', { name: 'Connect Shopify', exact: true }).click()
  await expect(page.getByText('Shopify connected. You can now load your catalog.')).toBeVisible()
  await page.getByRole('button', { name: 'Load catalog', exact: true }).click()
  await expect(page.getByText('Imported lamp', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Import & select', exact: true }).click()
  await expect(page.getByText('Imported lamp imported and selected.', { exact: false })).toBeVisible()
  await page.getByLabel('Ad account ID', { exact: true }).fill('act_123456')
  await page.getByLabel('Access token', { exact: false }).last().fill('browser-only-meta-token')
  await page.getByRole('button', { name: 'Connect Meta', exact: true }).click()
  await expect(page.getByText('Connected to Test account.')).toBeVisible()
  await page.getByRole('button', { name: 'Read last 30 days', exact: true }).click()
  await expect(page.getByText(/Spend: PKR 1000/)).toBeVisible()
})

test('syncs Shopify support, previews grounded answers and embeds a cross-origin customer widget', async ({ page, request }) => {
  const errors: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  // This test has its own connection; it does not depend on another test's order.
  await request.post('/api/integrations/shopify/credentials', { data: { shop_domain: 'test-store.myshopify.com', admin_token: 'browser-only-shopify-token' } })
  await page.getByRole('link', { name: 'Customer Support', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Customer support', exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Sync Shopify knowledge', exact: true }).click()
  await expect(page.getByText(/Synced 2 published products and 1 policy/)).toBeVisible()
  await page.getByLabel('Assistant name', { exact: true }).fill('Lighting helper')
  await page.getByLabel('Customer support email', { exact: true }).fill('help@client-shop.example')
  await page.getByLabel('Additional storefront origins', { exact: true }).fill('http://localhost:8011')
  await page.getByRole('button', { name: 'Add store FAQ', exact: true }).click()
  await page.getByLabel('FAQ 1 question', { exact: true }).fill('Do you offer gift wrapping?')
  await page.getByLabel('FAQ 1 answer', { exact: true }).fill('Gift wrapping is available on request before checkout.')
  await page.getByRole('checkbox', { name: 'Enable storefront chat' }).check()
  await page.getByRole('button', { name: 'Save support settings', exact: true }).click()
  await expect(page.getByText('Support settings saved.', { exact: true })).toBeVisible()
  await page.getByLabel('Preview customer message', { exact: true }).fill('What is your return policy?')
  await page.getByRole('button', { name: 'Send', exact: true }).click()
  await expect(page.getByRole('link', { name: 'Refund policy', exact: false })).toHaveAttribute('href', 'https://client-shop.example/policies/refund-policy')
  await page.getByLabel('Preview customer message', { exact: true }).fill('Show a desk lamp under USD 25')
  await page.getByRole('button', { name: 'Send', exact: true }).click()
  await expect(page.getByRole('link', { name: /Desk lamp 1/ })).toHaveAttribute('href', 'https://client-shop.example/products/lamp-1')
  const install = await (await request.get('/api/support/install')).json()
  await page.reload()
  await expect(page.getByLabel('Assistant name', { exact: true })).toHaveValue('Lighting helper')
  // Host the storefront on a different origin so Chromium exercises CORS preflight.
  await page.goto('http://localhost:8011/')
  await page.evaluate(({ scriptUrl, widgetId }) => {
    const script = document.createElement('script')
    script.src = scriptUrl; script.dataset.widget = widgetId
    document.body.append(script)
  }, { scriptUrl: 'http://127.0.0.1:8011/api/support/widget.js', widgetId: install.widget_id })
  await page.getByRole('button', { name: 'Chat with us', exact: true }).click()
  await expect(page.getByRole('dialog', { name: 'Lighting helper', exact: true })).toBeVisible()
  await page.getByLabel('Your message', { exact: true }).fill('Show a desk lamp under USD 25')
  await page.getByRole('dialog', { name: 'Lighting helper' }).getByRole('button', { name: 'Send', exact: true }).click()
  await expect(page.getByRole('dialog', { name: 'Lighting helper' }).getByRole('link', { name: 'Desk lamp 1', exact: true })).toHaveAttribute('href', 'https://client-shop.example/products/lamp-1')
  await page.getByLabel('Your message', { exact: true }).fill('Where is my order?')
  await page.getByRole('dialog', { name: 'Lighting helper' }).getByRole('button', { name: 'Send', exact: true }).click()
  await expect(page.getByRole('dialog', { name: 'Lighting helper' }).getByText(/Please contact the store's support team/)).toBeVisible()
  await expect(page.getByRole('link', { name: 'Contact support', exact: true })).toHaveAttribute('href', 'mailto:help@client-shop.example')
  await page.setViewportSize({ width: 390, height: 844 })
  const panel = await page.getByRole('dialog', { name: 'Lighting helper' }).boundingBox()
  expect(panel?.width).toBeLessThan(390)
  await page.getByLabel('Your message', { exact: true }).press('Escape')
  await expect(page.getByRole('button', { name: 'Chat with us', exact: true })).toBeFocused()
  expect(errors).toEqual([])
})
