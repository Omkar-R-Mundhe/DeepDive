import logging
from datetime import datetime, timezone
from urllib.parse import urlparse
from uuid import uuid4

import httpx

from app.config import ConfigurationError, get_required_setting, get_setting
from app.logging_utils import log_event, log_stage
from app.schemas.research import EvidenceRecord

BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"
TAVILY_SEARCH_URL = "https://api.tavily.com/search"


class ResearchProviderError(RuntimeError):
    pass


logger = logging.getLogger(__name__)


def search_sources(query: str, count: int = 5) -> list[EvidenceRecord]:
    provider = get_setting("SEARCH_PROVIDER", "tavily").lower()
    if provider not in {"brave", "tavily"}:
        raise ConfigurationError(
            "SEARCH_PROVIDER must be either 'brave' or 'tavily'."
        )

    api_key_name = (
        "TAVILY_API_KEY" if provider == "tavily" else "BRAVE_SEARCH_API_KEY"
    )
    with log_stage(logger, "search.configure", provider=provider):
        api_key = get_required_setting(api_key_name)

    try:
        with log_stage(
            logger,
            "search.request",
            provider=provider,
            requested_count=count,
        ):
            if provider == "tavily":
                response = httpx.post(
                    TAVILY_SEARCH_URL,
                    headers={
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {api_key}",
                    },
                    json={
                        "query": query,
                        "max_results": count,
                        "search_depth": "basic",
                        "include_answer": False,
                    },
                    timeout=15.0,
                )
            else:
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
            f"{provider.title()} Search returned HTTP "
            f"{exc.response.status_code}: {details}"
        )
        raise ResearchProviderError(message.replace(api_key, "[REDACTED]")) from exc
    except httpx.HTTPError as exc:
        message = str(exc).replace(api_key, "[REDACTED]")
        raise ResearchProviderError(
            f"{provider.title()} Search request failed: {message}"
        ) from exc
    except ValueError as exc:
        raise ResearchProviderError(
            f"{provider.title()} Search returned invalid JSON."
        ) from exc

    with log_stage(logger, "search.parse_results", provider=provider):
        if not isinstance(payload, dict):
            raise ResearchProviderError(
                f"{provider.title()} Search returned an invalid response."
            )

        if provider == "tavily":
            results = payload.get("results", [])
        else:
            web_results = payload.get("web", {})
            if not isinstance(web_results, dict):
                raise ResearchProviderError(
                    "Brave Search returned an invalid web result."
                )
            results = web_results.get("results", [])
        if not isinstance(results, list):
            raise ResearchProviderError(
                f"{provider.title()} Search returned an invalid results list."
            )

    retrieved_at = datetime.now(timezone.utc)
    evidence: list[EvidenceRecord] = []
    for result in results:
        if not isinstance(result, dict):
            continue

        title = result.get("title")
        source_url = result.get("url")
        passage = result.get(
            "content" if provider == "tavily" else "description"
        )
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
            f"{provider.title()} Search returned no results with usable source snippets."
        )

    log_event(
        logger,
        "search.results",
        "usable",
        provider=provider,
        received_count=len(results),
        usable_count=len(evidence),
    )
    return evidence
