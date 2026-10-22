/**
 * Interactive storefront renderer.
 *
 * Renders the Pydantic-validated WebsiteSpec with reusable React components —
 * no generated code is executed. The preview is fully interactive: catalog
 * search/filter, product detail, quantity controls, add to cart and a cart
 * drawer with subtotal calculation.
 */
import { useMemo, useState } from 'react'
import type { CSSProperties } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import type {
  BenefitsSection, FaqSection, FeaturedSection, FooterSection, HeaderSection, HeroSection,
  Product, ProductDetailSection, ReviewsSection, Section, WebsiteSpec,
} from '../types'
import { money } from './ProductCards'

type CartItem = { product: Product; qty: number }

export const FONT_STACKS: Record<string, string> = {
  serif: "'Fraunces', Georgia, serif",
  display: "'Inter', 'Helvetica Neue', Arial, sans-serif",
  sans: "'Inter', -apple-system, 'Segoe UI', Roboto, sans-serif",
  system: "-apple-system, 'Segoe UI', Roboto, sans-serif",
}
const SECTION_GAP: Record<string, string> = { compact: '34px', comfortable: '64px', airy: '104px' }
const SECTION_PAD: Record<string, string> = { compact: '34px', comfortable: '58px', airy: '84px' }

export function contrastText(hex: string): string {
  const c = hex.replace('#', '')
  if (c.length !== 6) return '#ffffff'
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(c.slice(i, i + 2), 16))
  return (0.299 * r + 0.587 * g + 0.114 * b) / 255 > 0.62 ? '#0b0b0b' : '#ffffff'
}
function alpha(hex: string, a: number): string {
  const c = hex.replace('#', '')
  if (c.length !== 6) return hex
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(c.slice(i, i + 2), 16))
  return `rgba(${r}, ${g}, ${b}, ${a})`
}
const wrapStyle = (device: string): CSSProperties => ({ maxWidth: 1120, margin: '0 auto', padding: device === 'mobile' ? '0 18px' : '0 28px' })
const sectionStyle = (d: WebsiteSpec['design']): CSSProperties => ({ padding: `${SECTION_PAD[d.density]} 0`, background: d.background })

function heroStyle(style: string, d: WebsiteSpec['design'], device: string): CSSProperties {
  const base: CSSProperties = {
    display: 'grid', gap: 34, padding: `${SECTION_PAD[d.density]} 0`, alignItems: 'center',
    maxWidth: 1120, margin: '0 auto',
    paddingLeft: device === 'mobile' ? 18 : 28, paddingRight: device === 'mobile' ? 18 : 28,
    background: d.background,
  }
  if (style === 'centered' || style === 'minimal') return { ...base, gridTemplateColumns: '1fr', justifyItems: 'center', textAlign: 'center' }
  if (style === 'editorial_split') return { ...base, gridTemplateColumns: device === 'mobile' ? '1fr' : '1fr 1fr' }
  if (style === 'boxed') return { ...base, gridTemplateColumns: '1fr', background: d.surface, borderRadius: d.radius }
  return { ...base, gridTemplateColumns: device === 'mobile' ? '1fr' : '1.05fr 0.95fr' }
}

export function StorefrontPreview({ spec, device = 'desktop' }: { spec: WebsiteSpec; device?: 'desktop' | 'mobile' }) {
  const d = spec.design
  const sections = spec.sections
  const product = spec.product
  const currency = spec.currency || 'PKR'

  const [cart, setCart] = useState<CartItem[]>([])
  const [cartOpen, setCartOpen] = useState(false)
  const [qty, setQty] = useState(1)
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState('all')
  const [mobileNav, setMobileNav] = useState(false)
  const [openFaq, setOpenFaq] = useState<number | null>(0)

  // Sections are a typed list in the spec; look them up by type once here so
  // the JSX below can stay declarative.
  const byType = <T extends Section>(type: string) => sections.find((s) => s.type === type) as T | undefined
  const header = byType<HeaderSection>('header')
  const hero = byType<HeroSection>('hero')
  const featured = byType<FeaturedSection>('featured')
  const detail = byType<ProductDetailSection>('product_detail')
  const benefits = byType<BenefitsSection>('benefits')
  const reviews = byType<ReviewsSection>('reviews')
  const faq = byType<FaqSection>('faq')
  const footer = byType<FooterSection>('footer')

  const motionEnabled = d.animation !== 'none'
  const anim = motionEnabled
    ? {
        initial: { opacity: 0, y: 14 },
        whileInView: { opacity: 1, y: 0 },
        viewport: { once: true, margin: '-40px' },
        transition: { duration: d.animation === 'moderate' ? 0.5 : 0.35 },
      }
    : {}

  // Client-side catalog search/filter for the preview only. The store data
  // itself is fixed in the generated specification.
  const catalog = useMemo(() => {
    if (!featured || !featured.show_catalog || !spec.sample_catalog?.length) return null
    const cats = ['all', ...new Set(spec.sample_catalog.map((p) => p.category))]
    let rows = spec.sample_catalog
    if (category !== 'all') rows = rows.filter((p) => p.category === category)
    if (query.trim()) {
      const q = query.toLowerCase()
      rows = rows.filter((p) => p.title.toLowerCase().includes(q) || p.description.toLowerCase().includes(q))
    }
    return { rows, cats }
  }, [featured, spec.sample_catalog, category, query])

  // Cart operations are local demo state: nothing is sent to a server or
  // checkout, which is why the preview is safe to click through.
  const addToCart = (p: Product, quantity = 1) => {
    setCart((c) => {
      const found = c.find((i) => i.product.id === p.id)
      if (found) return c.map((i) => (i.product.id === p.id ? { ...i, qty: i.qty + quantity } : i))
      return [...c, { product: p, qty: quantity }]
    })
    setCartOpen(true)
  }

  const subtotal = cart.reduce((sum, i) => sum + (i.product.observed_price ?? 0) * i.qty, 0)
  const count = cart.reduce((sum, i) => sum + i.qty, 0)

  const cardStyle: CSSProperties =
    d.card_style === 'elevated'
      ? { boxShadow: '0 10px 30px rgba(0,0,0,.09)', border: '1px solid transparent' }
      : d.card_style === 'bordered'
        ? { border: '1px solid rgba(0,0,0,.09)' }
        : { border: '1px solid transparent', background: 'transparent' }

  const btn: CSSProperties = {
    background: d.accent_color, color: contrastText(d.accent_color),
    borderRadius: d.radius, border: 'none', cursor: 'pointer',
  }
  const head = (size: number | string): CSSProperties => ({ fontFamily: FONT_STACKS[d.font_heading] ?? FONT_STACKS.serif, fontSize: size })

  const shell: CSSProperties = {
    background: d.background, color: d.text_color, fontFamily: FONT_STACKS[d.font_body] ?? FONT_STACKS.sans,
    ['--sp' as string]: SECTION_GAP[d.density],
    maxWidth: device === 'mobile' ? '420px' : '100%',
    margin: device === 'mobile' ? '0 auto' : undefined,
    borderRadius: device === 'mobile' ? '18px' : undefined,
    overflow: 'hidden' as const,
    border: device === 'mobile' ? '1px solid #e3e6e3' : undefined,
  }

  const nav = (header?.nav as unknown as { label: string; href: string }[] | undefined) ?? []

  return (
    <div style={shell}>
      {/* ------------------------------------------------------------ header */}
      {header && header.visible !== false && (
        <header style={{ position: 'sticky', top: 0, zIndex: 30, background: alpha(d.background, 0.94), borderBottom: '1px solid rgba(0,0,0,.07)', backdropFilter: 'blur(8px)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 18, padding: '0 20px', height: 60 }}>
            <a href="#top" style={{ ...head(17), fontWeight: 700, color: d.primary_color, textDecoration: 'none' }}>{header.logo_text}</a>
            <nav style={{ display: device === 'mobile' ? 'none' : 'flex', gap: 16, flex: 1 }}>
              {nav.map((n) => (
                <a key={n.label} href={n.href} style={{ fontSize: 13.5, color: d.text_color, opacity: 0.75, textDecoration: 'none' }}>{n.label}</a>
              ))}
            </nav>
            <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 10 }}>
              {device === 'mobile' && (
                <button onClick={() => setMobileNav((v) => !v)} aria-label="Menu" style={{ background: 'none', border: 'none', fontSize: 20, color: d.text_color, cursor: 'pointer' }}>☰</button>
              )}
              <button onClick={() => setCartOpen(true)} style={{ ...btn, padding: '8px 14px', fontSize: 13, fontWeight: 600 }}>Cart ({count})</button>
            </div>
          </div>
          <AnimatePresence>
            {mobileNav && device === 'mobile' && (
              <motion.nav initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} style={{ overflow: 'hidden', borderTop: '1px solid rgba(0,0,0,.06)', background: d.background }}>
                <div style={{ display: 'grid', gap: 2, padding: 10 }}>
                  {nav.map((n) => (
                    <a key={n.label} href={n.href} onClick={() => setMobileNav(false)} style={{ padding: '10px 12px', borderRadius: d.radius, fontSize: 14, color: d.text_color, textDecoration: 'none' }}>{n.label}</a>
                  ))}
                </div>
              </motion.nav>
            )}
          </AnimatePresence>
        </header>
      )}

      {/* -------------------------------------------------------------- hero */}
      {hero && hero.visible !== false && (
        <motion.section id="top" {...anim} style={heroStyle(hero.style, d, device)}>
          <div style={{ flexBasis: '52%', maxWidth: 620 }}>
            {hero.badge && (
              <span style={{ display: 'inline-block', background: d.surface, color: d.primary_color, borderRadius: 999, padding: '5px 13px', fontSize: 11.5, letterSpacing: '0.05em', marginBottom: 14 }}>{hero.badge}</span>
            )}
            <h1 style={{ ...head(device === 'mobile' ? 30 : 'clamp(28px, 4vw, 44px)'), lineHeight: 1.1, margin: 0 }}>{hero.headline}</h1>
            <p style={{ marginTop: 14, fontSize: 15.5, opacity: 0.82, lineHeight: 1.65 }}>{hero.subheadline}</p>
            <div style={{ display: 'flex', gap: 10, marginTop: 22, flexWrap: 'wrap' }}>
              <button onClick={() => product && addToCart(product)} style={{ ...btn, padding: '12px 22px', fontSize: 14, fontWeight: 600 }}>{hero.cta_label}</button>
              <a href="#benefits" style={{ padding: '12px 20px', borderRadius: d.radius, border: `1px solid ${d.primary_color}`, color: d.primary_color, fontSize: 14, fontWeight: 600, textDecoration: 'none' }}>{hero.secondary_cta_label}</a>
            </div>
          </div>
          <div style={{ flexBasis: '42%' }}>
            <ProductTile product={product} currency={currency} d={d} big head={head} />
          </div>
        </motion.section>
      )}

      {/* ---------------------------------------------------------- featured */}
      {featured && featured.visible !== false && (
        <motion.section id="product" {...anim} style={sectionStyle(d)}>
          <div style={wrapStyle(device)}>
            <h2 style={{ ...head(22), marginBottom: 6 }}>{featured.title}</h2>
            {product && (
              <div style={{ display: 'grid', gap: 22, gridTemplateColumns: device === 'mobile' ? '1fr' : '0.9fr 1.1fr', alignItems: 'start' }}>
                <ProductTile product={product} currency={currency} d={d} big head={head} />
                <div>
                  <p style={{ fontSize: 15, lineHeight: 1.7, opacity: 0.88 }}>{product.description}</p>
                  <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginTop: 16, flexWrap: 'wrap' }}>
                    <span style={{ ...head(24), color: d.primary_color }}>{money(product.observed_price, currency)}</span>
                    <QtyStepper qty={qty} setQty={setQty} radius={d.radius} />
                    <button onClick={() => addToCart(product, qty)} style={{ ...btn, padding: '11px 20px', fontSize: 14, fontWeight: 600 }}>Add to cart</button>
                  </div>
                  {product.is_sample_data && (
                    <p style={{ marginTop: 12, fontSize: 11.5, opacity: 0.6 }}>Sample/demo product data — price and details are illustrative.</p>
                  )}
                </div>
              </div>
            )}

            {catalog && (
              <div style={{ marginTop: 34 }}>
                {featured.catalog_filter && (
                  <div style={{ display: 'flex', gap: 10, marginBottom: 16, flexWrap: 'wrap' }}>
                    <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search products…" style={{ flex: '1 1 200px', padding: '9px 13px', borderRadius: d.radius, border: '1px solid rgba(0,0,0,.12)', fontSize: 13.5, background: d.background, color: d.text_color }} />
                    <select value={category} onChange={(e) => setCategory(e.target.value)} style={{ padding: '9px 12px', borderRadius: d.radius, border: '1px solid rgba(0,0,0,.12)', fontSize: 13.5, background: d.background, color: d.text_color }}>
                      {catalog.cats.map((c) => (<option key={c} value={c}>{c === 'all' ? 'All categories' : c}</option>))}
                    </select>
                  </div>
                )}
                {catalog.rows.length === 0 ? (
                  <div style={{ padding: 26, textAlign: 'center', border: '1px dashed rgba(0,0,0,.15)', borderRadius: d.radius, opacity: 0.7 }}>
                    No products match “{query}”. Try another search.
                  </div>
                ) : (
                  <div style={{ display: 'grid', gap: 16, gridTemplateColumns: `repeat(auto-fill, minmax(${device === 'mobile' ? 150 : 210}px, 1fr))` }}>
                    {catalog.rows.map((p) => (
                      <ProductCardMini key={p.id} product={p} currency={currency} d={d} cardStyle={cardStyle} onAdd={() => addToCart(p)} />
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </motion.section>
      )}

      {/* ------------------------------------------------------------ detail */}
      {detail && detail.visible !== false && (
        <motion.section {...anim} style={{ ...sectionStyle(d), background: d.surface }}>
          <div style={wrapStyle(device)}>
            <h2 style={{ ...head(22), marginBottom: 14 }}>{detail.title}</h2>
            <div style={{ display: 'grid', gap: 24, gridTemplateColumns: device === 'mobile' ? '1fr' : '1.2fr 0.8fr' }}>
              <div>
                <p style={{ fontSize: 15, lineHeight: 1.75, opacity: 0.85 }}>{detail.description}</p>
                <ul style={{ marginTop: 14, paddingLeft: 18, fontSize: 14.5, lineHeight: 1.9, opacity: 0.85 }}>
                  {(detail.bullets as unknown as string[]).map((b, i) => (<li key={i}>{b}</li>))}
                </ul>
              </div>
              <div style={{ borderRadius: d.radius, padding: 20, background: d.background, ...cardStyle }}>
                <p style={{ ...head(15), marginBottom: 8 }}>Good to know</p>
                <p style={{ fontSize: 13, lineHeight: 1.7, opacity: 0.8 }}>Dispatch in 24–48 hours · Cash on delivery available · 7-day returns on unopened items.</p>
              </div>
            </div>
          </div>
        </motion.section>
      )}

      {/* ---------------------------------------------------------- benefits */}
      {benefits && benefits.visible !== false && (
        <motion.section id="benefits" {...anim} style={sectionStyle(d)}>
          <div style={wrapStyle(device)}>
            <h2 style={{ ...head(22), marginBottom: 18 }}>{benefits.title}</h2>
            <div style={{ display: 'grid', gap: 16, gridTemplateColumns: `repeat(auto-fit, minmax(${device === 'mobile' ? 180 : 230}px, 1fr))` }}>
              {(benefits.items as unknown as { title: string; text: string }[]).map((b, i) => (
                <div key={i} style={{ borderRadius: d.radius, padding: 22, background: d.surface, ...cardStyle }}>
                  <span style={{ display: 'inline-flex', height: 30, width: 30, alignItems: 'center', justifyContent: 'center', borderRadius: 999, background: alpha(d.accent_color, 0.16), color: d.primary_color, fontSize: 14 }}>✓</span>
                  <p style={{ ...head(15), margin: '10px 0 6px' }}>{b.title}</p>
                  <p style={{ fontSize: 13.5, lineHeight: 1.65, opacity: 0.78 }}>{b.text}</p>
                </div>
              ))}
            </div>
          </div>
        </motion.section>
      )}

      {/* ----------------------------------------------------------- reviews */}
      {reviews && reviews.visible !== false && (
        <motion.section id="reviews" {...anim} style={{ ...sectionStyle(d), background: d.surface }}>
          <div style={wrapStyle(device)}>
            <h2 style={{ ...head(22), marginBottom: 6 }}>{reviews.title}</h2>
            <p style={{ fontSize: 11.5, opacity: 0.6, marginBottom: 16 }}>{reviews.sample_label}</p>
            <div style={{ display: 'grid', gap: 16, gridTemplateColumns: `repeat(auto-fit, minmax(${device === 'mobile' ? 180 : 230}px, 1fr))` }}>
              {(reviews.items as unknown as { name: string; rating: number; text: string }[]).map((r, i) => (
                <div key={i} style={{ borderRadius: d.radius, padding: 20, background: d.background, ...cardStyle }}>
                  <p style={{ color: d.accent_color, letterSpacing: 2, fontSize: 13 }}>{'★'.repeat(r.rating)}{'☆'.repeat(5 - r.rating)}</p>
                  <p style={{ fontSize: 13.5, lineHeight: 1.65, margin: '10px 0', opacity: 0.85 }}>{r.text}</p>
                  <p style={{ fontSize: 12, opacity: 0.6 }}>{r.name}</p>
                </div>
              ))}
            </div>
          </div>
        </motion.section>
      )}

      {/* ---------------------------------------------------------------- faq */}
      {faq && faq.visible !== false && (
        <motion.section id="faq" {...anim} style={sectionStyle(d)}>
          <div style={{ ...wrapStyle(device), maxWidth: 760 }}>
            <h2 style={{ ...head(22), marginBottom: 14 }}>{faq.title}</h2>
            {(faq.items as unknown as { q: string; a: string }[]).map((item, i) => (
              <div key={i} style={{ borderBottom: '1px solid rgba(0,0,0,.09)' }}>
                <button onClick={() => setOpenFaq(openFaq === i ? null : i)} style={{ width: '100%', display: 'flex', justifyContent: 'space-between', gap: 12, padding: '15px 2px', background: 'none', border: 'none', cursor: 'pointer', textAlign: 'left', fontSize: 14.5, fontWeight: 600, color: d.text_color }}>
                  {item.q}
                  <span style={{ opacity: 0.55 }}>{openFaq === i ? '−' : '+'}</span>
                </button>
                <AnimatePresence>
                  {openFaq === i && (
                    <motion.p initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} style={{ margin: 0, padding: '0 2px 15px', fontSize: 14, lineHeight: 1.7, opacity: 0.8, overflow: 'hidden' }}>
                      {item.a}
                    </motion.p>
                  )}
                </AnimatePresence>
              </div>
            ))}
          </div>
        </motion.section>
      )}

      {/* ------------------------------------------------------------- footer */}
      {footer && footer.visible !== false && (
        <footer style={{ background: d.primary_color, color: '#e9f3ee', padding: '44px 0 24px', marginTop: 'var(--sp)' }}>
          <div style={wrapStyle(device)}>
            <div style={{ display: 'grid', gap: 24, gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))' }}>
              {(footer.columns as unknown as { title: string; links: string[] }[]).map((c, i) => (
                <div key={i}>
                  <p style={{ ...head(14), marginBottom: 10 }}>{c.title}</p>
                  {c.links.map((l) => (
                    <a key={l} style={{ display: 'block', fontSize: 13, opacity: 0.78, textDecoration: 'none', color: 'inherit', padding: '3px 0' }}>{l}</a>
                  ))}
                </div>
              ))}
            </div>
            <p style={{ marginTop: 28, fontSize: 11.5, opacity: 0.6 }}>{footer.note}</p>
          </div>
        </footer>
      )}

      {/* ------------------------------------------------------- cart drawer */}
      <AnimatePresence>
        {cartOpen && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={() => setCartOpen(false)} style={{ position: 'fixed', inset: 0, background: 'rgba(11,11,11,.42)', zIndex: 60, display: 'flex', justifyContent: 'flex-end' }}>
            <motion.aside
              initial={{ x: '100%' }} animate={{ x: 0 }} exit={{ x: '100%' }}
              transition={{ type: 'spring', stiffness: 320, damping: 32 }}
              onClick={(e) => e.stopPropagation()}
              style={{ width: 'min(380px, 92vw)', height: '100%', background: d.background, color: d.text_color, padding: 22, display: 'flex', flexDirection: 'column', boxShadow: '-12px 0 40px rgba(0,0,0,.18)' }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <h3 style={{ ...head(18), margin: 0 }}>Your cart</h3>
                <button onClick={() => setCartOpen(false)} style={{ background: 'none', border: 'none', fontSize: 18, cursor: 'pointer', color: 'inherit' }} aria-label="Close cart">✕</button>
              </div>

              <div style={{ flex: 1, overflowY: 'auto', margin: '16px 0' }}>
                {cart.length === 0 ? (
                  <div style={{ padding: '38px 8px', textAlign: 'center', opacity: 0.65, fontSize: 14 }}>
                    Your cart is empty.<br />Add the featured product to see the subtotal update.
                  </div>
                ) : (
                  <div style={{ display: 'grid', gap: 12 }}>
                    {cart.map((item) => (
                      <div key={item.product.id} style={{ display: 'flex', gap: 12, alignItems: 'center', padding: 12, borderRadius: d.radius, background: d.surface }}>
                        <div style={{ flex: 1 }}>
                          <p style={{ fontSize: 13.5, fontWeight: 600, margin: 0 }}>{item.product.title}</p>
                          <p style={{ fontSize: 12.5, opacity: 0.7, margin: '3px 0 0' }}>{money(item.product.observed_price, currency)} × {item.qty}</p>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                          <button onClick={() => setCart((c) => c.map((i) => i.product.id === item.product.id ? { ...i, qty: Math.max(1, i.qty - 1) } : i))} style={miniBtn} aria-label="Decrease">−</button>
                          <span style={{ minWidth: 18, textAlign: 'center', fontSize: 13.5 }}>{item.qty}</span>
                          <button onClick={() => setCart((c) => c.map((i) => i.product.id === item.product.id ? { ...i, qty: i.qty + 1 } : i))} style={miniBtn} aria-label="Increase">+</button>
                        </div>
                        <button onClick={() => setCart((c) => c.filter((i) => i.product.id !== item.product.id))} style={{ ...miniBtn, border: 'none', background: 'none', opacity: 0.5 }} aria-label={`Remove ${item.product.title}`}>✕</button>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div style={{ borderTop: '1px solid rgba(0,0,0,.1)', paddingTop: 14 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 14.5 }}>
                  <span style={{ opacity: 0.75 }}>Subtotal</span>
                  <strong style={{ ...head(17) }}>{money(subtotal, currency)}</strong>
                </div>
                <p style={{ fontSize: 11.5, opacity: 0.6, margin: '6px 0 12px' }}>Shipping and taxes calculated at checkout. Demo store — checkout is not connected to payments.</p>
                <button disabled={!cart.length} style={{ ...btn, width: '100%', padding: 13, fontSize: 14, fontWeight: 700, cursor: cart.length ? 'pointer' : 'not-allowed', opacity: cart.length ? 1 : 0.5 }}>
                  Checkout (demo)
                </button>
              </div>
            </motion.aside>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

/* ------------------------------------------------------------------ pieces */

function ProductTile({ product, currency, d, big = false, head }: { product?: Product | null; currency: string; d: WebsiteSpec['design']; big?: boolean; head: (n: number) => CSSProperties }) {
  if (!product) {
    return (
      <div style={{ borderRadius: d.radius, background: d.surface, minHeight: big ? 240 : 160, display: 'grid', placeItems: 'center', opacity: 0.6, fontSize: 13 }}>
        No product selected
      </div>
    )
  }
  return (
    <div style={{ borderRadius: d.radius, background: d.primary_color, color: '#fff', minHeight: big ? 250 : 160, padding: 26, display: 'flex', flexDirection: 'column', justifyContent: 'flex-end', gap: 6 }}>
      <span style={{ fontSize: 10.5, textTransform: 'uppercase', letterSpacing: '0.09em', opacity: 0.72 }}>{product.category}</span>
      <strong style={{ ...head(big ? 20 : 16), lineHeight: 1.25 }}>{product.title}</strong>
      <em style={{ fontStyle: 'normal', color: d.accent_color, fontWeight: 600, fontSize: 15 }}>{money(product.observed_price, currency)}</em>
    </div>
  )
}

function ProductCardMini({ product, currency, d, cardStyle, onAdd }: { product: Product; currency: string; d: WebsiteSpec['design']; cardStyle: CSSProperties; onAdd: () => void }) {
  return (
    <div
      style={{ borderRadius: d.radius, padding: 14, background: d.background, ...cardStyle, transition: 'transform .18s ease, box-shadow .18s ease' }}
      onMouseEnter={(e) => (e.currentTarget.style.transform = 'translateY(-2px)')}
      onMouseLeave={(e) => (e.currentTarget.style.transform = 'translateY(0)')}
    >
      <div style={{ height: 84, borderRadius: Math.max(6, d.radius - 4), background: d.surface, display: 'grid', placeItems: 'center', marginBottom: 10, fontSize: 11, opacity: 0.5 }}>{product.category}</div>
      <p style={{ fontSize: 13, fontWeight: 600, margin: 0, lineHeight: 1.35 }}>{product.title}</p>
      <p style={{ fontSize: 13, color: d.primary_color, fontWeight: 700, margin: '6px 0 10px' }}>{money(product.observed_price, currency)}</p>
      <button onClick={onAdd} style={{ background: d.accent_color, color: contrastText(d.accent_color), border: 'none', borderRadius: d.radius, padding: '9px 12px', fontSize: 12.5, fontWeight: 600, cursor: 'pointer', width: '100%' }}>Add to cart</button>
    </div>
  )
}

function QtyStepper({ qty, setQty, radius }: { qty: number; setQty: (n: number) => void; radius: number }) {
  const b: CSSProperties = { width: 32, height: 36, borderRadius: radius, border: '1px solid rgba(0,0,0,.14)', background: 'transparent', cursor: 'pointer', fontSize: 15, color: 'inherit' }
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <button style={b} onClick={() => setQty(Math.max(1, qty - 1))} aria-label="Decrease quantity">−</button>
      <span style={{ minWidth: 20, textAlign: 'center', fontSize: 14.5 }}>{qty}</span>
      <button style={b} onClick={() => setQty(qty + 1)} aria-label="Increase quantity">+</button>
    </div>
  )
}

const miniBtn: CSSProperties = {
  width: 26, height: 26, borderRadius: 8, border: '1px solid rgba(0,0,0,.14)',
  background: 'transparent', cursor: 'pointer', fontSize: 14, lineHeight: 1, color: 'inherit',
}
