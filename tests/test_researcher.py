import httpx
import pytest

from app.agents import researcher
from app.agents.researcher import ResearchProviderError


def test_search_sources_uses_tavily_and_returns_provenanced_snippets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request_details = {}
    response = httpx.Response(
        200,
        json={
            "results": [
                {
                    "title": "Urban tree study",
                    "url": "https://example.org/tree-study",
                    "content": "Tree cover can reduce local temperatures.",
                },
                {
                    "title": "Unsafe scheme",
                    "url": "javascript:alert(1)",
                    "content": "Not an acceptable source URL.",
                },
            ]
        },
        request=httpx.Request("POST", researcher.TAVILY_SEARCH_URL),
    )

    def fake_post(url: str, **kwargs: object) -> httpx.Response:
        request_details["url"] = url
        request_details.update(kwargs)
        return response

    monkeypatch.setattr(
        researcher,
        "get_setting",
        lambda name, default: "tavily" if name == "SEARCH_PROVIDER" else default,
    )
    monkeypatch.setattr(researcher, "get_required_setting", lambda _: "test-token")
    monkeypatch.setattr(researcher.httpx, "post", fake_post)

    evidence = researcher.search_sources("urban trees", count=4)

    assert len(evidence) == 1
    assert evidence[0].evidence_id.startswith("E-")
    assert evidence[0].query == "urban trees"
    assert evidence[0].source_url == "https://example.org/tree-study"
    assert evidence[0].source_title == "Urban tree study"
    assert evidence[0].passage == "Tree cover can reduce local temperatures."
    assert evidence[0].source_type == "search_snippet"
    assert request_details["url"] == researcher.TAVILY_SEARCH_URL
    assert request_details["headers"]["Authorization"] == "Bearer test-token"
    assert request_details["json"] == {
        "query": "urban trees",
        "max_results": 4,
        "search_depth": "basic",
        "include_answer": False,
    }


def test_search_sources_returns_provenanced_snippets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request_details = {}
    response = httpx.Response(
        200,
        json={
            "web": {
                "results": [
                    {
                        "title": "Urban tree study",
                        "url": "https://example.org/tree-study",
                        "description": "Tree cover can reduce local temperatures.",
                    },
                    {
                        "title": "Unsafe scheme",
                        "url": "javascript:alert(1)",
                        "description": "Not an acceptable source URL.",
                    },
                ]
            }
        },
        request=httpx.Request("GET", researcher.BRAVE_SEARCH_URL),
    )

    def fake_get(url: str, **kwargs: object) -> httpx.Response:
        request_details["url"] = url
        request_details.update(kwargs)
        return response

    monkeypatch.setattr(
        researcher, "get_setting", lambda name, default: "brave"
    )
    monkeypatch.setattr(researcher, "get_required_setting", lambda _: "test-token")
    monkeypatch.setattr(researcher.httpx, "get", fake_get)

    evidence = researcher.search_sources("urban trees", count=4)

    assert len(evidence) == 1
    assert evidence[0].evidence_id.startswith("E-")
    assert evidence[0].query == "urban trees"
    assert evidence[0].source_url == "https://example.org/tree-study"
    assert evidence[0].source_title == "Urban tree study"
    assert evidence[0].passage == "Tree cover can reduce local temperatures."
    assert evidence[0].source_type == "search_snippet"
    assert request_details["url"] == researcher.BRAVE_SEARCH_URL
    assert request_details["headers"]["X-Subscription-Token"] == "test-token"
    assert request_details["params"] == {"q": "urban trees", "count": 4}


def test_search_sources_redacts_key_from_provider_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api_key = "test-brave-secret"
    request = httpx.Request("GET", researcher.BRAVE_SEARCH_URL)
    response = httpx.Response(
        401,
        text=f'{{"error":"invalid token: {api_key}"}}',
        request=request,
    )
    monkeypatch.setattr(
        researcher, "get_setting", lambda name, default: "brave"
    )
    monkeypatch.setattr(researcher, "get_required_setting", lambda _: api_key)

    def failed_get(*args: object, **kwargs: object) -> httpx.Response:
        raise httpx.HTTPStatusError(
            "Unauthorized",
            request=request,
            response=response,
        )

    monkeypatch.setattr(researcher.httpx, "get", failed_get)

    with pytest.raises(ResearchProviderError) as error:
        researcher.search_sources("urban trees")

    assert "HTTP 401" in str(error.value)
    assert "[REDACTED]" in str(error.value)
    assert api_key not in str(error.value)


def test_search_sources_rejects_invalid_provider_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = httpx.Response(
        200,
        json=[],
        request=httpx.Request("GET", researcher.BRAVE_SEARCH_URL),
    )
    monkeypatch.setattr(
        researcher, "get_setting", lambda name, default: "brave"
    )
    monkeypatch.setattr(researcher, "get_required_setting", lambda _: "test-token")
    monkeypatch.setattr(researcher.httpx, "get", lambda *args, **kwargs: response)

    with pytest.raises(ResearchProviderError, match="invalid response"):
        researcher.search_sources("urban trees")
