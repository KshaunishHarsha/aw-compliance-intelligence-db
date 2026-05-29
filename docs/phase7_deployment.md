# Phase 7: Hardening + Deployment

Production deployment of the platform. **Supabase** hosts Postgres + Storage, **Railway** hosts the FastAPI API + Celery worker + Redis, **Vercel** hosts the Next.js frontend.

---

## Architecture

```
            ┌─────────────────┐
            │  Vercel (CDN)   │   Next.js 16 — static + RSC
            │  *.vercel.app   │   NEXT_PUBLIC_API_URL → Railway
            └────────┬────────┘
                     │ HTTPS
                     ▼
            ┌─────────────────┐
            │  Railway        │   FastAPI (uvicorn) + Celery worker + Redis
            │  *.railway.app  │   All env vars live here
            └────────┬────────┘
                     │ Session pooler (Supavisor :5432)
                     ▼
            ┌─────────────────┐
            │  Supabase       │   Postgres 17.6 + pgvector + Storage bucket
            │  Singapore (ap- │   FK/trigger/index schema same as local
            │  southeast-1)   │
            └─────────────────┘
```

---

## Hardening Summary (pre-deploy)

| Feature | Implementation |
|---|---|
| Request ID middleware | `app/observability/middleware.py` — `X-Request-ID` on every response, threaded into all log lines via `contextvar` |
| Structured JSON logs | `app/observability/logging.py` — JSON formatter in production, human format locally; carries request_id, user_id, document_id, etc. |
| Consistent error JSON | `{"error":{"code","message","request_id"}}` on every 4xx/5xx |
| Rate limit | `app/observability/rate_limit.py` — Redis sliding window, default 10/min/IP on `/api/auth/login`, returns 429 + `Retry-After` |
| Production guard | `Settings.validate_for_production()` refuses to boot with `SECRET_KEY=changeme`, wildcard CORS, missing API keys |
| Health probes | `/health`, `/health/db`, `/health/redis`, `/health/storage` |
| Frontend error boundary | `src/app/error.tsx` — "Try again" / "Back to search" fallback for any route crash |

---

## 1. Supabase (already done)

| Step | Status |
|---|---|
| Project created | ✅ `olrdcfgqbvcrpenwbmbu` (ap-southeast-1) |
| `vector` + `pgcrypto` extensions enabled | ✅ |
| Alembic migrations applied to head (`b9c0d1e2f3a4`) | ✅ |
| Data migrated from local Postgres (1617 documents, 1616 embeddings) | ✅ |
| `fts_vector` populated by trigger | ✅ |
| Storage bucket `documents` | ✅ (already in use by local dev) |

**Connection strings** (Settings → Database → Connection Pooler → Session mode):
```
Host:     aws-1-ap-southeast-1.pooler.supabase.com
Port:     5432
Database: postgres
User:     postgres.olrdcfgqbvcrpenwbmbu
Password: <database password — rotate before going live>
```

**Important:** URL-encode `@` in the password as `%40` when building the URL.

---

## 2. Railway — Backend (FastAPI + Celery + Redis)

Three services in one Railway project, all from the same GitHub repo and same `backend/Dockerfile`.

### Step 1: Create project

1. Railway dashboard → **New Project**
2. **Deploy from GitHub repo** → pick `ai-aw-compliance-checker`
3. Railway will detect the Dockerfile; let it create the initial service. We'll fix settings next.

### Step 2: Add Redis

1. In the project, click **+ New** → **Database** → **Add Redis**
2. Railway provisions Redis and exposes `REDIS_URL` automatically as a service-to-service reference variable.

### Step 3: Configure the API service

1. Click into the service Railway created from the repo.
2. **Settings → Source**
   - Root directory: `backend`
   - Build: Dockerfile (auto-detected)
3. **Settings → Networking → Generate Domain** → note the `*.up.railway.app` URL.
4. **Variables** → paste all of these:

```env
DATABASE_URL=postgresql+asyncpg://postgres.<PROJECT_REF>:<URL_ENCODED_PASSWORD>@aws-1-ap-southeast-1.pooler.supabase.com:5432/postgres
SYNC_DATABASE_URL=postgresql://postgres.<PROJECT_REF>:<URL_ENCODED_PASSWORD>@aws-1-ap-southeast-1.pooler.supabase.com:5432/postgres
REDIS_URL=${{Redis.REDIS_URL}}
ENVIRONMENT=production
SECRET_KEY=<paste the SECRET_KEY printed by the script>
CORS_ORIGINS=https://<your-vercel-domain>.vercel.app
LOG_LEVEL=INFO
OPENROUTER_API_KEY=<copy from local .env>
STORAGE_PROVIDER=supabase
SUPABASE_URL=<copy from local .env>
SUPABASE_KEY=<copy from local .env>
SUPABASE_BUCKET=documents
```

> **`${{Redis.REDIS_URL}}`** is a Railway reference variable — it expands to the Redis service's internal URL at runtime.
>
> **`CORS_ORIGINS`** can be left as a placeholder until Vercel is deployed and you know the actual URL. The API will boot but the frontend can't talk to it until this matches.

### Step 4: Add the Worker service

1. Project → **+ New** → **GitHub Repo** → same repo
2. **Settings → Source**
   - Root directory: `backend`
   - Build: Dockerfile
   - **Custom Start Command**:
     ```
     celery -A celery_worker worker --loglevel=info --concurrency=2
     ```
3. **Settings → Networking** → **DO NOT** generate a public domain (worker has no HTTP server)
4. **Variables** → paste the same env block as the API service (Railway has "Shared Variables" — easiest to define once at the project level and link both services to them).

### Step 5: Deploy

1. Both services will redeploy automatically when you push to the configured branch.
2. **Logs** tab on the API service should show:
   ```
   INFO:     Uvicorn running on http://0.0.0.0:<PORT>
   INFO:     Application startup complete.
   ```
3. Smoke test the API:
   ```
   curl https://<api>.up.railway.app/health
   curl https://<api>.up.railway.app/health/db
   curl https://<api>.up.railway.app/health/redis
   curl https://<api>.up.railway.app/health/storage
   ```
   All four should return 200.

---

## 3. Vercel — Frontend (Next.js)

### Step 1: Import project

1. Vercel dashboard → **Add New → Project**
2. **Import Git Repository** → `ai-aw-compliance-checker`
3. **Framework Preset**: Next.js (auto-detected)
4. **Root Directory**: `frontend`
5. **Build & Output Settings**: leave defaults (Vercel handles `next build`)

### Step 2: Environment variables

In the import flow (or **Settings → Environment Variables** after):

```env
NEXT_PUBLIC_API_URL=https://<your-railway-api>.up.railway.app
```

Apply to **Production**, **Preview**, and **Development**.

### Step 3: Deploy

1. Click **Deploy**.
2. Wait for the build (~2–3 min).
3. Vercel assigns a `*.vercel.app` domain.

### Step 4: Update Railway CORS

Once you have the Vercel domain:

1. Railway → API service → **Variables**
2. Update `CORS_ORIGINS` to your actual Vercel URL:
   ```
   CORS_ORIGINS=https://ai-aw-compliance-checker.vercel.app
   ```
3. Repeat for the Worker service (or update the shared variable).
4. Railway will auto-redeploy.

---

## 4. Post-deploy smoke test

| Action | Expected |
|---|---|
| `GET /health` on Railway API | 200 `{"status":"ok"}` |
| Open Vercel URL | Redirects to `/login` |
| Log in as `test@example.com` / `test1234` | Redirects to `/search` |
| Run a search ("veterinary care primates") | 3+ results with score breakdown and match reasoning |
| Click a result → opens `/documents/[id]` | Metadata panel + PDF viewer load |
| Click "Ask about this document" | Chat panel opens, streams a response with `[CIT-N]` pills |
| Visit `/chat` | Shows past conversations (will be empty in prod — those were local-only) |

---

## 5. Rotate the database password

**Critical:** the password used during this setup was visible in chat history.

1. Supabase Dashboard → **Settings → Database → Reset database password**
2. Update both `DATABASE_URL` and `SYNC_DATABASE_URL` in Railway (URL-encode any `@`).
3. Railway will auto-redeploy.
4. Smoke-test `/health/db` again.

---

## 6. Common issues

### `MissingGreenlet` on first request after idle

Supabase connection went stale. Already mitigated by `pool_pre_ping=False, pool_recycle=300` in `db/session.py`. If it persists, drop `pool_recycle` to 60.

### CORS errors in browser console

`CORS_ORIGINS` doesn't match the Vercel URL. Check protocol (`https://`), no trailing slash, no path.

### `Refusing to boot in production: ...`

`validate_for_production()` is doing its job. Fix the listed env vars and redeploy.

### Worker logs show `Connection refused` to Redis

`REDIS_URL` not set, or the Redis service hasn't finished provisioning. Check Railway's Redis service status.

### Cold start latency

Railway free tier sleeps services after inactivity. First request after idle can take 5–10s. Upgrade to Hobby ($5/mo) to keep services warm.

---

## Cost (rough)

| Service | Plan | $/month |
|---|---|---|
| Supabase | Free tier (500MB DB, 1GB storage) | $0 |
| Railway | Hobby — API + Worker + Redis | ~$10–15 |
| Vercel | Hobby (free for personal projects) | $0 |
| OpenAI (via OpenRouter) | Pay-per-use — search reasoning + chat | ~$5–20 depending on traffic |

Total starting cost: **~$15–35/month** for a real deployment with no scaling.

Free tier alternative: Railway has a $5/mo trial; Supabase free fits the current corpus.
