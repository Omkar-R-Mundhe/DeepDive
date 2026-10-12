import pytest
from fastapi.testclient import TestClient

from app import main
from app.config import ConfigurationError
from app.services.llm_client import MeshAPIError

client = TestClient(main.app)


def test_health_returns_ok() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ask_returns_model_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main, "ask_model", lambda question: f"Answer to: {question}")

    response = client.post("/api/v1/ask", json={"question": "Hello"})

    assert response.status_code == 200
    assert response.json() == {"answer": "Answer to: Hello"}


def test_ask_rejects_blank_question() -> None:
    response = client.post("/api/v1/ask", json={"question": "   "})

    assert response.status_code == 422


def test_ask_reports_missing_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing_setting(_: str) -> str:
        raise ConfigurationError("Required setting MESH_API_KEY is missing or empty.")

    monkeypatch.setattr(main, "ask_model", missing_setting)

    response = client.post("/api/v1/ask", json={"question": "Hello"})

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Required setting MESH_API_KEY is missing or empty."
    }


def test_ask_reports_mesh_api_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    upstream_error = "Error code: 402 - insufficient balance"

    def failed_request(_: str) -> str:
        raise MeshAPIError(upstream_error)

    monkeypatch.setattr(main, "ask_model", failed_request)

    response = client.post("/api/v1/ask", json={"question": "Hello"})

    assert response.status_code == 502
    assert response.json() == {"detail": upstream_error}
