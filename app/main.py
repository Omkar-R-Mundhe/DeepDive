import logging
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.base import RequestResponseEndpoint

from app.logging_utils import configure_app_logging, log_stage, request_id_context

configure_app_logging()

from app.agents.claim_drafter import ClaimDraftError, draft_claims
from app.agents.planner import PlannerOutputError, create_research_plan
from app.agents.researcher import ResearchProviderError, search_sources
from app.agents.research_workflow import run_research
from app.agents.verifier import ClaimVerificationError, verify_claims
from app.config import ConfigurationError
from app.database.repository import save_evidence
from app.schemas.research import (
    ClaimDraftRequest,
    ClaimDraftResponse,
    ClaimVerificationRequest,
    ClaimVerificationResponse,
    ResearchPlan,
    ResearchRunRequest,
    ResearchRunResponse,
    SearchRequest,
    SearchResponse,
)
from app.services.llm_client import LLMProviderError, ask_model

app = FastAPI(
    title="DeepDive",
    description="A research system that verifies claims against cited source evidence.",
    version="0.1.0",
)
logger = logging.getLogger(__name__)


@app.middleware("http")
async def log_requests(
    request: Request,
    call_next: RequestResponseEndpoint,
) -> Response:
    request_id = uuid4().hex
    token = request_id_context.set(request_id)
    started_at = perf_counter()
    logger.info(
        "request_id=%s event=request_started method=%s path=%s",
        request_id,
        request.method,
        request.url.path,
    )
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        response.headers["X-Request-ID"] = request_id
        return response
    except Exception as exc:
        logger.error(
            "request_id=%s event=request_failed method=%s path=%s "
            "error_type=%s elapsed_ms=%.1f",
            request_id,
            request.method,
            request.url.path,
            type(exc).__name__,
            (perf_counter() - started_at) * 1000,
        )
        raise
    finally:
        logger.info(
            "request_id=%s event=request_completed method=%s path=%s "
            "status_code=%s elapsed_ms=%.1f",
            request_id,
            request.method,
            request.url.path,
            status_code,
            (perf_counter() - started_at) * 1000,
        )
        request_id_context.reset(token)


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
        with log_stage(logger, "api.ask"):
            answer = ask_model(request.question)
    except LLMProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return AskResponse(answer=answer)


@app.post("/api/v1/plan", response_model=ResearchPlan)
def plan(request: AskRequest) -> ResearchPlan:
    try:
        with log_stage(logger, "api.plan"):
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
        with log_stage(logger, "api.research.sources"):
            evidence = search_sources(request.query, request.count)
        with log_stage(logger, "evidence.persist", evidence_count=len(evidence)):
            save_evidence(evidence)
    except ResearchProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return SearchResponse(query=request.query, evidence=evidence)


@app.post("/api/v1/claims/draft", response_model=ClaimDraftResponse)
def draft_research_claims(request: ClaimDraftRequest) -> ClaimDraftResponse:
    try:
        with log_stage(
            logger,
            "api.claims.draft",
            evidence_count=len(request.evidence),
        ):
            claims = draft_claims(request.question, request.evidence)
    except ClaimDraftError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except LLMProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return ClaimDraftResponse(claims=claims)


@app.post("/api/v1/claims/verify", response_model=ClaimVerificationResponse)
def verify_research_claims(
    request: ClaimVerificationRequest,
) -> ClaimVerificationResponse:
    try:
        with log_stage(
            logger,
            "api.claims.verify",
            claim_count=len(request.claims),
            evidence_count=len(request.evidence),
        ):
            verifications = verify_claims(request.claims, request.evidence)
    except ClaimVerificationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except LLMProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return ClaimVerificationResponse(verifications=verifications)


@app.post("/api/v1/research/run", response_model=ResearchRunResponse)
def run_research_request(request: ResearchRunRequest) -> ResearchRunResponse:
    try:
        with log_stage(
            logger,
            "api.research.run",
            results_per_query=request.results_per_query,
        ):
            return run_research(
                request.question,
                results_per_query=request.results_per_query,
            )
    except ConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (
        ClaimDraftError,
        ClaimVerificationError,
        LLMProviderError,
        PlannerOutputError,
        ResearchProviderError,
    ) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
