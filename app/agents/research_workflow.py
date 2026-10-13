import logging

from app.agents.claim_drafter import draft_claims
from app.agents.planner import create_research_plan
from app.agents.researcher import search_sources
from app.agents.verifier import verify_claims
from app.database.repository import save_evidence
from app.logging_utils import log_event, log_stage
from app.schemas.research import EvidenceRecord, ResearchRunResponse

logger = logging.getLogger(__name__)


def run_research(question: str, results_per_query: int = 3) -> ResearchRunResponse:
    with log_stage(logger, "workflow.plan"):
        plan = create_research_plan(question)

    evidence: list[EvidenceRecord] = []
    for index, sub_question in enumerate(plan.sub_questions, start=1):
        with log_stage(
            logger,
            "workflow.search",
            sub_question_index=index,
            sub_question_count=len(plan.sub_questions),
            results_per_query=results_per_query,
        ):
            evidence.extend(search_sources(sub_question, results_per_query))

    with log_stage(logger, "workflow.persist_evidence", evidence_count=len(evidence)):
        save_evidence(evidence)

    with log_stage(logger, "workflow.draft_claims", evidence_count=len(evidence)):
        claims = draft_claims(question, evidence)

    with log_stage(
        logger,
        "workflow.verify_claims",
        claim_count=len(claims),
        evidence_count=len(evidence),
    ):
        verifications = verify_claims(claims, evidence)

    log_event(
        logger,
        "workflow",
        "completed",
        sub_question_count=len(plan.sub_questions),
        evidence_count=len(evidence),
        claim_count=len(claims),
        verification_count=len(verifications),
    )
    return ResearchRunResponse(
        question=question,
        plan=plan,
        evidence=evidence,
        claims=claims,
        verifications=verifications,
    )
