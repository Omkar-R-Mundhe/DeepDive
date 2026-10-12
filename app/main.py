from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.config import ConfigurationError
from app.services.llm_client import MeshAPIError, ask_model

app = FastAPI(
    title="DeepDive",
    description="A research system that verifies claims against cited source evidence.",
    version="0.1.0",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


class AskRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    question: str = Field(min_length=1)


class AskResponse(BaseModel):
    answer: str


@app.post("/api/v1/ask", response_model=AskResponse)
def ask(request: AskRequest) -> AskResponse:
    try:
        answer = ask_model(request.question)
    except MeshAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return AskResponse(answer=answer)
