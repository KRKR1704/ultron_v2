"""
tools/web_search.py — Web search via Tavily API.
"""

import logging
import os

from dotenv import load_dotenv

load_dotenv()
log = logging.getLogger(__name__)

_TAVILY_KEY = os.getenv("TAVILY_API_KEY", "")


async def search(query: str, max_results: int = 5) -> str:
    """
    Search the web for *query* using Tavily and return a formatted summary string.
    Returns a graceful error message if Tavily is unavailable or unconfigured.
    """
    if not query.strip():
        return "No search query provided."

    if not _TAVILY_KEY:
        return (
            f"I would search for '{query}', but the Tavily API key is not configured. "
            "Add TAVILY_API_KEY to your .env file."
        )

    try:
        from tavily import TavilyClient

        client = TavilyClient(api_key=_TAVILY_KEY)
        results = client.search(
            query=query,
            search_depth="basic",
            max_results=max_results,
        )

        if not results or not results.get("results"):
            return f"No results found for: {query}"

        lines: list[str] = [f"Search results for: {query}\n"]
        for i, r in enumerate(results["results"][:max_results], 1):
            title = r.get("title", "")
            url = r.get("url", "")
            snippet = r.get("content", r.get("snippet", ""))[:300]
            lines.append(f"{i}. {title}\n   {url}\n   {snippet}\n")

        return "\n".join(lines)

    except ImportError:
        return "Tavily is not installed. Run: pip install tavily-python"
    except Exception as err:
        log.error("Tavily search error: %s", err)
        return f"Search failed: {err}"
