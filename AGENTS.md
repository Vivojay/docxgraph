# Agent Notes

- Preferred entrypoint: `backend/app/main.py`
- Initialize DB schema: `python backend/seed.py` (calls `init_db()`)
- Default DB: SQLite (`experiencegraph.sqlite3`) via `DATABASE_URL`
- Auth uses JWT stored in `access_token` cookie
- Seed accounts: admin@northwind.test / adminpass, neuro@northwind.test / password
- Embeddings: OpenAI if `OPENAI_API_KEY` else sentence-transformers or hashed fallback
- Tests: `python -m pytest backend/tests`
