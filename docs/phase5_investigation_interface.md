# Phase 5: Investigation Interface

The user-facing frontend — design system, app shell, login, search, document detail with PDF viewer, and corpus browsing. Built on top of the hybrid retrieval engine from Phase 4.

---

## Overview

Phase 5 turns the backend into a usable investigative tool. An animal-welfare investigator can sign in, search the corpus with free-text + filters or browse it directly, click into any document for a side-by-side metadata + PDF view, and share a search URL with colleagues so they land on the same result set.

```
/                       → 307 → /search
/login                  Bare layout. Email/password → JWT in localStorage.
/search                 Hybrid search. Filter sidebar + results. URL-driven state.
/documents              Paginated browse of every leaf document.
/documents/[id]         Metadata panel + PDF viewer.
/design                 Living style guide. Bare layout, no auth.
```

---

## Stack & Conventions

| Layer | Choice |
|---|---|
| Framework | Next.js 16 (App Router, Turbopack) |
| React | 19 with promise-shaped `params` |
| Styling | Tailwind v4 (CSS-first `@theme inline`, no `tailwind.config.ts`) |
| Fonts | `next/font/google` with `display: "swap"` — Fraunces (display), IBM Plex Sans (UI), IBM Plex Mono (citations) |
| PDF viewer | `react-pdf` v10 with worker pinned to its bundled pdf.js version, loaded via `next/dynamic` `ssr: false` |
| Auth | JWT in `localStorage`, client-side `AuthGuard` redirects to `/login?next=…` |
| State sharing | URL search params (`?q=…&jurisdiction=CA&categories=sanitation`) |

Note: this stack has breaking changes from older Next.js / Tailwind versions. The project's [frontend/AGENTS.md](../frontend/AGENTS.md) flags this and points at `node_modules/next/dist/docs/` as the source of truth. Tailwind v4 puts all design tokens in CSS (`@theme inline`), not in a JS config file.

---

## Design System

### Aesthetic direction

Refined utilitarian dark theme with editorial typography — closer to a leather-bound investigative case file or a financial terminal than a SaaS dashboard. Sharp 2px corners, border-driven elevation instead of glowing drop shadows, generous use of monospace for citations and data, archival precision over decoration.

### Tokens (in [src/app/globals.css](../frontend/src/app/globals.css))

All tokens are exposed via Tailwind utilities (`bg-surface-2`, `text-primary`, `border-accent/40`, etc.):

| Group | Tokens |
|---|---|
| Surfaces (3 layers) | `surface-1` `#14110F` page · `surface-2` `#1C1916` card · `surface-3` `#252220` elevated |
| Borders | `border-subtle` `#2A2622` · `border-default` `#3A332D` · `border-strong` `#4D4439` |
| Text hierarchy | `text-primary` `#F5F1EB` · `text-secondary` · `text-tertiary` · `text-disabled` |
| Accent (muted amber) | `accent` `#B8842C` · `accent-hover` `#D49B3D` · `accent-muted` `#3D2D14` · `accent-foreground` |
| Status colors | `critical` · `warning` · `info` · `success` — each with a `*-muted` background variant; all meet WCAG AA against `surface-1` |
| Type scale | 12 / 13 / 15 / 17 / 22 / 28 / 36 / 48 px — base is 15px (slightly compressed for research density) |
| Radii | `none` `sm: 2px` `md: 3px` `lg: 4px` `full` — never pill shapes on form controls |
| Shadows | `shadow-1` `shadow-2` `shadow-3` · `shadow-accent-glow` for focus rings |

Plus:
- Subtle SVG noise overlay on `body::before` at 2.5% opacity for tactile texture
- Custom thin scrollbar styled in warm tones
- Amber text selection
- Global focus ring using `shadow-accent-glow`

### Design reference page

`/design` is a living style guide showing every token + primitive in real domain context. Use it during development to verify token changes propagate everywhere. Outside the `(app)` route group, so it renders bare without sidebar/topbar and has no auth requirement.

---

## App Shell

The `(app)` route group ([src/app/(app)/layout.tsx](../frontend/src/app/\(app\)/layout.tsx)) wraps every authenticated page with:

1. **`AuthGuard`** — client component that checks `localStorage` for a JWT. If missing, redirects to `/login?next=<current path>`. Until the check completes, renders a "Checking session…" placeholder to prevent flashing the authed UI.
2. **`Sidebar`** (256px) — brand block, three nav items (Search, Documents, Chat-coming-Phase-6), corpus stats footer (`1,616 documents · USDA APHIS · 9 CFR Title 9`).
3. **`TopBar`** (48px) — `/` keyboard hint, account chip with first-initial avatar + email pulled from localStorage, **Sign out** button.

Pages outside the group (`/login`, `/design`) render bare.

---

## Authentication

Phase 1 auth bugs surfaced during Phase 5 integration and were fixed:

1. **bcrypt 5.x incompatible with passlib 1.7.4** → pinned `bcrypt==4.2.0` in `backend/requirements.txt`
2. **`last_login_at` naive vs aware datetime mismatch** → `auth.py` uses `datetime.utcnow()` to match the `TIMESTAMP WITHOUT TIME ZONE` column
3. **Expired ORM access after commit triggered `MissingGreenlet`** → `auth.py` captures `str(user.id)` and `user.role` into locals *before* the update/commit
4. **`pool_pre_ping=True` on async engine fired sync IO** → `db/session.py` switched to `pool_pre_ping=False, pool_recycle=300`

Frontend auth flow ([src/lib/api.ts](../frontend/src/lib/api.ts)):

- `login(email, password)` POSTs `/api/auth/login`, stores `access_token` and `email` in localStorage.
- `getToken()` / `getStoredEmail()` / `clearSession()` helpers.
- Every authed request includes `Authorization: Bearer <token>`. On 401, clears session and bounces to `/login` via `window.location.replace`.
- Seeded dev user: `test@example.com` / `test1234`. In dev only, the login page offers a "fill seeded credentials" helper.

---

## Search Page

The core experience. Three-pane layout: filter sidebar (288px) · search input + sticky header · results.

### Components

| File | Responsibility |
|---|---|
| [src/components/search/search-input.tsx](../frontend/src/components/search/search-input.tsx) | Big search bar. Global `/` keyboard shortcut focuses + selects. Submit button label switches to **"Apply Filters"** when filters are active and the query is empty (`allowEmptySubmit`). |
| [src/components/search/filter-sidebar.tsx](../frontend/src/components/search/filter-sidebar.tsx) | Doc type (single-select), 10 violation categories (multi-select OR), jurisdiction text, date range, advanced (facility name partial match). Active count badge + clear-all. |
| [src/components/search/result-card.tsx](../frontend/src/components/search/result-card.tsx) | Wraps each result in a `<Link href="/documents/{id}">`. Shows rank, doc-type tag, facility title, score breakdown (or "Filter / metadata only" in filter-only mode), retrieval summary, accent-bordered "Why this matched" callout, category + species chips. |
| [src/app/(app)/search/page.tsx](../frontend/src/app/\(app\)/search/page.tsx) | State machine: `idle` (hero + example queries) → `loading` (skeleton cards) → `success` (results / empty) → `error` (retry). |

### Filter-only search

Triggered when the query is empty but filters are active. Backend supports this via the optional `query` field (Phase 4 update). The page:

- Enables the submit button via `allowEmptySubmit={filtersActiveNow}`.
- Auto-fires search when a filter is toggled (with or without a query).
- Shows different result-header copy: *"N results · filter-only · M filters applied · sorted by inspection date"*.

### URL state

Every search is shareable. State is serialized into URL params:

| Param | Maps to |
|---|---|
| `q` | `query` |
| `doc_type` | `doc_type` |
| `categories` | `categories[]` (comma-separated) |
| `jurisdiction` | `jurisdiction` |
| `facility` | `facility_name` |
| `date_from` / `date_to` | date range |

- On mount, the page parses the URL synchronously to seed initial state and immediately runs the search if anything was set.
- Every `runSearch()` call uses `router.replace(target, { scroll: false })` to update the URL without history bloat.
- Clearing all filters and the query wipes the URL too.

This means **back-from-detail preserves the result set**, and an investigator can paste a search URL into a colleague's chat and they'll land on the same view.

---

## Document Detail

`/documents/[id]` — two-pane layout: 420px metadata panel · PDF viewer.

### Metadata panel ([src/components/document/metadata-panel.tsx](../frontend/src/components/document/metadata-panel.tsx))

Top to bottom: doc-type tag + reference number → big facility title → original filename → full retrieval summary → structured metadata rows (facility, jurisdiction, inspection date, inspector, reference, issuer, source) → category chips → species chips → provenance footer (document ID, parent ID, status).

### PDF viewer ([src/components/document/pdf-viewer.tsx](../frontend/src/components/document/pdf-viewer.tsx))

- **`react-pdf` v10** via `next/dynamic` with `ssr: false` to avoid pdf.js's "legacy build in Node.js environments" warning and a wasted server render.
- PDF.js worker served from `unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs` (pinned to the exact version react-pdf ships against).
- Toolbar: prev / page number input / next, zoom out / percentage / zoom in, "Open ↗" external link.
- Fit-to-width via `ResizeObserver` on the container.
- Loading + error states.

### Page wiring ([src/app/(app)/documents/[id]/page.tsx](../frontend/src/app/\(app\)/documents/\[id\]/page.tsx))

- Uses `React.use(params)` to unwrap the promise-shaped `params` (Next 16 / React 19 convention).
- Fetches `GET /api/documents/{id}` and `GET /api/documents/{id}/url` in parallel via `Promise.all`.
- Breadcrumb back-link to `/search`; the URL-state preservation on the search page means filters are restored on return.
- 404-aware error message.

---

## Documents Browse

`/documents` — paginated table for browsing the entire corpus without a search query. Distinct from `/search`'s relevance-ranked filter-only mode.

- **Backend endpoint**: existing `GET /api/documents` with `page`, `page_size`, `doc_type`, `source`, `parent_id`, `include_parents`.
- **Frontend**:
  - Left rail: doc-type chips + source chips (single-select, click to toggle), clear-filters button.
  - Main: 5-column table — Type / Document (facility + filename) / Jurisdiction / Date / Reference.
  - Top + bottom pagination controls with prev / next.
  - URL-driven state: `/documents?doc_type=regulation&page=2`.
  - 25 documents per page (`PAGE_SIZE = 25`).
- The Documents nav item in the sidebar is now enabled (the "Soon" badge was removed).

---

## API Client

Single typed module at [src/lib/api.ts](../frontend/src/lib/api.ts) mirroring backend Pydantic schemas:

| Type / Function | Purpose |
|---|---|
| `SearchRequest` / `SearchResponse` / `SearchResult` / `ScoreBreakdown` | Hybrid search |
| `DocumentResponse` / `DocumentMetadata` / `DocumentUrlResponse` | Document detail + signed URL |
| `DocumentListParams` / `DocumentListResponse` | Browse |
| `TokenResponse` / `ApiError` | Auth |
| `login(email, password)` | POST `/api/auth/login` |
| `search(req)` | POST `/api/search` |
| `getDocument(id)` / `getDocumentUrl(id)` | GET `/api/documents/{id}` and `/url` |
| `listDocuments(params)` | GET `/api/documents` with filters |
| `getToken()` / `getStoredEmail()` / `clearSession()` | localStorage helpers |

The `request()` helper auto-injects the bearer token, handles 401s by clearing session + redirecting, and throws typed `ApiError` for non-2xx responses.

---

## File Layout

```
frontend/
└── src/
    ├── app/
    │   ├── layout.tsx               Root layout — fonts wired via next/font/google
    │   ├── globals.css              All design tokens via @theme inline + base styles
    │   ├── page.tsx                 /  → redirects to /search
    │   ├── design/page.tsx          /design — living style guide (bare layout)
    │   ├── login/page.tsx           /login — auth form (bare layout)
    │   └── (app)/
    │       ├── layout.tsx           App shell with AuthGuard + Sidebar + TopBar
    │       ├── search/page.tsx      /search — hybrid + filter-only + URL state
    │       ├── documents/
    │       │   ├── page.tsx         /documents — paginated browse
    │       │   └── [id]/page.tsx    /documents/[id] — detail with PDF viewer
    │       └── (chat/ — Phase 6)
    ├── components/
    │   ├── app-shell/
    │   │   ├── sidebar.tsx
    │   │   ├── top-bar.tsx
    │   │   └── auth-guard.tsx
    │   ├── search/
    │   │   ├── search-input.tsx
    │   │   ├── filter-sidebar.tsx
    │   │   └── result-card.tsx
    │   └── document/
    │       ├── metadata-panel.tsx
    │       └── pdf-viewer.tsx
    └── lib/
        └── api.ts                   Typed API client
```

---

## Known Limitations / Future Polish

- **CORS for PDFs**: signed Supabase Storage URLs must allow direct browser fetch. The current bucket setup works; if it ever doesn't, the fallback is to proxy through the backend.
- **Multiple lockfiles warning**: Next detects lockfiles in both `~/package-lock.json` and `frontend/package-lock.json` and warns at every dev startup. Set `turbopack.root` in `next.config.ts` to silence it, or delete the stray home-directory lockfile.
- **Search URL state vs Documents browse**: Browse uses its own URL params (`page`, `doc_type`, `source`) — the two pages don't share a query-language. Acceptable for V1; could be unified later.
- **No real-time updates**: if a document is re-ingested while the user is on the detail page, they won't see the change without a manual refresh.
- **Mobile**: the design is desktop-first. Filter sidebar, two-pane document detail, and the table-based browse don't have responsive variants yet.

---

## How to Run

```bash
# Backend
docker compose up -d
# Backend exposes :8000

# Frontend
cd frontend && npm run dev
# Frontend on :3000

# Sign in with: test@example.com / test1234
```

The frontend assumes `NEXT_PUBLIC_API_URL=http://localhost:8000` by default — override in `.env.local` if needed.
