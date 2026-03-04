"""Shared state definitions for Plan and Build agents."""
from __future__ import annotations

from langgraph.graph import MessagesState


class PlanState(MessagesState):
    """State for the conversational Plan Agent (ReAct pattern)."""

    # Current outline draft (None until first creation)
    outline: dict | None

    # Accumulated research / search content
    gathered_content: str

    # Images found from web search (deprecated - no longer populated)
    search_images: list[dict]

    # Whether the user has confirmed the outline
    outline_confirmed: bool

    # User's topic (extracted naturally by the LLM)
    topic: str

    # Phase for frontend UI coordination
    phase: str  # planning | confirmed | building | build_review | complete


class BuildState(MessagesState):
    """State for the Build Agent — batch PPT generation with feedback loop."""

    # Confirmed outline
    outline: dict

    # Template path
    template_path: str

    # Progress tracking
    current_slide_index: int
    total_slides: int

    # Generated contents per slide
    slide_contents: list[dict]

    # Status
    status: str  # initializing | processing_slide | awaiting_feedback | rendering | complete | error
    status_message: str

    # Output
    output_path: str

    # Slide feedback tracking
    pending_feedback_slide: int  # -1 = none, -2 = needs LLM interpretation, >=0 = specific slide

    # Gemini rendering path
    use_gemini_rendering: bool  # True = render slides as full-page Gemini images
    image_paths: list[str]      # PNG paths produced by GeminiSlideRenderer
