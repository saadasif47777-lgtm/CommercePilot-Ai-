/* CommercePilot Shopify chat. Public configuration only; never contains admin tokens. */
(() => {
  'use strict'
  const script = document.currentScript
  const widget = script?.dataset.widget
  if (!widget || !/^[a-f0-9]{32}$/.test(widget)) return
  const mountId = `commercepilot-support-${widget}`
  if (document.getElementById(mountId)) return
  const base = new URL(script.src).origin
  const endpoint = `${base}/api/support/widget/${widget}`
  const storageKey = `${mountId}:session`
  let token = '', busy = false
  try { token = sessionStorage.getItem(storageKey) || '' } catch { /* optional storage */ }

  async function api(path, body) {
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), 55000)
    try {
      const response = await fetch(`${endpoint}/${path}`, {
        method: body === undefined ? 'GET' : 'POST', credentials: 'omit', signal: controller.signal,
        ...(body === undefined ? {} : { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
      })
      const data = await response.json()
      if (!response.ok) {
        if (response.status === 401) {
          token = ''
          try { sessionStorage.removeItem(storageKey) } catch { /* optional storage */ }
        }
        throw new Error(typeof data.detail === 'string' ? data.detail : 'Please try again or contact the store.')
      }
      return data
    } finally { clearTimeout(timer) }
  }

  const element = (tag, text, className) => {
    const node = document.createElement(tag)
    if (text) node.textContent = text
    if (className) node.className = className
    return node
  }
  function link(text, href) {
    const node = element('a', text)
    try {
      if (new URL(href).protocol !== 'https:') return element('span', text)
      node.href = href; node.target = '_blank'; node.rel = 'noopener noreferrer'
    } catch { return element('span', text) }
    return node
  }

  async function start() {
    let config
    try { config = await api('config') } catch { return }
    const host = element('div'); host.id = mountId
    const root = host.attachShadow({ mode: 'open' })
    const style = element('style')
    style.textContent = `
      :host{all:initial;position:fixed;bottom:20px;right:20px;z-index:2147483000;font-family:system-ui,-apple-system,sans-serif;color:#17221d;font-size:14px;line-height:1.5}
      *{box-sizing:border-box}button,input{font:inherit}button,a{touch-action:manipulation}button{cursor:pointer}button:disabled{cursor:wait;opacity:.65}
      button:focus-visible,a:focus-visible,input:focus-visible{outline:3px solid #659cfd;outline-offset:2px}[hidden]{display:none!important}
      .launcher{background:var(--accent);color:white;border:0;border-radius:30px;padding:14px 20px;box-shadow:0 4px 20px #0003;font-weight:650}
      .panel{width:370px;height:min(610px,calc(100dvh - 40px));max-width:calc(100vw - 32px);background:white;border:1px solid #dde4df;border-radius:18px;box-shadow:0 12px 55px #0003;display:flex;flex-direction:column;overflow:hidden}
      .header{background:var(--accent);color:white;padding:16px;display:flex;align-items:center;gap:10px}.heading{flex:1;font-size:16px;font-weight:650}.close{border:0;background:transparent;color:inherit;font-size:24px;padding:0 6px}
      .notice{padding:10px 14px;background:#f3f6f4;color:#5c6a62;font-size:11px}.messages{padding:14px;overflow-y:auto;flex:1;min-height:120px}.turn{margin:0 0 12px;padding:12px;border-radius:12px;background:#f2f5f3;white-space:pre-wrap;overflow-wrap:anywhere}.user{background:var(--accent);color:white;margin-left:30px}.reply{margin-right:12px}
      .product{display:flex;gap:10px;padding:10px;margin-top:8px;border:1px solid #dbe3de;border-radius:10px;background:white;white-space:normal}.product img{width:52px;height:60px;object-fit:cover;border-radius:6px}.product p{margin:3px 0;font-size:12px}.product a{font-weight:600}a{color:#174a38;text-decoration:underline}.sources{display:flex;flex-wrap:wrap;gap:8px;margin-top:8px;font-size:12px}
      .status{padding:0 14px;color:#59695f;font-size:12px;min-height:20px}.error{color:#9f2c2c}.retry{border:0;background:transparent;color:inherit;text-decoration:underline;padding:3px}
      form{display:flex;gap:8px;padding:12px;border-top:1px solid #e1e7e3}input{min-width:0;flex:1;border:1px solid #cfd9d2;border-radius:9px;padding:10px;color:#17221d;background:white}.send{background:var(--accent);color:white;border:0;border-radius:9px;padding:10px 14px}
      .footer{display:flex;justify-content:space-between;gap:10px;padding:0 14px 12px;font-size:11px;color:#5c6a62}.reset{border:0;background:none;color:inherit;padding:0;text-decoration:underline}
      @media(max-width:480px){:host{right:12px;bottom:12px}.panel{width:calc(100vw - 24px);max-width:none;height:min(620px,calc(100dvh - 24px))}}
    `
    root.append(style)
    host.style.setProperty('--accent', /^#[a-f0-9]{6}$/i.test(config.accent) ? config.accent : '#174A38')
    const launcher = element('button', 'Chat with us', 'launcher')
    launcher.type = 'button'; launcher.setAttribute('aria-expanded', 'false'); launcher.setAttribute('aria-controls', `${mountId}-panel`)
    const panel = element('section', '', 'panel'); panel.id = `${mountId}-panel`; panel.hidden = true
    panel.setAttribute('role', 'dialog'); panel.setAttribute('aria-label', config.assistant_name)
    const header = element('div', '', 'header')
    const heading = element('div', config.assistant_name, 'heading')
    const close = element('button', '×', 'close'); close.type = 'button'; close.setAttribute('aria-label', 'Close chat')
    header.append(heading, close)
    const messages = element('div', '', 'messages'); messages.setAttribute('role', 'log'); messages.setAttribute('aria-label', 'Conversation'); messages.setAttribute('aria-live', 'polite')
    const status = element('div', '', 'status'); status.setAttribute('role', 'status')
    const form = element('form')
    const input = element('input'); input.type = 'text'; input.maxLength = 1000; input.placeholder = 'Ask about products, shipping or returns'; input.setAttribute('aria-label', 'Your message'); input.autocomplete = 'off'
    const send = element('button', 'Send', 'send'); send.type = 'submit'
    form.append(input, send)
    const footer = element('div', '', 'footer')
    const reset = element('button', 'New conversation', 'reset'); reset.type = 'button'
    footer.append(reset)
    if (config.support_email) {
      const contact = element('a', 'Contact support'); contact.href = `mailto:${config.support_email}`; footer.append(contact)
    }
    panel.append(header, element('div', 'AI assistant · Conversations expire after 24 hours. Please don’t share payment details or sensitive information.', 'notice'), messages, status, form, footer)
    root.append(panel, launcher); document.body.append(host)

    function add(text, kind) { const turn = element('div', text, `turn ${kind}`); messages.append(turn); messages.scrollTop = messages.scrollHeight; return turn }
    add(config.welcome, 'reply')
    const toggle = open => { panel.hidden = !open; launcher.hidden = open; launcher.setAttribute('aria-expanded', String(open)); (open ? input : launcher).focus() }
    launcher.onclick = () => toggle(true); close.onclick = () => toggle(false)
    panel.onkeydown = event => { if (event.key === 'Escape') toggle(false) }
    reset.onclick = () => {
      if (busy) return
      token = ''; try { sessionStorage.removeItem(storageKey) } catch { /* optional storage */ }
      messages.replaceChildren(); status.replaceChildren(); add(config.welcome, 'reply'); input.focus()
    }
    async function submit(message, retry = false) {
      if (!message.trim() || busy) return
      busy = true; input.disabled = true; send.disabled = true; reset.disabled = true
      if (!retry) add(message, 'user')
      status.className = 'status'; status.textContent = 'Thinking…'
      try {
        if (!token) {
          token = (await api('session', {})).session_token
          try { sessionStorage.setItem(storageKey, token) } catch { /* optional storage */ }
        }
        const reply = await api('chat', { message, session_token: token })
        const turn = add(reply.answer, 'reply')
        for (const product of reply.products || []) {
          const card = element('div', '', 'product')
          if (product.image?.startsWith('https://cdn.shopify.com/')) {
            const image = element('img'); image.src = product.image; image.alt = product.title; image.loading = 'lazy'; card.append(image)
          }
          const details = element('div')
          details.append(link(product.title, product.url), element('p', `${product.price !== product.max_price ? 'From ' : ''}${product.currency} ${product.price}`), element('p', 'Check current price and availability on the product page.'))
          card.append(details); turn.append(card)
        }
        const sources = element('div', '', 'sources')
        for (const source of reply.sources || []) if (source.url) sources.append(link(source.title, source.url))
        if (sources.childNodes.length) turn.append(sources)
        status.textContent = ''; input.value = ''; messages.scrollTop = messages.scrollHeight
      } catch (error) {
        status.className = 'status error'
        status.textContent = error.name === 'AbortError' ? 'The reply took too long. Please try again.' : error.message
        const retryButton = element('button', 'Retry message', 'retry'); retryButton.type = 'button'; retryButton.onclick = () => submit(message, true); status.append(retryButton)
      } finally { busy = false; input.disabled = false; send.disabled = false; reset.disabled = false; input.focus() }
    }
    form.onsubmit = event => { event.preventDefault(); submit(input.value.trim()) }
  }
  start()
})()
