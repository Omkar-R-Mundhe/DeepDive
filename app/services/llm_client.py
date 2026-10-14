import logging

from openai import OpenAI, OpenAIError

from app.config import ConfigurationError, get_required_setting, get_setting
from app.logging_utils import log_event, log_stage

MESH_BASE_URL = "https://api.meshapi.ai/v1"
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class LLMProviderError(RuntimeError):
    pass


logger = logging.getLogger(__name__)


def ask_model(question: str) -> str:
    provider = get_setting("LLM_PROVIDER", "mesh").lower()
    provider_settings = {
        "mesh": ("MESH_API_KEY", "MESH_MODEL", MESH_BASE_URL),
        "gemini": ("GEMINI_API_KEY", "GEMINI_MODEL", GEMINI_BASE_URL),
        "openrouter": (
            "OPENROUTER_API_KEY",
            "OPENROUTER_MODEL",
            OPENROUTER_BASE_URL,
        ),
    }
    if provider not in provider_settings:
        raise ConfigurationError(
            "LLM_PROVIDER must be 'mesh', 'gemini', or 'openrouter'."
        )

    try:
        with log_stage(logger, "llm.configure", provider=provider):
            api_key_name, model_name, base_url = provider_settings[provider]
            api_key = get_required_setting(api_key_name)
            model = get_required_setting(model_name)
        with log_stage(
            logger,
            "llm.request",
            heartbeat_interval_seconds=15,
            provider=provider,
            model=model,
        ):
            client = OpenAI(base_url=base_url, api_key=api_key)
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": question}],
            )
    except ConfigurationError:
        raise
    except OpenAIError as exc:
        error_message = str(exc).replace(api_key, "[REDACTED]")
        raise LLMProviderError(error_message) from exc

    choices = response.choices
    message = choices[0].message if choices else None
    content = message.content if message is not None else None
    if not isinstance(content, str) or not content.strip():
        finish_reason = choices[0].finish_reason if choices else None
        refusal_present = bool(getattr(message, "refusal", None))
        tool_call_count = len(getattr(message, "tool_calls", None) or [])
        log_event(
            logger,
            "llm.response",
            "no_text",
            provider=provider,
            model=model,
            choice_count=len(choices),
            finish_reason=finish_reason or "unknown",
            refusal_present=refusal_present,
            tool_call_count=tool_call_count,
        )
        raise LLMProviderError(
            f"The {provider} model '{model}' completed without returning text "
            f"(finish_reason={finish_reason or 'unknown'})."
        )

    log_event(logger, "llm.response", "received", provider=provider)
    return content
