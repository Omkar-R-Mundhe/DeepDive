from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from openai import OpenAIError

from app.services import llm_client
from app.services.llm_client import MeshAPIError


def test_ask_model_uses_mesh_configuration_and_returns_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mesh_client = Mock()
    mesh_client.chat.completions.create.return_value = SimpleNamespace(
        choices=[
            SimpleNamespace(message=SimpleNamespace(content="Hello from Mesh"))
        ]
    )
    settings = {"MESH_API_KEY": "test-key", "MESH_MODEL": "openai/gpt-4o"}
    monkeypatch.setattr(
        llm_client, "get_required_setting", lambda name: settings[name]
    )
    monkeypatch.setattr(
        llm_client, "OpenAI", lambda **_: mesh_client
    )

    answer = llm_client.ask_model("Hello")

    assert answer == "Hello from Mesh"
    mesh_client.chat.completions.create.assert_called_once_with(
        model="openai/gpt-4o",
        messages=[{"role": "user", "content": "Hello"}],
    )


def test_ask_model_preserves_mesh_error_and_redacts_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api_key = "secret-test-key"
    upstream_error = "Error code: 402 - insufficient balance"
    mesh_client = Mock()
    mesh_client.chat.completions.create.side_effect = OpenAIError(
        f"{upstream_error}; credential={api_key}"
    )
    settings = {"MESH_API_KEY": api_key, "MESH_MODEL": "openai/gpt-4o"}
    monkeypatch.setattr(
        llm_client, "get_required_setting", lambda name: settings[name]
    )
    monkeypatch.setattr(llm_client, "OpenAI", lambda **_: mesh_client)

    with pytest.raises(MeshAPIError) as error:
        llm_client.ask_model("Hello")

    assert str(error.value) == f"{upstream_error}; credential=[REDACTED]"
    assert api_key not in str(error.value)
