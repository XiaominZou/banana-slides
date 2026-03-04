"""Tool: Call Zhipu Web Search + Chat Model for in-depth research on a topic."""
from __future__ import annotations

import logging

from ..config import settings
from ..services.llm_service import LLMService
from ..services.search_service import SearchService

logger = logging.getLogger(__name__)

RESEARCH_PROMPT = """\
Please provide a comprehensive research report on the following topic for creating a professional presentation.

Topic: {topic}

The report should include:
1. Overview and background
2. Key points and main arguments
3. Important data, statistics, or facts
4. Current trends and developments
5. Different perspectives or viewpoints
6. Conclusions and future outlook

Format the report in a structured way with clear sections.
Respond in the same language as the topic.
"""


async def deepseek_research(topic: str) -> str:
    """Use Zhipu Web Search + Chat Model to generate a comprehensive research report."""
    
    # Search for information using Zhipu
    search_service = SearchService()
    search_service.provider = "zhipu_mcp"  # Force use Zhipu for research
    search_service.zhipu_mcp_api_key = settings.zhipu_mcp_api_key
    
    try:
        # Search multiple queries to gather comprehensive information
        search_result = await search_service.search(topic, max_results=10)
        
        # Extract search results for context
        search_context = []
        for r in search_result.get("results", [])[:10]:
            title = r.get("title", "")
            url = r.get("url", "")
            snippet = r.get("snippet", "")
            if title:
                search_context.append(f"- {title}\n  URL: {url}\n  Summary: {snippet}\n")
        
        search_context_str = "\n".join(search_context)
        
        # Generate research report using LLM with search context
        llm = LLMService(
            base_url=settings.chat_model_base_url,
            api_key=settings.chat_model_api_key,
            model_name=settings.chat_model_name,
        )

        messages = [
            {
                "role": "system",
                "content": "You are a research assistant. Provide thorough, well-structured research reports based on web search results."
            },
            {
                "role": "user",
                "content": f"""I need to research the following topic for a presentation:

{topic}

I have gathered some initial information from web search:

{search_context_str}

Please provide a comprehensive research report including:
1. Overview and background
2. Key points and main arguments
3. Important data, statistics, or facts
4. Current trends and developments
5. Different perspectives or viewpoints
6. Conclusions and future outlook

Format the report in a structured way with clear sections.
Respond in the same language as the topic."""
            },
        ]
        
        result = await llm.chat(messages, temperature=0.3, max_tokens=16384)
        return result
        
    except Exception as e:
        logger.exception("Research generation failed: %s", e)
        return f"Research generation failed: {e}. Using topic directly: {topic}"
