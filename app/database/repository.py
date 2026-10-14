import sqlite3
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from app.schemas.research import EvidenceRecord, ResearchRunResponse

DEFAULT_DATABASE_PATH = Path("data/deepdive.sqlite3")
ResearchJobState = Literal["queued", "running", "completed", "failed"]


def _ensure_research_runs_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS research_runs (
            run_id TEXT PRIMARY KEY,
            question TEXT NOT NULL,
            results_per_query INTEGER NOT NULL,
            status TEXT NOT NULL CHECK (
                status IN ('queued', 'running', 'completed', 'failed')
            ),
            current_stage TEXT,
            error TEXT,
            result_json TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )


def create_research_run(
    run_id: str,
    question: str,
    results_per_query: int,
    database_path: Path = DEFAULT_DATABASE_PATH,
) -> None:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(database_path) as connection:
        _ensure_research_runs_table(connection)
        connection.execute(
            """
            INSERT INTO research_runs (
                run_id, question, results_per_query, status, current_stage,
                error, result_json, created_at, updated_at
            )
            VALUES (?, ?, ?, 'queued', 'Waiting to start', NULL, NULL, ?, ?)
            """,
            (run_id, question, results_per_query, now, now),
        )


def update_research_run(
    run_id: str,
    status: ResearchJobState,
    current_stage: str,
    error: str | None = None,
    result: ResearchRunResponse | None = None,
    database_path: Path = DEFAULT_DATABASE_PATH,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    result_json = (
        result.model_dump_json()
        if result is not None
        else None
    )
    with sqlite3.connect(database_path) as connection:
        _ensure_research_runs_table(connection)
        cursor = connection.execute(
            """
            UPDATE research_runs
            SET status = ?, current_stage = ?, error = ?, result_json = ?,
                updated_at = ?
            WHERE run_id = ?
            """,
            (status, current_stage, error, result_json, now, run_id),
        )
        if cursor.rowcount != 1:
            raise LookupError(f"Research run {run_id} does not exist.")


def get_research_run(
    run_id: str,
    database_path: Path = DEFAULT_DATABASE_PATH,
) -> dict[str, object] | None:
    if not database_path.exists():
        return None
    with sqlite3.connect(database_path) as connection:
        _ensure_research_runs_table(connection)
        row = connection.execute(
            """
            SELECT run_id, status, current_stage, error, created_at, updated_at,
                   result_json
            FROM research_runs
            WHERE run_id = ?
            """,
            (run_id,),
        ).fetchone()
    if row is None:
        return None

    return {
        "run_id": row[0],
        "status": row[1],
        "current_stage": row[2],
        "error": row[3],
        "created_at": row[4],
        "updated_at": row[5],
        "result": json.loads(row[6]) if row[6] is not None else None,
    }


def fail_incomplete_research_runs(
    database_path: Path = DEFAULT_DATABASE_PATH,
) -> None:
    if not database_path.exists():
        return
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(database_path) as connection:
        _ensure_research_runs_table(connection)
        connection.execute(
            """
            UPDATE research_runs
            SET status = 'failed',
                current_stage = 'Research interrupted by server restart',
                error = 'The server restarted before this research run completed.',
                updated_at = ?
            WHERE status IN ('queued', 'running')
            """,
            (now,),
        )


def save_evidence(
    records: list[EvidenceRecord],
    database_path: Path = DEFAULT_DATABASE_PATH,
) -> None:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS evidence (
                evidence_id TEXT PRIMARY KEY,
                query TEXT NOT NULL,
                source_url TEXT NOT NULL,
                source_title TEXT NOT NULL,
                retrieved_at TEXT NOT NULL,
                passage TEXT NOT NULL,
                source_type TEXT NOT NULL
            )
            """
        )
        connection.executemany(
            """
            INSERT INTO evidence (
                evidence_id,
                query,
                source_url,
                source_title,
                retrieved_at,
                passage,
                source_type
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    record.evidence_id,
                    record.query,
                    record.source_url,
                    record.source_title,
                    record.retrieved_at.isoformat(),
                    record.passage,
                    record.source_type,
                )
                for record in records
            ],
        )
