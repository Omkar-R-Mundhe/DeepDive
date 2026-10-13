# Changelog

## 2026-10-12

- Created the initial FastAPI project scaffold.
- Added `GET /health`, returning `{"status": "ok"}`.
- Added a health endpoint test; it passes.
- Added setup documentation, dependency files, and `.env`/virtual-environment
  Git ignores.
- Added Mesh configuration loading, a Mesh chat-completions client, and
  `POST /api/v1/ask`.
- Added tests for health, ask success, invalid requests, and Mesh/configuration
  errors.
- Preserved upstream Mesh error details in API responses while redacting the
  configured API key.
- Added an opt-in Gemini API provider for local testing; Mesh remains the
  default provider and hackathon target.
- Configured the local development environment for Gemini and verified a live
  `POST /api/v1/ask` response. The account required `gemini-3.8-flash`; this
  credential is kept only in the ignored local `.env`.
- Added the Planner agent, validated research-plan schema, and
  `POST /api/v1/plan` endpoint for 3–5 distinct sub-questions.
- Verified the Planner endpoint live against Gemini; the response returned
  four validated sub-questions, scope boundaries, and source recommendations.
- Added a Brave Search retrieval endpoint and SQLite persistence for returned
  source snippets. Live Brave requests await a separate search API key.
- Added claim drafting and passage-level verification agents and API endpoints.
  Claims retain evidence IDs; verifier output is schema-validated and cannot
  cite evidence IDs that were not attached to the claim.
- Kept credentials out of `.env.example`; local API keys belong in `.env`.
- Tightened environment-file ignores and pushed the project to its dedicated
  GitHub repository.

## 2026-10-13

- Added evidence-linked claim drafting and structured claim verification.
- Added API endpoints for claim drafting and verification, with checks that
  prevent unknown evidence IDs from entering claims or verdicts.
- Added test coverage for supported, contradicted/insufficient evidence paths,
  malformed responses, and evidence-reference validation.
- Added per-request correlation IDs and elapsed-time logs for API, LLM,
  planning, search, evidence persistence, claim drafting, and verification
  stages. Logs record safe counts and failure types without recording request
  text, evidence passages, model output, or credentials.
- Added Tavily as the default search provider, keeping Brave selectable through
  configuration. Both providers produce the existing evidence records and
  continue to persist search snippets in SQLite.
- Added `POST /api/v1/research/run` to coordinate planning, per-sub-question
  search, evidence persistence, claim drafting, and claim verification in one
  request. Search results per question are bounded, and a failed search stops
  the run before partial evidence is persisted.
- Configured an explicit INFO-level application console logger so Uvicorn's
  logging setup cannot silently suppress stage-start events. Logs now have
  timestamps and include a startup confirmation. Long LLM calls emit elapsed-
  time heartbeats every 15 seconds.
