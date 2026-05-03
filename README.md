# ExperienceGraph Enterprise

ExperienceGraph Enterprise is a clinician-first, multi-tenant SaaS MVP for turning de-identified micro-cases into a reusable experience graph. It supports similar-case retrieval, expert routing, peer validation, auditability, and enterprise-safe local demo workflows.

## What Changed
- React is the primary product UI, backed by an API-first FastAPI backend.
- Roles now support `clinician`, `org_admin`, `reviewer`, `auditor`, and demo-only `super_admin`.
- Seed data now creates 2 orgs, 8 users per org, and 52 cases total.
- Retrieval uses a reusable structured-case core with hybrid scoring and persisted case similarity edges.
- Audit logs now cover auth, case views, exports, graph rebuilds, and settings changes.
- Firebase and Qdrant adapters are now wired into the backend search/indexing flow so we can move toward a Firebase-first operational model without losing offline local development.

## Core Features
- JWT access tokens plus refresh-cookie auth
- Multi-tenant org and team scoping
- Verified-clinician endorsements with rate limits
- Rich case schema with follow-up, resource setting, age bucket, specialty domain, and tag groups
- Hybrid similar-case search: semantic score + tags + constraints + specialty alignment
- Hybrid search now blends semantic retrieval, keyword relevance, fuzzy matching, tag overlap, constraint overlap, and age-bucket alignment
- Explainable expert routing with score breakdowns
- Revision history with diff payloads
- Org settings, exports, and system metrics
- Offline-safe deterministic embedding fallback

## Local Quickstart
1. Create and activate a virtual environment.
2. Install backend dependencies:

```powershell
pip install -r requirements.txt
```

3. Seed demo data and start the backend:

```powershell
$env:PYTHONPATH='backend'
python -m backend.app.seed
python -m backend.app.main
```

4. Start the React frontend in a second terminal:

```powershell
cd frontend
npm run dev
```

5. Or run the combined dev helper after `npm` is on `PATH`:

```powershell
python scripts/dev.py
```

Backend API docs: `http://127.0.0.1:8000/docs`

Frontend default URL: `http://localhost:5173`

## Demo Accounts
- Demo Health admin: `admin@demo.health` / `AdminPass123!`
- Demo Health clinician: `dr.lee.1@demo.health` / `DemoPass123!`
- Demo Health reviewer: `reviewer.1@demo.health` / `DemoPass123!`
- Demo Health auditor: `auditor.1@demo.health` / `DemoPass123!`
- Northwind admin: `admin@northwind.health` / `NorthwindPass123!`

## Demo Script
1. Login as `admin@demo.health`.
2. Open the dashboard and confirm seeded case counts.
3. Create a new ED neuro or immunotherapy case.
4. Open the case detail and inspect similar cases.
5. Open the Match page and submit a routing query.
6. Open the Admin page and inspect audit logs plus system metrics.
7. Trigger an export and confirm case count is returned.

Expected results:
- Similar-case search returns scored cases with explanations.
- Expert routing returns ranked clinicians with explanation breakdowns.
- Audit logs record login, case view, export, and admin actions.

## Tests
Backend tests:

```powershell
python -m pytest -q
```

Current coverage includes:
- retrieval math and hybrid routing
- PII detection
- permissions
- template field normalization
- refresh token rotation

## Search and Storage Notes
- Runtime write-paths are backend-controlled: cases, users, and audit events can be mirrored into Firebase document collections and Qdrant vectors when those services are configured.
- `STORAGE_BACKEND=firebase` is the intended cloud direction. In local locked-down environments, the app still runs safely without Firebase credentials and falls back to local SQL plus deterministic embeddings.
- Qdrant is optional but supported for vector retrieval through `QDRANT_URL`, `QDRANT_API_KEY`, and `QDRANT_COLLECTION_NAME`.
- The hybrid scorer combines:
  - semantic similarity
  - keyword relevance
  - fuzzy matching
  - tag overlap
  - constraint overlap
  - specialty alignment
  - age-bucket alignment

## Environment Notes
- SQLite is the default local path: `experiencegraph_enterprise.db`
- `EMBEDDING_PROVIDER=auto` uses OpenAI when `OPENAI_API_KEY` is set, otherwise deterministic hash embeddings for offline-safe local runs
- `sentence-transformers` remains optional and can be enabled explicitly with `EMBEDDING_PROVIDER=sentence-transformers`
- Firebase settings:
  - `FIREBASE_PROJECT_ID`
  - `FIREBASE_CREDENTIALS_PATH` or `FIREBASE_CREDENTIALS_JSON`
  - `FIREBASE_CASES_COLLECTION`
  - `FIREBASE_USERS_COLLECTION`
  - `FIREBASE_AUDIT_COLLECTION`

## Docker
Build and run the backend plus Postgres:

```powershell
docker compose up --build
```

## Important API Endpoints
- `POST /api/auth/login`
- `POST /api/auth/refresh`
- `POST /api/auth/logout`
- `GET /api/auth/me`
- `GET /api/cases`
- `POST /api/cases`
- `PUT /api/cases/{case_id}`
- `GET /api/cases/{case_id}`
- `GET /api/cases/{case_id}/similar`
- `POST /api/search/cases`
- `POST /api/routing/experts`
- `POST /api/cases/{case_id}/endorse`
- `GET /api/admin/logs`
- `GET /api/admin/revisions/{case_id}`
- `GET /api/admin/exports/cases`
- `GET /api/metrics/roi`
- `GET /api/metrics/system`
- `GET /api/org/settings`
- `PUT /api/org/settings`
