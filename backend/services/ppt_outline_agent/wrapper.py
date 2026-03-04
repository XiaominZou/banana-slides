"""Wrapper for single-shot outline generation."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
from typing import Dict, List

logger = logging.getLogger(__name__)


def generate_outline_single_shot_sync(
    user_request: str,
    topic: str = None,
    enable_research: bool = True,
    timeout: int = 1200,
    progress_callback=None,
    language: str = None,
) -> dict | None:
    """Execute the Plan Agent in single-shot mode (synchronous wrapper).
    
    Args:
        user_request: User's outline request
        topic: Optional topic override
        enable_research: Whether to enable web search and research
        timeout: Timeout in seconds
        progress_callback: Optional callback function for progress updates
            Signature: callback(stage: str, message: str)
        language: Output language (zh, en, ja, auto)
    
    Returns:
        Outline dict if successful, None otherwise
    """
    result_container = {'outline': None, 'error': None}
    
    def run_async():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            outline = loop.run_until_complete(
                _generate_outline_single_shot_async(
                    user_request=user_request,
                    topic=topic,
                    enable_research=enable_research,
                    progress_callback=progress_callback,
                    language=language,
                )
            )
            result_container['outline'] = outline
        except Exception as e:
            logger.error(f"Agent execution failed: {e}", exc_info=True)
            result_container['error'] = str(e)
        finally:
            loop.close()
    
    # 在后台线程运行
    thread = threading.Thread(target=run_async, daemon=True)
    thread.start()
    thread.join(timeout=timeout)
    
    if thread.is_alive():
        logger.error("Agent execution timed out")
        if progress_callback:
            progress_callback('timeout', '生成超时，正在降级到简单模式...')
        return None
    
    if result_container['error']:
        raise Exception(result_container['error'])
    
    return result_container['outline']


async def _generate_outline_single_shot_async(
    user_request: str,
    topic: str = None,
    enable_research: bool = True,
    progress_callback=None,
    language: str = None,
) -> dict | None:
    """Async implementation of single-shot outline generation.
    
    Args:
        user_request: User's outline request
        topic: Optional topic override
        enable_research: Whether to enable web search and research
        progress_callback: Optional callback for progress updates
        language: Output language (zh, en, ja, auto)
    """
    # 延迟导入，避免循环导入
    from langchain_core.messages import HumanMessage
    from .core.plan_agent import build_plan_graph
    from .core.state import PlanState

    # 发送进度：初始化
    if progress_callback:
        progress_callback('init', '正在初始化大纲生成引擎...')

    # 设置研究管线的进度回调（通过 ContextVar）
    from .tools.research_pipeline import _progress_callback_var
    research_token = _progress_callback_var.set(progress_callback)

    try:
        graph = build_plan_graph()

        # 发送进度：准备开始
        if progress_callback:
            progress_callback('preparing', '正在分析您的需求...')

        # 添加语言指令到 user_request
        enhanced_request = user_request
        if language and language != 'auto':
            from services.prompts import get_language_instruction
            lang_instruction = get_language_instruction(language)
            if lang_instruction:
                enhanced_request = f"{user_request}\n\n{lang_instruction}"

        # 构建初始状态
        initial_state: PlanState = {
            "messages": [HumanMessage(content=enhanced_request)],
            "outline": None,
            "outline_confirmed": False,
            "phase": "planning",
            "gathered_content": "",
            "search_images": [],
            "topic": topic or user_request,
        }

        # 第一步：生成大纲
        if progress_callback:
            progress_callback('generating', '正在生成大纲结构...')

        logger.info("Starting outline generation agent...")
        result = await graph.ainvoke(initial_state, config={"configurable": {"thread_id": "outline-gen-" + str(hash(user_request))}})

        if not result.get("outline"):
            logger.warning("Agent did not generate an outline")
            return None

        # 第二步：自动确认大纲
        if progress_callback:
            progress_callback('optimizing', '正在优化大纲结构...')

        logger.info("Auto-confirming outline...")
        confirm_state = {
            **result,
            "messages": [
                *result["messages"],
                HumanMessage(content="请确认这个大纲，直接使用它即可"),
            ],
        }

        final_result = await graph.ainvoke(confirm_state, config={"configurable": {"thread_id": "outline-confirm-" + str(hash(user_request))}})

        outline = final_result.get("outline") or result.get("outline")

        logger.info(f"Final result outline type: {type(outline)}")
        if isinstance(outline, dict):
            logger.info(f"Final result outline keys: {list(outline.keys())}")
            logger.info(f"Final result outline title: {outline.get('title', 'N/A')}")
            logger.info(f"Final result outline total_slides: {outline.get('total_slides', 'N/A')}")
            logger.info(f"Final result outline slides count: {len(outline.get('slides', []))}")
        else:
            logger.warning(f"Final result outline is not a dict: {outline}")

        from .core.plan_agent import _enrich_sparse_slides
        enriched_outline = _enrich_sparse_slides(outline)

        if progress_callback:
            slides_count = len(enriched_outline.get('slides', []))
            progress_callback('complete', f'大纲生成完成，共 {slides_count} 张幻灯片')

        logger.info(f"Outline generated: {len(enriched_outline.get('slides', []))} slides, enriched with elements")
        return enriched_outline

    except Exception as e:
        logger.error(f"Agent execution failed: {e}", exc_info=True)
        if progress_callback:
            progress_callback('error', f'生成失败: {str(e)}')
        return None
    finally:
        # 清理 ContextVar
        _progress_callback_var.reset(research_token)


def convert_outline_to_pages(outline: dict) -> List[Dict]:
    """Convert Outline dict to legacy page format, preserving full elements.
    
    Args:
        outline: Outline dict from agent (not Outline model to avoid validation issues)
    
    Returns:
        List of page dicts: [{
            title: str,
            points: List[str],  # 向后兼容
            elements: List[dict],  # 完整元素信息
            part: str | None,
            slide_type: str | None,
            layout_style: str | None,
            layout_variant: str | None
        }, ...]
    """
    pages = []
    
    for slide in outline.get("slides", []):
        # 提取要点（向后兼容）
        points = []
        
        for element in slide.get("elements", []):
            elem_type = element.get("type", "")
            
            if elem_type == "bullet_list":
                bullet_items = element.get("bullet_items", [])
                if isinstance(bullet_items, list):
                    points.extend(bullet_items)
            elif elem_type == "text":
                content = element.get("content", "")
                if content:
                    points.append(content)
            elif elem_type == "subtitle":
                content = element.get("content", "")
                if content:
                    points.append(content)
        
        # 使用 layout_style 或 slide_type 作为 part
        part = slide.get("layout_style") or slide.get("slide_type")
        if part == "content":
            part = None  # 不标记普通 content
        
        page_data = {
            'title': slide.get("title", "Untitled"),
            'points': points,  # 向后兼容
            'part': part,
        }
        
        # 保留完整元素信息
        if slide.get("elements"):
            page_data['elements'] = slide["elements"]
        
        # 保留其他元数据
        if slide.get("slide_type"):
            page_data['slide_type'] = slide["slide_type"]
        if slide.get("layout_style"):
            page_data['layout_style'] = slide["layout_style"]
        if slide.get("layout_variant"):
            page_data['layout_variant'] = slide["layout_variant"]
        
        pages.append(page_data)
    
    return pages
