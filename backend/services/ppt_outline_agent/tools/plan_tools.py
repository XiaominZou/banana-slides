"""Tools available to the Plan Agent for outline creation and modification."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional

from langchain_core.tools import tool

from .deepseek_research import deepseek_research
from .research_pipeline import deep_research_pipeline, _progress_callback_var
from .web_search import format_search_results, web_search

logger = logging.getLogger(__name__)

# Slide types that must have content elements
_CONTENT_SLIDE_TYPES = {
    "content", "two_column", "image_focus", "chart_focus",
    "table_focus", "comparison",
}
# Layout style → (min_elements, target_elements, min_visual_count)
# High-density layouts (layout_3/4/6/7) can exceed 10 elements — do NOT cap at 7.
_LAYOUT_DENSITY: dict[str, tuple[int, int, int]] = {
    "layout_1": (4, 6, 1),    # Left-image right-text: 1 arch diagram + subtitle + 3 text blocks
    "layout_2": (6, 8, 3),    # Problem-solution dual column: 2-3 charts/diagrams per side
    "layout_3": (9, 11, 6),   # Three-phase vertical: 4 KPI + 3 flowcharts + 3 tables
    "layout_4": (7, 9, 4),    # Four-quadrant grid: 4 images + 4 bullet_lists
    "layout_5": (6, 8, 2),    # Zone-block mixed: 2 arch diagrams + 3 text + 1 table
    "layout_6": (8, 10, 3),   # Three-column analysis: 3 images + 3 bullets + summary
    "layout_7": (8, 11, 5),   # Case-process-conclusion: 3 cases + 2 flows + 6 points
    "layout_8": (2, 3, 1),    # Simple top-bottom transition: subtitle + 2-3 text + 1 image
}
_DEFAULT_DENSITY = (4, 6, 1)  # Fallback when no layout_style is set

# Keywords that suggest a diagram placeholder is better than a chart placeholder
_PLAN_DIAGRAM_KEYWORDS = {
    "架构", "流程", "系统", "组件", "框架", "结构", "原理", "机制",
    "architecture", "flow", "system", "component", "framework",
    "process", "workflow", "pipeline", "structure",
}


def _ensure_slide_density(slide: dict) -> dict:
    """Inject placeholder elements for content slides below their layout's minimum.

    Uses layout_style to determine the target element count. High-density layouts
    (layout_3/4/6/7) require 9-13 elements; layout_8 only needs 2-3.
    Placeholders are sparse so the Build Agent's enrichment fills them with
    proper data-rich content. Only ADDS elements — never removes or replaces.
    """
    if slide.get("slide_type") not in _CONTENT_SLIDE_TYPES:
        return slide

    layout_style = slide.get("layout_style", "")
    min_elems, _target_elems, _min_visual = _LAYOUT_DENSITY.get(
        layout_style, _DEFAULT_DENSITY
    )

    elements = list(slide.get("elements", []))
    title = slide.get("title", "")

    if len(elements) >= min_elems:
        return slide  # already dense enough

    types_present = {e.get("type") for e in elements}
    title_lower = title.lower()
    is_diagram_slide = any(k in title_lower for k in _PLAN_DIAGRAM_KEYWORDS)

    # 1. bullet_list — Build Agent will enrich sparse bullets automatically
    if "bullet_list" not in types_present and len(elements) < min_elems:
        elements.append({"type": "bullet_list", "bullet_items": ["key point 1", "key point 2"]})
        types_present.add("bullet_list")

    # 2. Cycle through visual placeholders until min_elems is reached
    # Ordered by information value: primary visual → table → secondary visuals
    visual_cycle = [
        ({"type": "image", "diagram_type": "architecture", "content": title}
         if is_diagram_slide else
         {"type": "chart", "chart_type": "bar", "content": title}),
        {"type": "table", "content": title},
        {"type": "image", "diagram_type": "flowchart", "content": title},
        {"type": "chart", "chart_type": "line", "content": title},
        {"type": "image", "diagram_type": "timeline", "content": title},
        {"type": "chart", "chart_type": "pie", "content": title},
    ]
    for placeholder in visual_cycle:
        if len(elements) >= min_elems:
            break
        elements.append(placeholder)

    return {**slide, "elements": elements}


@tool
async def search_web(query: str) -> str:
    """Search the web for information about a topic. Returns search results
    with titles, snippets, and URLs.

    Args:
        query: The search query string.
    """
    # 报告研究进度
    callback = _progress_callback_var.get()
    if callback:
        callback('research_mode', '正在进行快速检索...')
        logger.info("Agent selected research mode: Fast/Search")

    search_data = await web_search(query)
    text = format_search_results(search_data)
    return text if text else "No results found."


@tool
async def research_topic(topic: str) -> str:
    """Generate an in-depth research report on a topic using chat model.
    Use this when user wants thorough, structured research for their presentation.

    Args:
        topic: The topic to research in detail.
    """
    # 报告研究进度
    callback = _progress_callback_var.get()
    if callback:
        callback('research_mode', '正在进行中度调研...')
        logger.info("Agent selected research mode: Medium/DeepSeek")

    result = await deepseek_research(topic)
    return result or "Research returned no content."


@tool
async def deep_research(topic: str) -> str:
    """Run a comprehensive multi-step research pipeline on a topic.

    This performs 6 steps automatically:
    1. Analyze topic dimensions (market, tech, competition, trends, etc.)
    2. Run parallel web searches across all dimensions
    3. Extract key facts, statistics, and trends
    4. Identify research gaps
    5. Fill gaps with targeted follow-up searches
    6. Synthesize everything into a structured report

    Use this instead of research_topic when you need deeper, more data-rich research
    for a comprehensive presentation. Takes longer but produces much richer content.

    Args:
        topic: The topic to research in depth.
    """
    # 报告研究进度
    callback = _progress_callback_var.get()
    if callback:
        callback('research_mode', '正在进行深度研究（6步综合分析）...')
        logger.info("Agent selected research mode: Deep/6-Step")

    result = await deep_research_pipeline(topic)
    return result or "Deep research returned no content."


@tool
async def create_outline(
    title: str,
    slides: list[dict],
    subtitle: str = "",
    theme_color: str = "#960000",
    style: Optional[dict] = None,
) -> str:
    """Create a new presentation outline from scratch. Call this after you have
    enough information about the topic and content structure.

    Args:
        title: The presentation title.
        slides: List of slide specifications. Each slide is a dict with keys:
            - slide_index (int): 0-based index
            - slide_type (str): one of cover, toc, section_header, content,
              two_column, image_focus, chart_focus, table_focus, comparison, quote, closing
            - layout_style (str, optional): visual structure — "layout_1" through "layout_8"
              (see LAYOUT STYLE SELECTION in the system prompt for details)
            - layout_variant (str, optional): renderer hint — "hero"|"magazine"|"comparison"|
              "featured"|"timeline"|"auto" (derived from layout_style)
            - title (str): slide title
            - elements (list): list of element dicts with 'type' and content fields.
              Elements can include optional layout ({"preset": "left_half"}),
              bold (true/false), color ("#hex"), and font_size (int) overrides.
              For image elements: use image_prompt for AI generation.
            - speaker_notes (str, optional): notes for the speaker
        subtitle: Optional presentation subtitle.
        theme_color: Hex color for the theme (default deep red).
        style: Optional style configuration dict with keys: fonts, colors, spacing.
    """
    outline = {
        "title": title,
        "subtitle": subtitle,
        "author": "",
        "total_slides": len(slides),
        "theme_color": theme_color,
        "slides": [_ensure_slide_density(s) for s in slides],
    }
    if style:
        outline["style"] = style
    return json.dumps(outline, ensure_ascii=False)


@tool
async def modify_outline(
    action: str,
    slide_index: int = -1,
    slide_data: Optional[dict] = None,
    target_index: int = -1,
    updates: Optional[dict] = None,
) -> str:
    """Modify the current presentation outline. Supports adding, removing,
    moving, and editing slides.

    Args:
        action: The modification action. One of:
            - "add": Add a new slide at slide_index (or append if -1)
            - "remove": Remove the slide at slide_index
            - "move": Move slide from slide_index to target_index
            - "edit": Update the slide at slide_index with the provided updates
            - "edit_title": Change the presentation title (use updates={"title": "new title"})
        slide_index: The 0-based index of the slide to act on. Use -1 with "add" to append.
        slide_data: For "add" action: the complete slide spec dict.
        target_index: For "move" action: the destination index.
        updates: For "edit" / "edit_title" action: dict of fields to update.
    """
    instruction = {
        "action": action,
        "slide_index": slide_index,
        "slide_data": slide_data,
        "target_index": target_index,
        "updates": updates,
    }
    return json.dumps(instruction, ensure_ascii=False)


@tool
async def confirm_outline() -> str:
    """Confirm the current outline and mark it as ready for building.
    Call this ONLY when the user explicitly confirms they are satisfied with the outline.
    """
    return json.dumps({"confirmed": True})


@tool
async def review_narrative(outline_json: str) -> str:
    """Review the presentation outline for narrative coherence and story flow.

    Optional — call this if the user explicitly asks for a review, or when
    you want to double-check a large/complex outline before confirming.
    Returns a brief assessment with improvement suggestions.

    Args:
        outline_json: The JSON string returned by create_outline.
    """
    from ..config import settings
    from ..services.llm_service import LLMService

    review_prompt = f"""\
Review this presentation outline for narrative coherence and story flow.
Be concise — 150 words max.

Outline (excerpt):
{outline_json[:3000]}

Respond with:
- Score: X/10
- Key strengths (1-2 points)
- Main issues (1-2 points)
- Top suggestion

Respond in the same language as the outline.
"""

    llm = LLMService(
        base_url=settings.chat_model_base_url,
        api_key=settings.chat_model_api_key,
        model_name=settings.chat_model_name,
    )
    try:
        result = await asyncio.wait_for(
            llm.chat(
                [{"role": "user", "content": review_prompt}],
                temperature=0.3,
                max_tokens=16384,
            ),
            timeout=30,
        )
        return result or "Review returned no content."
    except asyncio.TimeoutError:
        return "Review timed out. The outline looks reasonable — proceed with confirm_outline if satisfied."
    except Exception as e:
        return f"Review failed: {e}"


PLAN_TOOLS = [search_web, research_topic, deep_research, create_outline, modify_outline, review_narrative, confirm_outline]
