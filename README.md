# ExperienceGraph

ExperienceGraph is a clinician-only, server-rendered FastAPI application for capturing de-identified micro-cases, retrieving similar cases, and routing to the right expert with visible rationale. The launch product is workflow-first, not social, not patient-facing, and not autonomous clinical advice.

## Product direction
- Official UI surface: FastAPI templates
- Launch wedge: general clinician workflow with strongest optimisation for neuro referral and diagnostic routing
- Core value: reduce time, improve access to expertise, and make case-based decisions safer and more auditable

## Core capabilities
- Email/password auth with org roles: `clinician`, `org_admin`, `reviewer`, `auditor`, optional demo `super_admin`
- Rapid case capture with specialty, urgency, age bucket, care setting, constraints, tags, and progressive-detail fields
- Hard de-identification gate before persistence for structured and free-text fields
- Hybrid similar-case retrieval:
  - semantic similarity
  - keyword relevance
  - fuzzy matching
  - tag overlap
  - constraint overlap
  - specialty alignment
  - age-bucket alignment
- Explainable expert routing with availability, validation, and experience signals
- Immutable revision history with diff payloads
- Audit trails for auth, case views, edits, exports, settings changes, and graph/index rebuilds
- Firebase document sync and optional Qdrant vector sync, with SQLite fallback for local work

## Local quickstart
```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
$env:PYTHONPATH='backend'
python -m backend.app.seed
python -m backend.app.main
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000).

## Demo accounts
- `admin@demo.health` / `AdminPass123!`
- `reviewer.1@demo.health` / `DemoPass123!`
- `auditor.1@demo.health` / `DemoPass123!`
- `dr.lee.1@demo.health` / `DemoPass123!`

## Main workflows
1. Sign in at `/login`.
2. Review recent cases and program metrics on `/dashboard`.
3. Start a structured case from `/cases/new`.
4. Inspect similar cases and routing signals from the case detail page.
5. Run org-level case retrieval at `/search`.
6. Route a case to experts at `/match`.
7. Review profile, audit, revisions, and verification controls from `/profile`, `/admin`, `/admin/logs`, and `/admin/revisions/{case_id}`.

## Storage and search notes
- `STORAGE_BACKEND=firebase` is the intended cloud storage direction.
- Local development still works without Firebase or Qdrant.
- Qdrant is used when available for vector retrieval through:
  - `QDRANT_URL`
  - `QDRANT_API_KEY`
  - `QDRANT_COLLECTION_NAME`
- Embeddings use:
  - OpenAI if `OPENAI_API_KEY` is set
  - `sentence-transformers` if explicitly selected
  - deterministic hash embeddings as the locked-down fallback

## Important endpoints
- `POST /api/auth/login|refresh|logout`
- `GET /api/auth/me`
- `GET/POST/PUT /api/cases`
- `GET /api/cases/{id}`
- `GET /api/cases/{id}/similar`
- `POST /api/search/cases`
- `POST /api/routing/experts`
- `POST /api/cases/{id}/endorse`
- `GET /api/admin/logs`
- `GET /api/admin/revisions/{id}`
- `GET /api/admin/exports/cases`
- `GET /api/metrics/roi`
- `GET /api/metrics/system`

## Tests
```powershell
python -m pytest -q
```

Current coverage includes retrieval, routing, permissions, PII checks, template field normalisation, storage fallbacks, and token flows.
