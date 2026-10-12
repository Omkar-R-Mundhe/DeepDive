import sqlite3
from pathlib import Path

from app.schemas.research import EvidenceRecord

DEFAULT_DATABASE_PATH = Path("data/deepdive.sqlite3")


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
