from openai import OpenAI, OpenAIError

from app.config import ConfigurationError, get_required_setting, get_setting

MESH_BASE_URL = "https://api.meshapi.ai/v1"
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"


class LLMProviderError(RuntimeError):
    pass


def ask_model(question: str) -> str:
    provider = get_setting("LLM_PROVIDER", "mesh").lower()
    provider_settings = {
        "mesh": ("MESH_API_KEY", "MESH_MODEL", MESH_BASE_URL),
        "gemini": ("GEMINI_API_KEY", "GEMINI_MODEL", GEMINI_BASE_URL),
    }
    if provider not in provider_settings:
        raise ConfigurationError(
            "LLM_PROVIDER must be either 'mesh' or 'gemini'."
        )

    try:
        api_key_name, model_name, base_url = provider_settings[provider]
        api_key = get_required_setting(api_key_name)
        model = get_required_setting(model_name)
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

    if not response.choices or response.choices[0].message.content is None:
        raise LLMProviderError(f"The {provider} API returned no answer.")

    return response.choices[0].message.content
