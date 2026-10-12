# DeepDive

DeepDive is an API-first research system that aims to verify individual claims
against the source passages cited for them.

## Current milestone

The scaffold exposes `GET /health`, `POST /api/v1/ask`, and
`POST /api/v1/plan`. The plan endpoint asks the Planner to create and validate
3–5 research sub-questions, scope boundaries, and recommended source types.
`POST /api/v1/research/sources` searches Brave and stores the returned evidence
snippets in a local SQLite database.

## Setup

From PowerShell in this directory:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -m uvicorn app.main:app --reload
```

Open <http://127.0.0.1:8000/docs> for the API documentation. The health
endpoint is available at <http://127.0.0.1:8000/health> and returns
`{"status":"ok"}`.

To try the Planner endpoint, send a JSON request such as
`{"question":"How is urban tree cover changing?"}` to
`POST /api/v1/plan`.

To search Brave, set `BRAVE_SEARCH_API_KEY` in `.env`, restart the app, then
send `{"query":"urban tree cover and heat","count":5}` to
`POST /api/v1/research/sources`. Returned passages are Brave search snippets,
not full-page text; the response labels them `search_snippet`. Evidence is
persisted to `data/deepdive.sqlite3`, which is ignored by Git.

## Tests

```powershell
python -m pytest
```

## Configuration and secrets

Copy `.env.example` to `.env` and add your provider's key. Set
`LLM_PROVIDER=mesh` to use Mesh (the hackathon target), or set
`LLM_PROVIDER=gemini` for temporary local testing with the Gemini API directly.
Each provider has its own key and model settings; never reuse or relabel a
provider key. Gemini-direct calls bypass Mesh and are for development testing
only. The Gemini model should be one enabled for your key; the current local
setup was verified with `gemini-3.8-flash`. Brave search uses its own
`BRAVE_SEARCH_API_KEY`, separate from the LLM key. Restart Uvicorn after
changing `.env` so the app loads the selected provider and settings. Keep real
keys in `.env` only—never put them in `.env.example` or source control. `.env`
is ignored by Git.
