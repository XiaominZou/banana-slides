"""Tool: Web search for topic content and images."""
from __future__ import annotations

import logging

from ..services.search_service import SearchService

logger = logging.getLogger(__name__)


async def web_search(query: str, max_results: int = 10) -> dict:
    """
    Search the web for content related to the query.
    Returns {"answer": str, "results": [...], "images": [...]}.
    """
    service = SearchService()
    try:
        result = await service.search(query, max_results=max_results, include_images=True)
        return result
    except Exception as e:
        logger.exception("Web search failed")
        return {
            "answer": "",
            "results": [],
            "images": [],
            "error": str(e),
        }


def format_search_results(search_data: dict) -> str:
    """Format search results into readable text for the LLM."""
    parts = []

    if search_data.get("answer"):
        parts.append(f"Summary: {search_data['answer']}\n")

    for i, r in enumerate(search_data.get("results", []), 1):
        parts.append(f"{i}. [{r['title']}]({r['url']})")
        parts.append(f"   {r['snippet']}\n")

    if search_data.get("images"):
        parts.append("\nRelated Images:")
        for img in search_data["images"][:5]:
            desc = img.get("description", "Image")
            parts.append(f"  - {desc}: {img['url']}")

    return "\n".join(parts)
