from openai import OpenAI, OpenAIError

from app.config import get_required_setting

MESH_BASE_URL = "https://api.meshapi.ai/v1"


class MeshAPIError(RuntimeError):
    pass


def ask_model(question: str) -> str:
    api_key = get_required_setting("MESH_API_KEY")
    model = get_required_setting("MESH_MODEL")
    client = OpenAI(base_url=MESH_BASE_URL, api_key=api_key)

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": question}],
        )
    except OpenAIError as exc:
        error_message = str(exc).replace(api_key, "[REDACTED]")
        raise MeshAPIError(error_message) from exc

    if not response.choices or response.choices[0].message.content is None:
        raise MeshAPIError("The Mesh API returned no answer.")

    return response.choices[0].message.content
