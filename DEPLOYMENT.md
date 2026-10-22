# Deploying CommercePilot AI

The project has two parts:

* **`frontend/`** — React + TypeScript, built by Vite into static files.
* **`commercepilot/`** — FastAPI backend, imported by `api/index.py` for Vercel
  or served with Uvicorn anywhere else.

```
GitHub ──► Vercel
             build: npm run build        → public/  (static UI)
             function: api/index.py      → /api/*   (FastAPI)
```

One origin serves both, so no CORS configuration or API base URL is needed in
production.

---

## 1. Local

```bash
python -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                # optional: add LLM_API_KEY

# terminal 1 — API
uvicorn commercepilot.api:app --reload --port 8000

# terminal 2 — UI with hot reload
cd frontend
npm ci
npm run dev                         # http://localhost:3000
```

Vite proxies `/api` to `http://127.0.0.1:8000` (override with `VITE_API_TARGET`),
so the browser only talks to the exposed origin.

To serve the production build from FastAPI instead:

```bash
cd frontend && npm run build && cd ..
python app.py                       # http://localhost:8000  (UI + API)
```

Run the checks with `pip install -r requirements-dev.txt && pytest -q`, then
`cd frontend && npx tsc -b && npm run build`.

---

## 2. Vercel (single project, free plan)

1. Push the repository to GitHub.
2. Vercel → **Add New…** → **Project** → import the repository.
3. Keep the defaults; [`vercel.json`](vercel.json) and
   [`package.json`](package.json) already define the build.
4. Add optional environment variables (§3), then **Deploy**.

| Setting | Value |
|---|---|
| Framework preset | *Other* |
| Root directory | repository root |
| Build command | `npm run build` |
| Output directory | `public` |
| Install command | default (`npm install`) |
| Serverless function | `api/index.py` (FastAPI) |
| Rewrites | `/api/(.*)` → `api/index.py`, everything else → `index.html` |

`api/index.py` sets `DB_PATH=/tmp/commercepilot.sqlite3` because `/tmp` is the
only writable directory in a function. The Python dependencies come from
`requirements.txt` at the repository root.

### Verify the deployment

```bash
curl https://<project>.vercel.app/api/health
# {"status":"ok","service":"commercepilot-ai","version":"1.0.0","llm_mode":"fallback","projects":0}

curl -I https://<project>.vercel.app/          # 200 text/html
python scripts/verify_deployment.py --base https://<project>.vercel.app
```

The smoke test checks the UI page, the health endpoint, sample-data labelling,
an example project through the full workflow, the storefront export, the
simulated campaign label and the assistant.

---

## 3. Environment variables

Only `LLM_API_KEY` changes behaviour materially; everything else is optional and
the app works without it.

| Name | Required | Notes |
|---|---|---|
| `LLM_API_KEY` | no | Groq key (console.groq.com/keys). Without it: labelled templates |
| `LLM_PROVIDER` | no | `groq` (default), `openai`, `openrouter`, `mistral`, or any compatible provider |
| `LLM_BASE_URL` | no | Override for a self-hosted / Ollama endpoint |
| `LLM_MODEL` | no | Cheap model for every task (default `openai/gpt-oss-20b`) |
| `LLM_MODEL_STRONG` | no | Optional stronger model for storefront and ad copy only |
| `AI_MONTHLY_CAP_USD` | no | Hard monthly cap, default `25`; `0` disables |
| `AI_BUDGET_WARN_PCT` | no | Warning threshold, default `80` |
| `SERPER_API_KEY` | no | Google-style search results; free keyless `ddgs` is the default |
| `DB_PATH` | no | SQLite file path (see §5 for persistence) |
| `CORS_ORIGINS` | no | Only when the UI is served from a different origin than the API |
| `VITE_API_BASE_URL` | no | Build-time API origin for a split deployment; empty = same origin |
| `META_*`, `SHOPIFY_*` | no | Optional; server-side only, never sent to the browser |

Never commit real values. Locally they belong in `.env`; on Vercel use the
project's Environment Variables page and redeploy after a change.

---

## 4. Free-tier limits you should know

| Limit | Effect | Mitigation |
|---|---|---|
| Ephemeral function filesystem | SQLite in `/tmp` resets on cold start/redeploy | Click **Explore the example project** on Overview to rebuild the demo; see §5 for persistence |
| 60 s function duration (`maxDuration`) | A full workflow plus live search could approach it | Keep research limits modest; the UI runs steps individually too |
| Function cold starts | First request after idle is slower | Open the URL before a demo |
| 250 MB function bundle | Fine here: the Python dependencies are small | — |
| Groq free tier | Rate limits, not spend | The app retries on 429, then falls back to templates with a visible label |

The frontend bundle is a static asset, so it is served from Vercel's edge cache
and is unaffected by cold starts.

---

## 5. Persistent data / self-hosting

SQLite needs a writable, persistent disk. Any host that can run a Python process
and build the frontend (Node 20+) works:

```bash
npm ci --prefix frontend && npm run build --prefix frontend
pip install -r requirements.txt
python app.py                       # binds 0.0.0.0:$PORT
```

Set `DB_PATH=/data/commercepilot.sqlite3` on a mounted disk and keep the default
health check `/api/health`. If the host cannot run Node, build `frontend/dist`
in CI and deploy it as an artifact — `app.py` serves that directory automatically
and falls back to `index.html` for client-side routes.

Alternatively, deploy the frontend to any static host and the API separately,
then build the UI with `VITE_API_BASE_URL=https://api.example.com` and set
`CORS_ORIGINS` on the API to the UI origin.

---

## 6. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `ModuleNotFoundError: commercepilot` | The function was deployed from a subdirectory; `api/index.py` expects the repository root |
| UI loads but every action fails | Check `/api/health`. A rewritten `/api/*` that returns HTML means the rewrite is missing |
| Blank page on a deep link | The SPA rewrite to `index.html` is missing in `vercel.json` |
| `llm_mode: fallback` unexpectedly | `LLM_API_KEY` is unset/blank on the platform; env vars are read at start, so redeploy after changing them |
| `AI budget ... has been reached` | `AI_MONTHLY_CAP_USD` reached. Raise it deliberately or wait for next month; features fall back to templates |
| Data disappeared after a deploy | Expected with `/tmp`. See §5 for a persistent disk |
| Vite dev shows a 403 "Blocked request" | The preview hostname must be allowed; set `__VITE_ADDITIONAL_SERVER_ALLOWED_HOSTS` when running `npm run dev` |

---

## 7. What is deliberately not deployed

* No ad platform publishing or Shopify writes — those stay drafts.
* No user accounts yet; the service is single-tenant.
* No external queue, cache or cron job — nothing that would need a paid
  component.
