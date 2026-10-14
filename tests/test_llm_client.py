from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from openai import OpenAIError

from app.services import llm_client
from app.services.llm_client import LLMProviderError


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
    monkeypatch.setattr(llm_client, "get_setting", lambda name, default: default)
    monkeypatch.setattr(
        llm_client, "OpenAI", lambda **_: mesh_client
    )

    answer = llm_client.ask_model("Hello")

    assert answer == "Hello from Mesh"
    mesh_client.chat.completions.create.assert_called_once_with(
        model="openai/gpt-4o",
        messages=[{"role": "user", "content": "Hello"}],
    )
    assert llm_client.MESH_BASE_URL == "https://api.meshapi.ai/v1"


def test_ask_model_uses_gemini_settings_and_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mesh_client = Mock()
    mesh_client.chat.completions.create.return_value = SimpleNamespace(
        choices=[
            SimpleNamespace(message=SimpleNamespace(content="Hello from Gemini"))
        ]
    )
    settings = {
        "GEMINI_API_KEY": "test-gemini-key",
        "GEMINI_MODEL": "gemini-3.8-flash",
    }
    client_options = {}
    monkeypatch.setattr(
        llm_client, "get_required_setting", lambda name: settings[name]
    )
    monkeypatch.setattr(
        llm_client, "get_setting", lambda name, default: "gemini"
    )
    monkeypatch.setattr(
        llm_client,
        "OpenAI",
        lambda **kwargs: client_options.update(kwargs) or mesh_client,
    )

    answer = llm_client.ask_model("Hello")

    assert answer == "Hello from Gemini"
    assert client_options == {
        "base_url": llm_client.GEMINI_BASE_URL,
        "api_key": "test-gemini-key",
    }
    mesh_client.chat.completions.create.assert_called_once_with(
        model="gemini-3.8-flash",
        messages=[{"role": "user", "content": "Hello"}],
    )


def test_ask_model_uses_openrouter_settings_and_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = Mock()
    client.chat.completions.create.return_value = SimpleNamespace(
        choices=[
            SimpleNamespace(message=SimpleNamespace(content="Hello from OpenRouter"))
        ]
    )
    settings = {
        "OPENROUTER_API_KEY": "test-openrouter-key",
        "OPENROUTER_MODEL": "openai/gpt-4o-mini",
    }
    client_options = {}
    monkeypatch.setattr(
        llm_client, "get_required_setting", lambda name: settings[name]
    )
    monkeypatch.setattr(
        llm_client, "get_setting", lambda name, default: "openrouter"
    )
    monkeypatch.setattr(
        llm_client,
        "OpenAI",
        lambda **kwargs: client_options.update(kwargs) or client,
    )

    answer = llm_client.ask_model("Hello")

    assert answer == "Hello from OpenRouter"
    assert client_options == {
        "base_url": llm_client.OPENROUTER_BASE_URL,
        "api_key": "test-openrouter-key",
    }
    client.chat.completions.create.assert_called_once_with(
        model="openai/gpt-4o-mini",
        messages=[{"role": "user", "content": "Hello"}],
    )


def test_ask_model_reports_successful_completion_without_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = Mock()
    client.chat.completions.create.return_value = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content=None,
                    refusal=None,
                    tool_calls=None,
                ),
                finish_reason="length",
            )
        ]
    )
    settings = {
        "OPENROUTER_API_KEY": "test-openrouter-key",
        "OPENROUTER_MODEL": "dots-studio/dots-3-note-preview:free",
    }
    monkeypatch.setattr(
        llm_client, "get_required_setting", lambda name: settings[name]
    )
    monkeypatch.setattr(
        llm_client, "get_setting", lambda name, default: "openrouter"
    )
    monkeypatch.setattr(llm_client, "OpenAI", lambda **_: client)

    with pytest.raises(LLMProviderError, match="completed without returning text"):
        llm_client.ask_model("Return a JSON object.")


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
    monkeypatch.setattr(llm_client, "get_setting", lambda name, default: default)
    monkeypatch.setattr(llm_client, "OpenAI", lambda **_: mesh_client)

    with pytest.raises(LLMProviderError) as error:
        llm_client.ask_model("Hello")

    assert str(error.value) == f"{upstream_error}; credential=[REDACTED]"
    assert api_key not in str(error.value)
