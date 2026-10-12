# DeepDive

DeepDive is an API-first research system that aims to verify individual claims
against the source passages cited for them.

## Current milestone

The scaffold exposes `GET /health` and `POST /api/v1/ask`. The ask endpoint
forwards a prompt to the Mesh chat-completions API and returns the model's
answer.

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

## Tests

```powershell
python -m pytest
```

## Configuration and secrets

Copy `.env.example` to `.env`, then replace `MESH_API_KEY` with your key.
`MESH_MODEL` defaults to `openai/gpt-4o`; update it if your Mesh account uses a
different model ID. Keep the real key in `.env` only—never put it in
`.env.example` or source control. `.env` is ignored by Git.
