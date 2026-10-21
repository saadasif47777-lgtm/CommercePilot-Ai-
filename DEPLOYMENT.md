# Deploying CommercePilot AI

CommercePilot AI is **one Python process**: FastAPI serves the JSON API at
`/api`, and Gradio is mounted at `/` for the interface. There is no build step,
no Node.js and no separate frontend service.

```
GitHub ──► Render (free web service) ──► https://<name>.onrender.com
             python app.py
             ├── /            Gradio UI
             ├── /api/*       JSON API
             └── /docs        API reference
```

> **Vercel is not a target.** Serverless functions cannot host a long-lived
> Gradio server (websockets, in-process state). The earlier Vercel setup was
> removed together with the TypeScript frontend.

---

## 1. Local

```bash
python -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                # optional: add LLM_API_KEY
python app.py
```

* UI: <http://localhost:7860>
* API health: <http://localhost:7860/api/health>
* API docs: <http://localhost:7860/docs>

Run the tests with `pip install -r requirements-dev.txt && pytest -q`.

---

## 2. Render (free plan)

### Option A — Blueprint

1. Push this repository to GitHub.
2. Render dashboard → **New +** → **Blueprint** → select the repository.
3. Render reads [`render.yaml`](render.yaml) and creates the web service.
4. Add optional environment variables (below), then deploy.

### Option B — manual Web Service

| Field | Value |
|---|---|
| Name | `commercepilot-ai` |
| Language | Python 3 |
| Root Directory | *repository root* |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `python app.py` |
| Health Check Path | `/api/health` |
| Instance Type | Free |

`app.py` binds to `0.0.0.0` and reads `PORT`, which Render supplies.

### Verify the deployment

```bash
curl https://<name>.onrender.com/api/health
# {"status":"ok","service":"commercepilot-ai","version":"1.0.0","llm_mode":"fallback","projects":0}

python scripts/verify_deployment.py --base https://<name>.onrender.com
```

The smoke test checks the UI page, the health endpoint, sample-data labelling,
an example project through the full workflow, the storefront export and the
assistant.

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
| `DB_PATH` | no | SQLite file path. Use `/data/commercepilot.sqlite3` with a disk |
| `PYTHON_VERSION` | recommended | `3.12` |
| `CORS_ORIGINS` | no | Only for external API clients; the UI is same-origin |
| `META_*`, `SHOPIFY_*` | no | Optional; server-side only, never sent to the browser |

Never commit real values. Locally they belong in `.env`; on Render use the
dashboard's Environment tab (blueprint entries marked `sync: false` prompt you).

---

## 4. Free-tier limits you should know

| Limit | Effect | Mitigation |
|---|---|---|
| Sleeps after ~15 idle minutes | First request takes ~1 minute | Open the URL before a demo |
| Ephemeral filesystem | SQLite resets on restart/redeploy | Click **Create example project**; or attach a disk + `DB_PATH` |
| 512 MB RAM | Fine for this app; large concurrent workflows could be tight | Keep research limits modest |
| No background workers | Everything is request-driven | By design |
| Groq free tier | Rate limits, not spend | The app retries on 429, then falls back to templates with a visible label |

Other free hosts that can run a long-lived Python server (for example a Hugging
Face Space) also work; the app reads `PORT` and binds `0.0.0.0`, so no code
changes are needed.

---

## 5. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `ModuleNotFoundError: commercepilot` | Start command was run from a subdirectory, or the repo was deployed with a Root Directory other than the root |
| `Address already in use` | Another process owns the port; stop it or set `PORT` |
| UI loads but every action fails | Check `/api/health`; if the app is waking up, retry after a minute |
| `llm_mode: fallback` unexpectedly | `LLM_API_KEY` is unset or blank on the platform; env vars are read at start, so redeploy after changing them |
| Storefront preview blank | Generate the storefront first; the preview is the exported page served from `/api/projects/<id>/store/export` |
| `AI budget ... has been reached` | `AI_MONTHLY_CAP_USD` reached. Raise it deliberately or wait for the next month; features fall back to templates |
| Data disappeared after a deploy | Expected on the free plan (no persistent disk). See §4 |

---

## 6. What is deliberately not deployed

* No ad platform publishing or Shopify writes — those stay drafts.
* No user accounts yet; the service is single-tenant.
* No external queue, cache or cron job — nothing that would need a paid
  component.
