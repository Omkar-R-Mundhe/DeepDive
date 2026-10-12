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
- Kept credentials out of `.env.example`; local API keys belong in `.env`.
