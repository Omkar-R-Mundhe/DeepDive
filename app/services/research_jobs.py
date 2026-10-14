import logging
from uuid import uuid4

from app.agents.claim_drafter import ClaimDraftError
from app.agents.planner import PlannerOutputError
from app.agents.report_writer import ResearchReportError
from app.agents.research_workflow import run_research
from app.agents.researcher import ResearchProviderError
from app.agents.verifier import ClaimVerificationError
from app.config import ConfigurationError
from app.database.repository import update_research_run
from app.logging_utils import request_id_context
from app.schemas.research import ResearchRunResponse
from app.services.llm_client import LLMProviderError

logger = logging.getLogger(__name__)
EXPECTED_RUN_ERRORS = (
    ClaimDraftError,
    ClaimVerificationError,
    ConfigurationError,
    LLMProviderError,
    PlannerOutputError,
    ResearchReportError,
    ResearchProviderError,
)


def _user_facing_error(exc: Exception) -> str:
    message = str(exc).casefold()
    if "402" in message or "payment required" in message or "insufficient credits" in message:
        return (
            "The AI provider account has insufficient credits for this request. "
            "Add credits to the provider account or select a model available "
            "within your current balance."
        )
    if any(
        term in message
        for term in ("429", "quota", "rate limit", "resource_exhausted")
    ):
        return (
            "A connected provider has reached its request quota. Check its usage "
            "or rate-limit dashboard, then retry after the quota window resets."
        )
    if isinstance(exc, ConfigurationError):
        return (
            "The research service is not fully configured. Check the provider "
            "and API-key settings on the server."
        )
    if isinstance(exc, LLMProviderError):
        if "completed without returning text" in message:
            return (
                "The selected AI model completed without returning a text "
                "answer. Choose a currently available text/chat model in "
                "OpenRouter and try again."
            )
        if any(
            term in message
            for term in ("401", "403", "unauthorized", "invalid api key")
        ):
            return (
                "The AI provider rejected its credentials. Check the API key "
                "configured on the server."
            )
        return "The AI provider could not complete the request. Please try again later."
    if isinstance(exc, ResearchProviderError):
        if any(
            term in message
            for term in ("401", "403", "unauthorized", "invalid api key")
        ):
            return (
                "The search provider rejected its credentials. Check the API "
                "key configured on the server."
            )
        return "The web search provider could not complete the request. Please try again later."
    if isinstance(exc, PlannerOutputError):
        return "The research planner returned an unusable response. Please try again."
    if isinstance(exc, ClaimDraftError):
        return "The claim drafting step could not complete. Please try again."
    if isinstance(exc, ClaimVerificationError):
        return "The claim verification step could not complete. Please try again."
    if isinstance(exc, ResearchReportError):
        return "The research was verified, but the final answer could not be prepared. Please try again."
    return "Research could not be completed. Please try again later."


def execute_research_job(
    run_id: str,
    question: str,
    results_per_query: int,
) -> None:
    token = request_id_context.set(run_id)
    logger.info("run_id=%s event=job_started", run_id)
    try:
        update_research_run(
            run_id,
            status="running",
            current_stage="Starting research",
        )

        def record_progress(stage: str) -> None:
            update_research_run(
                run_id,
                status="running",
                current_stage=stage,
            )

        result = run_research(
            question,
            results_per_query,
            progress_callback=record_progress,
        )
        update_research_run(
            run_id,
            status="completed",
            current_stage="Research complete",
            result=result,
        )
        logger.info("run_id=%s event=job_completed", run_id)
    except EXPECTED_RUN_ERRORS as exc:
        update_research_run(
            run_id,
            status="failed",
            current_stage="Research failed",
            error=_user_facing_error(exc),
        )
        logger.error(
            "run_id=%s event=job_failed error_type=%s",
            run_id,
            type(exc).__name__,
        )
    except Exception as exc:
        update_research_run(
            run_id,
            status="failed",
            current_stage="Research failed",
            error="Research failed unexpectedly. Check the server logs.",
        )
        logger.exception(
            "run_id=%s event=job_failed_unexpected error_type=%s",
            run_id,
            type(exc).__name__,
        )
    finally:
        request_id_context.reset(token)


def new_research_run_id() -> str:
    return uuid4().hex
