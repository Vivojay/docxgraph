# ExperienceGraph Agent Notes

- Backend correctness comes first. UI work should only ship when the underlying API behavior is real.
- Current direction is Firebase-first plus optional Qdrant for vectors. Do not introduce Supabase.
- Local evaluation may still use SQLite safely when Firebase creds are unavailable, but cloud-facing storage assumptions should target Firebase collections.
- Embeddings: OpenAI if key present; else sentence-transformers; final fallback to deterministic hash embedding.
- Keep search hybrid and explainable: semantic + keyword + fuzzy + structured filters.
- Seed script creates demo orgs, users, cases, and graph edges.
- Access logs are captured on case view; admins and auditors can review them.
- React is the primary product UI; backend HTML is a lightweight fallback and API/docs entrypoint.
- Default local DB is `experiencegraph_enterprise.db`; use a temp `DATABASE_URL` for isolated evaluation runs.
- In locked-down environments, keep `EMBEDDING_PROVIDER=auto` or `hash` to avoid network fetches for sentence-transformers.
- Use `python scripts/dev.py` for combined seed + backend + frontend startup when `npm` is on `PATH`.
