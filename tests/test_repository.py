import sqlite3

from app.database.repository import save_evidence
from app.schemas.research import EvidenceRecord


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
