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
- Kept credentials out of `.env.example`; local API keys belong in `.env`.
- Tightened environment-file ignores and pushed the project to its dedicated
  GitHub repository.
