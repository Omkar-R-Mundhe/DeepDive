from datetime import datetime, timezone
from urllib.parse import urlparse
from uuid import uuid4

import httpx

from app.config import get_required_setting
from app.schemas.research import EvidenceRecord

BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"


class ResearchProviderError(RuntimeError):
    pass


def search_sources(query: str, count: int = 5) -> list[EvidenceRecord]:
    api_key = get_required_setting("BRAVE_SEARCH_API_KEY")
    try:
        response = httpx.get(
            BRAVE_SEARCH_URL,
            headers={
                "Accept": "application/json",
                "X-Subscription-Token": api_key,
            },
            params={"q": query, "count": count},
            timeout=15.0,
        )
        response.raise_for_status()
        payload = response.json()
    except httpx.HTTPStatusError as exc:
        details = exc.response.text[:1000]
        message = (
            f"Brave Search returned HTTP {exc.response.status_code}: {details}"
        )
        raise ResearchProviderError(message.replace(api_key, "[REDACTED]")) from exc
    except httpx.HTTPError as exc:
        message = str(exc).replace(api_key, "[REDACTED]")
        raise ResearchProviderError(f"Brave Search request failed: {message}") from exc
    except ValueError as exc:
        raise ResearchProviderError(
            "Brave Search returned invalid JSON."
        ) from exc

    if not isinstance(payload, dict):
        raise ResearchProviderError("Brave Search returned an invalid response.")

    web_results = payload.get("web", {})
    if not isinstance(web_results, dict):
        raise ResearchProviderError("Brave Search returned an invalid web result.")
    results = web_results.get("results", [])
    if not isinstance(results, list):
        raise ResearchProviderError("Brave Search returned an invalid results list.")

    retrieved_at = datetime.now(timezone.utc)
    evidence: list[EvidenceRecord] = []
    for result in results:
        if not isinstance(result, dict):
            continue

        title = result.get("title")
        source_url = result.get("url")
        passage = result.get("description")
        if not all(isinstance(value, str) and value.strip() for value in (
            title,
            source_url,
            passage,
        )):
            continue

        parsed_url = urlparse(source_url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            continue

        evidence.append(
            EvidenceRecord(
                evidence_id=f"E-{uuid4().hex[:12]}",
                query=query,
                source_url=source_url,
                source_title=title,
                retrieved_at=retrieved_at,
                passage=passage,
            )
        )

    if not evidence:
        raise ResearchProviderError(
            "Brave Search returned no results with usable source snippets."
        )

    return evidence
