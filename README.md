# ExperienceGraph

ExperienceGraph is a clinician-only MVP that turns structured micro-cases into an experience graph for similar-case retrieval, expert routing, and peer validation.

## Features
- Email/password auth with orgs/roles (doctor/admin)
- Micro-case ingestion with tags, revisions, and PHI blocking
- Similar-case retrieval (hybrid: embeddings + structured filters)
- Expert routing with explanations and reputation signals
- Peer validation with rate limiting
- Case view access logs for org admins

## Quickstart
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
python backend/seed.py
uvicorn backend.app.main:app --reload
```

Open `http://127.0.0.1:8000`.

## Demo Script
1) Login with `admin@northwind.test` / `adminpass`.
2) Create a new micro-case via “Add micro-case”.
   - Expected: redirected to case view page.
3) Go to “Case search” and search for `lingual numbness`.
   - Expected: results include “Lingual numbness with headaches”.
4) Go to “Expert match” and paste a case summary.
   - Expected: ranked doctors with explanations.
5) Click “Endorse usefulness” on any case.
   - Expected: alert confirmation, prevents self-endorsement.
6) Admin logs: call `GET /api/admin/access-logs` with admin session.
   - Expected: list of case view records.

## Environment
See `.env.example` for settings. Defaults use SQLite for local dev. Optional `OPENAI_API_KEY` enables OpenAI embeddings; `EMBEDDINGS_BACKEND=hash` forces local hashing.

Optional extras:
- `pip install sentence-transformers` to enable local transformer embeddings
- `pip install psycopg[binary]==3.2.3` to connect to Postgres outside Docker

## Docker
Docker files are included for deployment readiness.
```bash
docker-compose up --build
```

## Tests
```bash
python -m pytest backend/tests
```
