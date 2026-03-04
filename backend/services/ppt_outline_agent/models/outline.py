from __future__ import annotations

import logging
from enum import Enum

from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)

# ── Alias maps for common LLM variations ────────────────────────

_ELEMENT_TYPE_ALIASES: dict[str, str] = {
    "bullet": "bullet_list",
    "bullets": "bullet_list",
    "bullet_points": "bullet_list",
    "bulletlist": "bullet_list",
    "list": "bullet_list",
    "heading": "title",
    "header": "title",
    "paragraph": "text",
    "body": "text",
    "body_text": "text",
    "img": "image",
    "picture": "image",
    "photo": "image",
    "graph": "chart",
    "diagram": "image",   # diagram routes to image with diagram_type metadata
    "flowchart": "image",
    "architecture": "image",
    "data_table": "table",
    "notes": "speaker_notes",
    "note": "speaker_notes",
    "sub_title": "subtitle",
    "kpi_card": "kpi",
    "metric": "kpi",
    "key_metric": "kpi",
    "indicator": "kpi",
}

_SLIDE_TYPE_ALIASES: dict[str, str] = {
    "title": "cover",
    "title_slide": "cover",
    "intro": "cover",
    "introduction": "cover",
    "opening": "cover",
    "end": "closing",
    "thank_you": "closing",
    "thanks": "closing",
    "summary": "closing",
    "conclusion": "closing",
    "section": "section_header",
    "section_title": "section_header",
    "divider": "section_header",
    "two_col": "two_column",
    "twocolumn": "two_column",
    "dual": "two_column",
    "compare": "comparison",
    "vs": "comparison",
    "versus": "comparison",
    "image": "image_focus",
    "photo": "image_focus",
    "picture": "image_focus",
    "chart": "chart_focus",
    "graph": "chart_focus",
    "data": "chart_focus",
    "table": "table_focus",
    "text": "content",
    "body": "content",
    "default": "content",
    "blank": "content",
    "quotation": "quote",
    "table_of_contents": "toc",
    "contents": "toc",
    "agenda": "toc",
}

_CHART_TYPE_ALIASES: dict[str, str] = {
    "column": "bar",
    "histogram": "bar",
    "bar_chart": "bar",
    "line_chart": "line",
    "pie_chart": "pie",
    "donut": "pie",
    "doughnut": "pie",
    "scatter_plot": "scatter",
    "area_chart": "area",
}


class ElementType(str, Enum):
    TITLE = "title"
    SUBTITLE = "subtitle"
    TEXT = "text"
    BULLET_LIST = "bullet_list"
    TABLE = "table"
    IMAGE = "image"
    CHART = "chart"
    KPI = "kpi"
    SPEAKER_NOTES = "speaker_notes"


class ChartType(str, Enum):
    BAR = "bar"
    LINE = "line"
    PIE = "pie"
    SCATTER = "scatter"
    AREA = "area"


class SlideType(str, Enum):
    COVER = "cover"
    TOC = "toc"
    SECTION_HEADER = "section_header"
    CONTENT = "content"
    TWO_COLUMN = "two_column"
    IMAGE_FOCUS = "image_focus"
    CHART_FOCUS = "chart_focus"
    TABLE_FOCUS = "table_focus"
    COMPARISON = "comparison"
    QUOTE = "quote"
    CLOSING = "closing"


class ElementLayout(BaseModel):
    """Explicit layout specification for an element on a slide.

    All measurements in inches. When coordinates are None the renderer
    falls back to the named *preset*.
    """

    left: float | None = None
    top: float | None = None
    width: float | None = None
    height: float | None = None
    preset: str = "auto"  # auto | left_half | right_half | top_third | center
    #                       bottom_third | full | left_quarter | right_three_quarter


class SlideElement(BaseModel):
    """A single content element on a slide."""

    type: ElementType
    content: str = ""
    bullet_items: list[str] | None = None
    table_data: list[list[str]] | None = None
    chart_type: ChartType | None = None
    chart_data: dict | None = None
    image_url: str | None = None
    image_prompt: str | None = None
    position: str = "auto"  # kept for backward compat

    # Layout & per-element style overrides
    layout: ElementLayout | None = None
    bold: bool | None = None
    font_size: int | None = None
    color: str | None = None
    use_dark_bg: bool = False

    # KPI-specific fields
    kpi_value: str | None = None         # e.g. "23%", "$5.2B", "1,200"
    kpi_label: str | None = None         # e.g. "同比增长", "Revenue"
    kpi_trend: str | None = None         # e.g. "↑23%", "↓5%", "持平"
    kpi_trend_color: str | None = None   # e.g. "#10B981" green, "#EF4444" red

    # Diagram-specific fields (for image elements that are diagrams)
    diagram_type: str | None = None      # "flowchart" | "architecture" | "mindmap" | "sequence" | "timeline"
    diagram_source: str | None = None    # "auto" | "gemini" | "web" — generation strategy

    @field_validator("type", mode="before")
    @classmethod
    def _coerce_element_type(cls, v: object) -> object:
        if isinstance(v, str):
            v = v.strip().lower()
            v = _ELEMENT_TYPE_ALIASES.get(v, v)
        return v

    @field_validator("chart_type", mode="before")
    @classmethod
    def _coerce_chart_type(cls, v: object) -> object:
        if isinstance(v, str):
            v = v.strip().lower()
            v = _CHART_TYPE_ALIASES.get(v, v)
        return v


class SlideSpec(BaseModel):
    """Specification for one slide."""

    slide_index: int
    slide_type: SlideType
    title: str
    elements: list[SlideElement] = Field(default_factory=list)
    speaker_notes: str = ""
    transition: str = "none"
    background_image_url: str | None = None
    layout_style: str | None = None    # "layout_1"..."layout_8" — visual structure annotation
    layout_variant: str = "auto"       # "hero"|"magazine"|"comparison"|"featured"|"timeline"|"auto"

    @field_validator("slide_type", mode="before")
    @classmethod
    def _coerce_slide_type(cls, v: object) -> object:
        if isinstance(v, str):
            v = v.strip().lower()
            v = _SLIDE_TYPE_ALIASES.get(v, v)
        return v


class Outline(BaseModel):
    """Complete PPT outline — the contract between Plan and Build agents."""

    title: str
    subtitle: str = ""
    author: str = ""
    total_slides: int = 0
    slides: list[SlideSpec] = Field(default_factory=list)
    theme_color: str = "#2563EB"
    font_family: str = "auto"
    metadata: dict = Field(default_factory=dict)
    style: dict = Field(default_factory=dict)


def parse_outline_safe(data: dict) -> Outline:
    """Parse an outline dict into an Outline, salvaging slides on validation errors.

    If strict parsing fails, tries to parse slides one-by-one and skips
    invalid ones rather than losing the entire outline.
    """
    # Try strict parsing first
    try:
        return Outline(**data)
    except Exception as exc:
        logger.warning("Strict Outline parsing failed: %s", exc)

    # Fallback: parse slides individually, skip broken ones
    raw_slides = data.get("slides", [])
    valid_slides: list[SlideSpec] = []

    for i, raw_slide in enumerate(raw_slides):
        if not isinstance(raw_slide, dict):
            logger.warning("Slide %d: not a dict, skipping", i)
            continue

        # Ensure slide_index exists
        if "slide_index" not in raw_slide:
            raw_slide["slide_index"] = i

        # Try to parse individual elements, keeping valid ones
        raw_elements = raw_slide.get("elements", [])
        valid_elements: list[dict] = []
        for j, raw_elem in enumerate(raw_elements):
            if not isinstance(raw_elem, dict):
                continue
            try:
                SlideElement(**raw_elem)
                valid_elements.append(raw_elem)
            except Exception as elem_exc:
                elem_type = raw_elem.get("type", "?")
                logger.warning(
                    "Slide %d element %d (type=%s): validation failed: %s",
                    i, j, elem_type, elem_exc,
                )
                # Try to salvage by forcing type to "text"
                try:
                    fallback_elem = {**raw_elem, "type": "text"}
                    SlideElement(**fallback_elem)
                    valid_elements.append(fallback_elem)
                    logger.info("Slide %d element %d: salvaged as text", i, j)
                except Exception:
                    pass

        raw_slide["elements"] = valid_elements

        try:
            slide = SlideSpec(**raw_slide)
            valid_slides.append(slide)
        except Exception as slide_exc:
            slide_title = raw_slide.get("title", "?")
            logger.warning(
                "Slide %d (%s): validation failed: %s", i, slide_title, slide_exc,
            )
            # Try forcing slide_type to "content"
            try:
                fallback_slide = {**raw_slide, "slide_type": "content"}
                slide = SlideSpec(**fallback_slide)
                valid_slides.append(slide)
                logger.info("Slide %d: salvaged as content type", i)
            except Exception:
                pass

    logger.info(
        "Outline parsed: %d/%d slides salvaged", len(valid_slides), len(raw_slides),
    )

    return Outline(
        title=data.get("title", "Untitled"),
        subtitle=data.get("subtitle", ""),
        author=data.get("author", ""),
        total_slides=len(valid_slides),
        slides=valid_slides,
        theme_color=data.get("theme_color", "#2563EB"),
        font_family=data.get("font_family", "auto"),
        metadata=data.get("metadata", {}),
        style=data.get("style", {}),
    )
