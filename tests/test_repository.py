import sqlite3

from app.database.repository import (
    create_research_run,
    fail_incomplete_research_runs,
    get_research_run,
    save_evidence,
    update_research_run,
)
from app.schemas.research import (
    EvidenceRecord,
    ResearchPlan,
    ResearchReport,
    ResearchReportSection,
    ResearchRunResponse,
)


def test_save_evidence_persists_source_provenance(tmp_path) -> None:
    database_path = tmp_path / "data" / "test.sqlite3"
    record = EvidenceRecord(
        evidence_id="E-test123",
        query="urban trees",
        source_url="https://example.org/tree-study",
        source_title="Urban tree study",
        retrieved_at="2026-10-12T16:00:00+00:00",
        passage="Tree cover can reduce local temperatures.",
    )

    save_evidence([record], database_path)

    with sqlite3.connect(database_path) as connection:
        saved = connection.execute(
            """
            SELECT evidence_id, query, source_url, source_title, passage, source_type
            FROM evidence
            """
        ).fetchone()

    assert saved == (
        "E-test123",
        "urban trees",
        "https://example.org/tree-study",
        "Urban tree study",
        "Tree cover can reduce local temperatures.",
        "search_snippet",
    )


def test_research_run_status_and_result_are_persisted(tmp_path) -> None:
    database_path = tmp_path / "data" / "test.sqlite3"
    run_id = "run-123"
    result = ResearchRunResponse(
        question="Research question",
        report=ResearchReport(
            answer="A synthesized answer.",
            sections=[
                ResearchReportSection(
                    heading="Finding",
                    body="A verified finding.",
                    evidence_ids=[],
                )
            ],
        ),
        plan=ResearchPlan(
            sub_questions=["Question one?", "Question two?", "Question three?"],
            scope_boundaries=["Current evidence."],
            recommended_source_types=["Research papers"],
        ),
        evidence=[],
        claims=[],
        verifications=[],
    )

    create_research_run(run_id, "Research question", 2, database_path)
    update_research_run(
        run_id,
        status="running",
        current_stage="Searching sub-question 1 of 3",
        database_path=database_path,
    )

    running = get_research_run(run_id, database_path)
    assert running is not None
    assert running["status"] == "running"
    assert running["current_stage"] == "Searching sub-question 1 of 3"

    update_research_run(
        run_id,
        status="completed",
        current_stage="Research complete",
        result=result,
        database_path=database_path,
    )

    completed = get_research_run(run_id, database_path)
    assert completed is not None
    assert completed["status"] == "completed"
    assert completed["result"]["question"] == "Research question"


def test_startup_marks_interrupted_jobs_failed(tmp_path) -> None:
    database_path = tmp_path / "data" / "test.sqlite3"
    create_research_run("run-456", "Research question", 2, database_path)
    update_research_run(
        "run-456",
        status="running",
        current_stage="Drafting claims",
        database_path=database_path,
    )

    fail_incomplete_research_runs(database_path)

    run = get_research_run("run-456", database_path)
    assert run is not None
    assert run["status"] == "failed"
    assert run["current_stage"] == "Research interrupted by server restart"
    assert "server restarted" in run["error"]
