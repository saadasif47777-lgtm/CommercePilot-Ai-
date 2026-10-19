# Deploying CommercePilot AI

Target architecture — the two services are deployed separately and joined by one
environment variable:

```
GitHub  ──►  Vercel   (frontend, static React/Vite build)   https://<you>.vercel.app
        └──►  Render   (backend,  Python/FastAPI service)   https://<name>.onrender.com
                                   ▲
        VITE_API_BASE_URL ─────────┘   (baked into the JS bundle at build time)
        CORS_ORIGINS ─────────────────► (backend allow-list, read at runtime)
```

Nothing secret is sent to the browser. `VITE_API_BASE_URL` is a **public origin
URL**, not a credential — `VITE_`-prefixed values are visible in the bundle by
design.

---

## 1. What is in this repository

| Item | Path / value |
|---|---|
| Frontend directory | `frontend/` (React 19 + Vite 7 + TypeScript + Tailwind 4) |
| Frontend install / build | `npm install` → `npm run build` (runs `tsc -b && vite build`) |
| Frontend output | `frontend/dist/` |
| Frontend dev server | `npm run dev` (port 3000, proxies `/api` to the backend) |
| Backend entry point | `backend/main.py`, importable as **`backend.main:app`** |
| Backend dependencies | `requirements.txt` **at the repository root** |
| Backend run (local) | `python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000` |
| Health endpoint | `GET /api/health` |
| API docs | `GET /docs` |
| Tests | `pytest tests/ -q` (111 tests + frontend `npm run build` type-check), `npm run build` |
| Deployment smoke test | `scripts/verify_deployment.py` |
| Environment template | `.env.example` (names only, no values) |
| Render blueprint | `render.yaml` (optional — same settings as §3) |
| Vercel config | `frontend/vercel.json` (SPA deep-link rewrite) |

Run every backend command **from the repository root** — the app is a package
(`backend.main:app`), not a script.

---

## 2. Environment variables

### Backend — Render dashboard → Environment

| Name | Required | Value | Secret? |
|---|---|---|---|
| `CORS_ORIGINS` | **yes** | `https://<your-frontend>.vercel.app` (add local dev origins for testing) | no |
| `PYTHON_VERSION` | recommended | `3.12` (matches local testing) | no |
| `DB_PATH` | only with a disk | `/data/commercepilot.sqlite3` | no |
| `OPENAI_API_KEY` | no | enables LLM copywriting; app works in labelled fallback mode without it | **yes** |
| `SERPER_API_KEY` | no | richer live search; `ddgs` works keyless | **yes** |
| `META_ACCESS_TOKEN`, `META_AD_ACCOUNT_ID`, `META_APP_ID`, `META_APP_SECRET` | no | only for real Meta publishing | **yes** |
| `SHOPIFY_SHOP_DOMAIN`, `SHOPIFY_ADMIN_TOKEN` | no | only for real Shopify sync | **yes** |

`PORT` is provided by Render — the start command binds to it. `BACKEND_HOST`,
`BACKEND_PORT` are local-development only and default to `0.0.0.0:8000`.

### Frontend — Vercel → Settings → Environment Variables

| Name | Required | Value |
|---|---|---|
| `VITE_API_BASE_URL` | **yes** | the Render origin, **no trailing slash**: `https://<name>.onrender.com` |

`VITE_` values are inlined at **build** time. Changing one requires a
redeploy. Never put a secret in a `VITE_` variable.

Local development needs no frontend variable: leave it unset so requests stay
same-origin and Vite proxies `/api` to `127.0.0.1:8000`.

---

## 3. Backend on Render

Either path gives the same settings.

**Option A — Blueprint (repo contains `render.yaml`)**
Render dashboard → **New +** → **Blueprint** → connect the GitHub repo → it reads
`render.yaml`. Set `CORS_ORIGINS` when prompted (it is marked `sync: false`).

**Option B — manual Web Service**
Render dashboard → **New +** → **Web Service** → connect the repo.

| Field | Value |
|---|---|
| Name | `commercepilot-ai-api` |
| Runtime | **Python 3** (or `Docker` is not needed) |
| Region | closest to your audience |
| **Root Directory** | *leave empty* (repository root — `requirements.txt` lives there) |
| Branch | `main` (or your working branch) |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `uvicorn backend.main:app --host 0.0.0.0 --port $PORT` |
| **Health Check Path** | `/api/health` |
| Instance Type | Free (see §6 for its limits) |

Environment: add `CORS_ORIGINS=https://<your-frontend>.vercel.app` and
`PYTHON_VERSION=3.12`. Add the optional integration keys only if you have them.

**Do not** set the root directory to `backend/` — the build would not find
`requirements.txt` and the module would import as `main:app` instead of
`backend.main:app`.

Deploy, then open `https://<name>.onrender.com/api/health`; you should see:

```json
{"status":"ok","service":"commercepilot-ai","version":"1.0.0","llm_mode":"fallback","projects":0}
```

---

## 4. Frontend on Vercel

Vercel dashboard → **Add New… → Project** → import the same GitHub repo.

| Setting | Value |
|---|---|
| Framework Preset | **Vite** |
| **Root Directory** | `frontend` |
| Build Command | `npm run build` |
| Output Directory | `dist` |
| Install Command | *(leave the detected default)* |
| Node version | 20+ (Vercel default is fine) |

Then **Settings → Environment Variables** → add `VITE_API_BASE_URL` =
`https://<name>.onrender.com` for Production *and* Preview → **Deploy**.

`frontend/vercel.json` supplies the SPA rewrite, so deep links such as
`/store` and `/analytics` work on refresh and on direct visits.

Order matters: the backend must be deployed **before** the frontend build, or
the bundle will contain an empty API base URL.

---

## 5. Connect and verify

1. Set `CORS_ORIGINS` on Render to the exact Vercel origin (scheme + host, no
   trailing slash). Origin strings must match exactly — `http://localhost:3000`
   and `http://127.0.0.1:3000` are different origins.
2. Run the automated smoke test:

   ```bash
   .venv/bin/pip install httpx
   .venv/bin/python scripts/verify_deployment.py \
       --backend https://<name>.onrender.com \
       --frontend https://<your-frontend>.vercel.app
   ```

   It checks health, CORS (including preflight), sample-data labelling,
   Example Project → full workflow → report → assistant, and that the JS bundle
   contains no secrets and no stray localhost URLs. Exit code 0 = all passed.
3. Open the public URL in an incognito window and walk the 60-second demo
   script from the README. Confirm in the browser dev tools that no request
   fails and no CORS error appears.

### Acceptance checklist

- [ ] `GET https://<name>.onrender.com/api/health` returns `status: ok`
- [ ] Dashboard loads with no console/network errors
- [ ] **Example Project** creates (201) and appears in the sidebar
- [ ] **Run Full Commerce Workflow** completes all 7 steps `success`
- [ ] Product Hunter returns ranked results, sample rows labelled *sample data*
- [ ] Selected product flows into the storefront generator
- [ ] Storefront preview renders; cart, quantity, mobile toggle work
- [ ] Campaign allocations must sum to the budget (mismatch → 422)
- [ ] Analytics metrics compute from the stored price/cost
- [ ] Assistant answers using the current project context
- [ ] Backend health endpoint works independently of the frontend
- [ ] Deep link `https://<frontend>/store` works on refresh
- [ ] No secrets in the page source or network tab
- [ ] Public URL opens on another device / in incognito

---

## 6. Free-tier realities (verified October 2026)

* **Render Free** web service: 0.1 CPU / 512 MB, spins down after **15 minutes**
  without traffic. The first request after spin-down takes **~1 minute** while
  it restarts; open the site a minute before you present.
  ([render.com/docs/free](https://render.com/docs/free))
* **Render free instances have no persistent disk.** The SQLite file
  (`backend/commercepilot.sqlite3`, overridable with `DB_PATH`) lives on the
  instance disk, so **projects are lost on restart, redeploy or spin-down**.
  This is acceptable for the demo: the sidebar's **Example Project** button
  rebuilds the demo state in one click. For durable data, upgrade to a paid
  instance, attach a disk and set `DB_PATH=/data/commercepilot.sqlite3`
  (`render.yaml` shows the commented `disk:` block).
  ([render.com/docs/disks](https://render.com/docs/disks))
* **Vercel Hobby**: 100 GB transfer, 200 projects, 45-minute builds,
  100 deployments/day, one concurrent build. It is **personal, non-commercial
  use only**, and cannot connect to repositories owned by a Git *organization*.
  ([vercel.com/docs/plans/hobby](https://vercel.com/docs/plans/hobby),
  [vercel.com/docs/limits](https://vercel.com/docs/limits))
* Free-tier terms change — re-check both pages before your event.

---

## 7. Troubleshooting

| Symptom | Cause and fix |
|---|---|
| Browser: *CORS policy: No 'Access-Control-Allow-Origin'* | `CORS_ORIGINS` on Render does not exactly match the frontend origin (scheme, host, port). Fix the value and **restart** the service. |
| API requests return the app's HTML (200, `text/html`) | `VITE_API_BASE_URL` missing or wrong when the frontend was built. Set it, then **redeploy** the frontend (it is baked in at build time). |
| `ModuleNotFoundError: No module named 'backend'` | Start command ran from the wrong directory, or root directory was set to `backend/`. Use repo root and `backend.main:app`. |
| `ModuleNotFoundError: No module named 'fastapi'` | Build command did not run `pip install -r requirements.txt`. |
| Render: *Application failed to respond* | Health check path is not `/api/health`, or the start command ignores `$PORT`. Check the Logs tab. |
| Frontend loads, everything says *Backend unreachable* | Backend asleep (free tier) — wait ~1 minute and retry, or check `/api/health` directly. |
| Projects vanish between visits | Free-tier ephemeral disk (§6). Expected; recreate the Example Project. |
| `404` on a page refresh | `frontend/vercel.json` missing or Root Directory not set to `frontend`. |

---

## 8. What still needs external credentials

Nothing below is required for the competition demo — the app runs fully and
labels itself honestly without them.

| Feature | Needed | Behaviour without it |
|---|---|---|
| LLM copywriting / intent parsing | `OPENAI_API_KEY` | Deterministic templates, `llm_mode: "fallback"` in health |
| Richer live search | `SERPER_API_KEY` | Keyless DuckDuckGo search still works |
| **Publishing** Meta ads | Meta token + app + ad account | **Not Connected**; simulation labelled *DEMO — NOT PUBLISHED* |
| **Syncing** Shopify products | Shopify shop domain + Admin token | **Not Connected**; sample catalogue used |

Do not claim Meta ads were published or a Shopify theme was deployed unless
those API calls actually succeeded.

---

## 9. Local fallback (keep it working)

```bash
# Backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000

# Frontend
cd frontend && npm install && npm run dev     # http://localhost:3000
```

If the public backend is asleep or unreachable during your presentation, the
local stack is the backup: it needs no external service at all.

---

## 10. Single-project Vercel deployment (one URL, no card)

This is the live deployment: **https://commercepilot-ai-one.vercel.app**
(Vercel project `commerce-pilot1/commercepilot-ai`). One Vercel project serves
the static React build *and* the FastAPI backend from the same origin, so there
is no CORS configuration and no `VITE_API_BASE_URL` — the browser calls `/api/*`
relatively and `vercel.json` routes it to the Python function.

| File | Purpose |
|---|---|
| `api/index.py` | ASGI entry for Vercel's Python runtime (imports `backend.main:app`, sets `DB_PATH=/tmp/commercepilot.sqlite3`) |
| `vercel.json` | `/api/*` → the function; everything else → `index.html` (SPA deep links) |
| `package.json` (root) | `npm run build` installs `frontend/`, builds it and copies `frontend/dist` → `public/` |

Redeploying: `vercel deploy --prod` (Vercel CLI already authenticated in the
workspace). Deployment Protection must stay **off** for the URL to be public.

**Ephemeral data (accepted trade-off):** Vercel functions only have `/tmp`,
and each instance has its own copy, so projects reset on cold starts and may
not be visible across instances. The **Example Project** button rebuilds the
demo state in one click. For durable data, use the Render path in §3 with a
disk, or a managed database.

**Smoke test note:** `scripts/verify_deployment.py` was written for the split
deployment in §1. Its three CORS/`VITE_API_BASE_URL` checks fail by design on
the single-origin deployment (no cross-origin requests exist); the other 13
checks — health, sample labelling, example project, full workflow, report,
storefront, assistant, bundle secrets, SPA deep links — pass against it.
