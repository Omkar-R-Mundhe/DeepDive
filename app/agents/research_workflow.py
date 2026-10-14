import logging
from collections.abc import Callable

from app.agents.claim_drafter import draft_claims
from app.agents.planner import create_research_plan
from app.agents.report_writer import write_research_report
from app.agents.researcher import search_sources
from app.agents.verifier import verify_claims
from app.database.repository import save_evidence
from app.logging_utils import log_event, log_stage
from app.schemas.research import EvidenceRecord, ResearchRunResponse

logger = logging.getLogger(__name__)


def run_research(
    question: str,
    results_per_query: int = 3,
    progress_callback: Callable[[str], None] | None = None,
) -> ResearchRunResponse:
    if progress_callback is not None:
        progress_callback("Planning research")
    with log_stage(logger, "workflow.plan"):
        plan = create_research_plan(question)

    evidence: list[EvidenceRecord] = []
    for index, sub_question in enumerate(plan.sub_questions, start=1):
        if progress_callback is not None:
            progress_callback(
                f"Searching sub-question {index} of {len(plan.sub_questions)}"
            )
        with log_stage(
            logger,
            "workflow.search",
            sub_question_index=index,
            sub_question_count=len(plan.sub_questions),
            results_per_query=results_per_query,
        ):
            evidence.extend(search_sources(sub_question, results_per_query))

    if progress_callback is not None:
        progress_callback(f"Saving {len(evidence)} evidence records")
    with log_stage(logger, "workflow.persist_evidence", evidence_count=len(evidence)):
        save_evidence(evidence)

    if progress_callback is not None:
        progress_callback("Drafting claims")
    with log_stage(logger, "workflow.draft_claims", evidence_count=len(evidence)):
        claims = draft_claims(question, evidence)

    if progress_callback is not None:
        progress_callback(f"Verifying {len(claims)} claims")
    with log_stage(
        logger,
        "workflow.verify_claims",
        claim_count=len(claims),
        evidence_count=len(evidence),
    ):
        verifications = verify_claims(claims, evidence)

    if progress_callback is not None:
        progress_callback("Writing research answer")
    with log_stage(
        logger,
        "workflow.write_report",
        verification_count=len(verifications),
    ):
        report = write_research_report(question, verifications, evidence)

    log_event(
        logger,
        "workflow",
        "completed",
        sub_question_count=len(plan.sub_questions),
        evidence_count=len(evidence),
        claim_count=len(claims),
        verification_count=len(verifications),
        report_section_count=len(report.sections),
    )
    return ResearchRunResponse(
        question=question,
        report=report,
        plan=plan,
        evidence=evidence,
        claims=claims,
        verifications=verifications,
    )
