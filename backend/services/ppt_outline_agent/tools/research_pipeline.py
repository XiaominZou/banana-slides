"""Multi-step deep research pipeline for the Plan Agent.

Implements a 6-step iterative research flow:
  1. Analyze topic → identify key dimensions
  2. Parallel multi-query search across dimensions
  3. Extract structured insights from search results
  4. Identify research gaps
  5. Targeted gap-filling searches
  6. Synthesize all findings into a structured report

Designed to produce richer source material than a single search call.
"""
from __future__ import annotations

import asyncio
import logging
from contextvars import ContextVar
from typing import Optional

from .web_search import format_search_results, web_search
from ..config import settings
from ..services.llm_service import LLMService

logger = logging.getLogger(__name__)

# ContextVar for storing progress callback across async calls
_progress_callback_var = ContextVar('progress_callback', default=None)

# ── Prompts ──────────────────────────────────────────────────────

_DIMENSION_PROMPT = """\
Analyze the following presentation topic and identify 4-6 key research dimensions \
(e.g. market size, technology trends, competitive landscape, use cases, challenges, \
future outlook).

For each dimension, provide:
1. A concise name (3-6 words)
2. 2 targeted search queries — one in English, one in Chinese if topic is Chinese \
   (or two English queries if topic is English)

Topic: {topic}

Respond in JSON format:
{{
  "dimensions": [
    {{
      "name": "Market Size & Growth",
      "queries": ["AI market size 2024 statistics", "人工智能市场规模 2024"]
    }},
    ...
  ]
}}
"""

_EXTRACT_INSIGHTS_PROMPT = """\
You are a research analyst. Extract the most important, specific, data-rich insights \
from the following search results for a presentation about "{topic}".

Focus on:
- Specific numbers, percentages, dollar figures, growth rates
- Named companies, products, technologies
- Key trends with supporting evidence
- Concrete facts that would make strong slide content

Search results:
{search_text}

Respond in JSON:
{{
  "key_facts": ["fact 1 with specific data", "fact 2...", ...],
  "statistics": ["stat 1", "stat 2", ...],
  "trends": ["trend 1", "trend 2", ...],
  "companies_mentioned": ["company A", "company B", ...],
  "coverage_assessment": "What aspects are well-covered vs missing"
}}
"""

_GAP_ANALYSIS_PROMPT = """\
Based on the research collected so far about "{topic}", identify what important \
information is still missing or under-covered.

Research dimensions covered: {dimensions_covered}
Key facts found: {key_facts_summary}

What is missing? Generate 2-3 specific search queries to fill the most important gaps. \
Focus on: specific data/statistics, recent news, case studies, or expert analysis.

Respond in JSON:
{{
  "gaps": ["gap description 1", "gap description 2"],
  "gap_queries": ["specific search query 1", "specific search query 2", "query 3"]
}}
"""

_SYNTHESIS_PROMPT = """\
Synthesize the following research findings into a comprehensive, structured research \
report that can be used to create a professional presentation.

Topic: {topic}

Research findings:
{all_findings}

The report should:
1. Start with a high-level summary (3-5 sentences with key numbers)
2. Cover all major dimensions with specific data
3. Include a section on key statistics and metrics
4. Include recent trends and future outlook
5. Be organized so each section maps to 1-2 presentation slides
6. Use plain text (NO markdown bold **markers**)
7. Include specific numbers, company names, percentages wherever possible

Write in the same language as the topic ({language_hint}).
"""


# ── Pipeline Steps ───────────────────────────────────────────────


def _get_llm() -> LLMService:
    return LLMService(
        base_url=settings.chat_model_base_url,
        api_key=settings.chat_model_api_key,
        model_name=settings.chat_model_name,
    )


async def _analyze_dimensions(topic: str) -> list[dict]:
    """Step 1: Break topic into research dimensions with search queries."""
    llm = _get_llm()
    prompt = _DIMENSION_PROMPT.format(topic=topic)
    try:
        import json
        raw = await llm.json_chat(
            [
                {"role": "system", "content": "Output valid JSON only."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.4,
            max_tokens=16384,
        )
        data = json.loads(raw)
        return data.get("dimensions", [])
    except Exception:
        logger.warning("Dimension analysis failed, using default dimensions")
        return [
            {"name": "Overview", "queries": [f"{topic} overview statistics 2024"]},
            {"name": "Trends", "queries": [f"{topic} latest trends 2024"]},
            {"name": "Market", "queries": [f"{topic} market size growth"]},
            {"name": "Key Players", "queries": [f"{topic} leading companies examples"]},
        ]


async def _search_query(query: str) -> str:
    """Run a single web search and return formatted text."""
    try:
        result = await web_search(query, max_results=8)
        return format_search_results(result)
    except Exception as e:
        logger.warning("Search failed for query '%s': %s", query[:60], e)
        return ""


async def _extract_insights(topic: str, combined_text: str) -> dict:
    """Step 3: Extract structured insights from combined search results."""
    llm = _get_llm()
    # Truncate to avoid token overflow
    truncated = combined_text[:6000]
    prompt = _EXTRACT_INSIGHTS_PROMPT.format(topic=topic, search_text=truncated)
    try:
        import json
        raw = await llm.json_chat(
            [
                {"role": "system", "content": "Output valid JSON only."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=16384,
        )
        return json.loads(raw)
    except Exception:
        logger.warning("Insight extraction failed")
        return {
            "key_facts": [], "statistics": [], "trends": [],
            "companies_mentioned": [], "coverage_assessment": "Unable to extract",
        }


async def _identify_gaps(topic: str, dimensions: list[dict], insights: dict) -> list[str]:
    """Step 4: Identify missing research areas and generate gap-filling queries."""
    llm = _get_llm()
    dims_covered = ", ".join(d.get("name", "") for d in dimensions)
    key_facts_summary = "; ".join(insights.get("key_facts", [])[:5])
    prompt = _GAP_ANALYSIS_PROMPT.format(
        topic=topic,
        dimensions_covered=dims_covered,
        key_facts_summary=key_facts_summary or "none yet",
    )
    try:
        import json
        raw = await llm.json_chat(
            [
                {"role": "system", "content": "Output valid JSON only."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.4,
            max_tokens=16384,
        )
        data = json.loads(raw)
        return data.get("gap_queries", [])
    except Exception:
        logger.warning("Gap analysis failed")
        return []


async def _synthesize(topic: str, all_text: str) -> str:
    """Step 6: Synthesize all findings into a structured report."""
    llm = _get_llm()
    # Detect language hint from topic
    has_cjk = any("\u4e00" <= c <= "\u9fff" for c in topic)
    language_hint = "Chinese (中文)" if has_cjk else "English"
    truncated = all_text[:8000]
    prompt = _SYNTHESIS_PROMPT.format(
        topic=topic,
        all_findings=truncated,
        language_hint=language_hint,
    )
    try:
        result = await llm.chat(
            [
                {"role": "system", "content": "You are a senior research analyst. Write comprehensive, data-rich reports."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=16384,
        )
        return result
    except Exception as e:
        logger.exception("Research synthesis failed")
        return f"Research synthesis failed: {e}. Raw findings: {all_text[:2000]}"


# ── Public API ───────────────────────────────────────────────────

async def deep_research_pipeline(topic: str, progress_callback=None) -> str:
    """Run full 6-step deep research pipeline on a topic.

    Returns a comprehensive structured research report.

    Args:
        topic: Research topic
        progress_callback: Optional callback for progress updates
                         Signature: callback(stage: str, message: str)
    """
    # 优先使用 ContextVar 中的 callback（从 wrapper 设置），否则使用参数
    callback = _progress_callback_var.get(progress_callback)
    token = _progress_callback_var.set(callback)

    try:
        logger.info("Starting deep research pipeline for: %s", topic[:80])

        # Step 1: Analyze dimensions
        if callback:
            callback('research_step1', '正在分析研究维度...')
        logger.info("Step 1: Analyzing research dimensions...")
        dimensions = await _analyze_dimensions(topic)
        logger.info("Identified %d research dimensions", len(dimensions))
        if callback:
            callback('research_step2', f'已识别 {len(dimensions)} 个研究维度，正在搜索...')

        # Step 2: Parallel multi-query search across all dimensions
        logger.info("Step 2: Running parallel searches (%d dimensions)...", len(dimensions))
        all_queries = []
        for dim in dimensions:
            all_queries.extend(dim.get("queries", []))

        search_tasks = [_search_query(q) for q in all_queries]
        search_results = await asyncio.gather(*search_tasks, return_exceptions=True)

        combined_text_parts = []
        for q, result in zip(all_queries, search_results):
            if isinstance(result, str) and result:
                combined_text_parts.append(f"[Query: {q}]\n{result}\n")
        combined_text = "\n".join(combined_text_parts)
        logger.info("Collected %d chars of search data", len(combined_text))
        if callback:
            callback('research_step3', f'搜索完成，已收集 {len(combined_text)} 字符数据，正在提取关键信息...')

        # Step 3: Extract insights
        logger.info("Step 3: Extracting key insights...")
        insights = await _extract_insights(topic, combined_text)
        logger.info(
            "Extracted: %d facts, %d stats, %d trends",
            len(insights.get("key_facts", [])),
            len(insights.get("statistics", [])),
            len(insights.get("trends", [])),
        )
        if callback:
            facts_count = len(insights.get("key_facts", []))
            stats_count = len(insights.get("statistics", []))
            callback('research_step4', f'已提取 {facts_count} 个事实、{stats_count} 个统计数据，正在分析缺失信息...')

        # Step 4: Identify gaps
        logger.info("Step 4: Identifying research gaps...")
        gap_queries = await _identify_gaps(topic, dimensions, insights)
        logger.info("Found %d gap queries", len(gap_queries))

        # Step 5: Fill gaps with targeted searches
        if gap_queries:
            if callback:
                callback('research_step5', f'发现 {len(gap_queries)} 个信息缺口，正在补充搜索...')
            logger.info("Step 5: Running gap-filling searches...")
            gap_tasks = [_search_query(q) for q in gap_queries[:3]]
            gap_results = await asyncio.gather(*gap_tasks, return_exceptions=True)
            for q, result in zip(gap_queries, gap_results):
                if isinstance(result, str) and result:
                    combined_text += f"\n[Gap Query: {q}]\n{result}\n"
        elif callback:
            callback('research_step5', '信息已完整，无需补充搜索')

        # Step 6: Synthesize everything
        if callback:
            callback('research_step6', '正在综合研究结果生成报告...')
        logger.info("Step 6: Synthesizing research report...")
        report = await _synthesize(topic, combined_text)
        logger.info("Deep research pipeline complete. Report: %d chars", len(report))

        return report
    finally:
        # Clean up context var
        _progress_callback_var.reset(token)
