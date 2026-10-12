from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.agents.planner import PlannerOutputError, create_research_plan
from app.agents.researcher import ResearchProviderError, search_sources
from app.config import ConfigurationError
from app.database.repository import save_evidence
from app.schemas.research import ResearchPlan, SearchRequest, SearchResponse
from app.services.llm_client import LLMProviderError, ask_model

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
    except LLMProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return AskResponse(answer=answer)


@app.post("/api/v1/plan", response_model=ResearchPlan)
def plan(request: AskRequest) -> ResearchPlan:
    try:
        return create_research_plan(request.question)
    except PlannerOutputError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except LLMProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/api/v1/research/sources", response_model=SearchResponse)
def research_sources(request: SearchRequest) -> SearchResponse:
    try:
        evidence = search_sources(request.query, request.count)
        save_evidence(evidence)
    except ResearchProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return SearchResponse(query=request.query, evidence=evidence)
