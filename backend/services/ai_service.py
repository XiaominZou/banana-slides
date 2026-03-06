"""
AI Service - handles all AI model interactions
Based on demo.py and gemini_genai.py
TODO: use structured output API
"""

import os
import json
import re
import logging
import requests
import asyncio
from typing import List, Dict, Optional, Union
from textwrap import dedent
from PIL import Image
from tenacity import retry, stop_after_attempt, retry_if_exception_type
from .prompts import (
    get_outline_generation_prompt,
    get_outline_parsing_prompt,
    get_page_description_prompt,
    get_image_generation_prompt,
    get_image_edit_prompt,
    get_description_to_outline_prompt,
    get_description_split_prompt,
    get_outline_refinement_prompt,
    get_descriptions_refinement_prompt,
    get_ppt_page_content_extraction_prompt,
    get_layout_caption_prompt,
    get_style_extraction_prompt,
    get_outline_generation_prompt_markdown,
    get_outline_parsing_prompt_markdown,
    get_description_to_outline_prompt_markdown,
    get_page_outline_refinement_prompt,
    get_page_description_refinement_prompt,
    get_element_refinement_prompt,
)
from .ai_providers import (
    get_text_provider,
    get_image_provider,
    get_caption_provider,
    TextProvider,
    ImageProvider,
)
from config import get_config

logger = logging.getLogger(__name__)


class ProjectContext:
    """项目上下文数据类，统一管理 AI 需要的所有项目信息"""

    def __init__(
        self,
        project_or_dict,
        reference_files_content: Optional[List[Dict[str, str]]] = None,
    ):
        """
        Args:
            project_or_dict: 项目对象（Project model）或项目字典（project.to_dict()）
            reference_files_content: 参考文件内容列表
        """
        # 支持直接传入 Project 对象，避免 to_dict() 调用，提升性能
        if hasattr(project_or_dict, "idea_prompt"):
            # 是 Project 对象
            self.idea_prompt = project_or_dict.idea_prompt
            self.outline_text = project_or_dict.outline_text
            self.description_text = project_or_dict.description_text
            self.creation_type = project_or_dict.creation_type or "idea"
            self.outline_requirements = project_or_dict.outline_requirements
            self.description_requirements = project_or_dict.description_requirements
        else:
            # 是字典
            self.idea_prompt = project_or_dict.get("idea_prompt")
            self.outline_text = project_or_dict.get("outline_text")
            self.description_text = project_or_dict.get("description_text")
            self.creation_type = project_or_dict.get("creation_type", "idea")
            self.outline_requirements = project_or_dict.get("outline_requirements")
            self.description_requirements = project_or_dict.get(
                "description_requirements"
            )

        self.reference_files_content = reference_files_content or []

    def to_dict(self) -> Dict:
        """转换为字典，方便传递"""
        return {
            "idea_prompt": self.idea_prompt,
            "outline_text": self.outline_text,
            "description_text": self.description_text,
            "creation_type": self.creation_type,
            "outline_requirements": self.outline_requirements,
            "description_requirements": self.description_requirements,
            "reference_files_content": self.reference_files_content,
        }


class AIService:
    """Service for AI model interactions using pluggable providers"""

    def __init__(
        self,
        text_provider: TextProvider = None,
        image_provider: ImageProvider = None,
        caption_provider: TextProvider = None,
    ):
        """
        Initialize AI service with providers

        Args:
            text_provider: Optional pre-configured TextProvider. If None, created from factory.
            image_provider: Optional pre-configured ImageProvider. If None, created from factory.
        """
        config = get_config()

        # 优先使用 Flask app.config（可由 Settings 覆盖），否则回退到 Config 默认值
        try:
            from flask import current_app, has_app_context
        except ImportError:
            current_app = None  # type: ignore
            has_app_context = lambda: False  # type: ignore

        if has_app_context() and current_app and hasattr(current_app, "config"):
            self.text_model = current_app.config.get("TEXT_MODEL", config.TEXT_MODEL)
            self.image_model = current_app.config.get("IMAGE_MODEL", config.IMAGE_MODEL)
            # 分离的文本和图像推理配置
            self.enable_text_reasoning = current_app.config.get(
                "ENABLE_TEXT_REASONING", False
            )
            self.text_thinking_budget = current_app.config.get(
                "TEXT_THINKING_BUDGET", 1024
            )
            self.enable_image_reasoning = current_app.config.get(
                "ENABLE_IMAGE_REASONING", False
            )
            self.image_thinking_budget = current_app.config.get(
                "IMAGE_THINKING_BUDGET", 1024
            )
        else:
            self.text_model = config.TEXT_MODEL
            self.image_model = config.IMAGE_MODEL
            self.enable_text_reasoning = False
            self.text_thinking_budget = 1024
            self.enable_image_reasoning = False
            self.image_thinking_budget = 1024

        # Caption model for multimodal (image→text) tasks
        if has_app_context() and current_app and hasattr(current_app, "config"):
            self.caption_model = current_app.config.get(
                "IMAGE_CAPTION_MODEL", config.IMAGE_CAPTION_MODEL
            )
        else:
            self.caption_model = config.IMAGE_CAPTION_MODEL

        # Use provided providers or create from factory based on AI_PROVIDER_FORMAT (from Flask config or env var)
        self.text_provider = text_provider or get_text_provider(model=self.text_model)
        self.image_provider = image_provider or get_image_provider(
            model=self.image_model
        )
        self.caption_provider = caption_provider or get_caption_provider(
            model=self.caption_model
        )

    def _get_text_thinking_budget(self) -> int:
        """
        获取文本生成的思考负载

        Returns:
            如果启用文本推理则返回配置的 budget，否则返回 0
        """
        return self.text_thinking_budget if self.enable_text_reasoning else 0

    def _get_image_thinking_budget(self) -> int:
        """
        获取图像生成的思考负载

        Returns:
            如果启用图像推理则返回配置的 budget，否则返回 0
        """
        return self.image_thinking_budget if self.enable_image_reasoning else 0

    @staticmethod
    def extract_image_urls_from_markdown(text: str) -> List[str]:
        """
        从 markdown 文本中提取图片 URL

        Args:
            text: Markdown 文本，可能包含 ![](url) 格式的图片

        Returns:
            图片 URL 列表（包括 http/https URL 和 /files/ 开头的本地路径）
        """
        if not text:
            return []

        # 匹配 markdown 图片语法: ![](url) 或 ![alt](url)
        pattern = r"!\[.*?\]\((.*?)\)"
        matches = re.findall(pattern, text)

        # 过滤掉空字符串，支持 http/https URL 和 /files/ 开头的本地路径（包括 mineru、materials 等）
        urls = []
        for url in matches:
            url = url.strip()
            if url and (
                url.startswith("http://")
                or url.startswith("https://")
                or url.startswith("/files/")
            ):
                urls.append(url)

        return urls

    @staticmethod
    def remove_markdown_images(text: str) -> str:
        """
        从文本中移除 Markdown 图片链接，只保留 alt text（描述文字）

        Args:
            text: 包含 Markdown 图片语法的文本

        Returns:
            移除图片链接后的文本，保留描述文字
        """
        if not text:
            return text

        # 将 ![描述文字](url) 替换为 描述文字
        # 如果没有描述文字（空的 alt text），则完全删除该图片链接
        def replace_image(match):
            alt_text = match.group(1).strip()
            # 如果有描述文字，保留它；否则删除整个链接
            return alt_text if alt_text else ""

        pattern = r"!\[(.*?)\]\([^\)]+\)"
        cleaned_text = re.sub(pattern, replace_image, text)

        # 清理可能产生的多余空行
        cleaned_text = re.sub(r"\n\s*\n\s*\n", "\n\n", cleaned_text)

        return cleaned_text

    @retry(
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type((json.JSONDecodeError, ValueError)),
        reraise=True,
    )
    def generate_json(
        self, prompt: str, thinking_budget: int = 1000
    ) -> Union[Dict, List]:
        """
        生成并解析JSON，如果解析失败则重新生成

        Args:
            prompt: 生成提示词
            thinking_budget: 思考预算（会根据 enable_text_reasoning 配置自动调整）

        Returns:
            解析后的JSON对象（字典或列表）

        Raises:
            json.JSONDecodeError: JSON解析失败（重试3次后仍失败）
        """
        # 调用AI生成文本（根据 enable_text_reasoning 配置调整 thinking_budget）
        actual_budget = self._get_text_thinking_budget()
        response_text = self.text_provider.generate_text(
            prompt, thinking_budget=actual_budget
        )

        # 清理响应文本：移除markdown代码块标记和多余空白
        cleaned_text = response_text.strip().strip("```json").strip("```").strip()

        try:
            return json.loads(cleaned_text)
        except json.JSONDecodeError as e:
            logger.warning(
                f"JSON解析失败，将重新生成。原始文本: {cleaned_text[:200]}... 错误: {str(e)}"
            )
            raise

    @retry(
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type((json.JSONDecodeError, ValueError)),
        reraise=True,
    )
    def generate_json_with_image(
        self, prompt: str, image_path: str, thinking_budget: int = 1000
    ) -> Union[Dict, List]:
        """
        带图片输入的JSON生成，如果解析失败则重新生成（最多重试3次）

        Args:
            prompt: 生成提示词
            image_path: 图片文件路径
            thinking_budget: 思考预算（会根据 enable_text_reasoning 配置自动调整）

        Returns:
            解析后的JSON对象（字典或列表）

        Raises:
            json.JSONDecodeError: JSON解析失败（重试3次后仍失败）
            ValueError: caption_provider 不支持图片输入
        """
        # 使用 caption_provider（支持图片输入的多模态模型）
        actual_budget = self._get_text_thinking_budget()
        provider = self.caption_provider
        if hasattr(provider, "generate_with_image"):
            response_text = provider.generate_with_image(
                prompt=prompt, image_path=image_path, thinking_budget=actual_budget
            )
        elif hasattr(provider, "generate_text_with_images"):
            response_text = provider.generate_text_with_images(
                prompt=prompt, images=[image_path], thinking_budget=actual_budget
            )
        else:
            raise ValueError("caption_provider 不支持图片输入")

        # 清理响应文本：移除markdown代码块标记和多余空白
        cleaned_text = (
            response_text.strip()
            .removeprefix("```json")
            .removeprefix("```")
            .removesuffix("```")
            .strip()
        )

        try:
            return json.loads(cleaned_text)
        except json.JSONDecodeError as e:
            logger.warning(
                f"JSON解析失败（带图片），将重新生成。原始文本: {cleaned_text[:200]}... 错误: {str(e)}"
            )
            raise

    @staticmethod
    def _convert_mineru_path_to_local(mineru_path: str) -> Optional[str]:
        """
        将 /files/mineru/{extract_id}/{rel_path} 格式的路径转换为本地文件系统路径（支持前缀匹配）

        Args:
            mineru_path: MinerU URL 路径，格式为 /files/mineru/{extract_id}/{rel_path}

        Returns:
            本地文件系统路径，如果转换失败则返回 None
        """
        from utils.path_utils import find_mineru_file_with_prefix

        matched_path = find_mineru_file_with_prefix(mineru_path)
        return str(matched_path) if matched_path else None

    @staticmethod
    def download_image_from_url(url: str) -> Optional[Image.Image]:
        """
        从 URL 下载图片并返回 PIL Image 对象

        Args:
            url: 图片 URL

        Returns:
            PIL Image 对象，如果下载失败则返回 None
        """
        try:
            logger.debug(f"Downloading image from URL: {url}")
            response = requests.get(url, timeout=30, stream=True)
            response.raise_for_status()

            # 从响应内容创建 PIL Image
            image = Image.open(response.raw)
            # 确保图片被加载
            image.load()
            logger.debug(f"Successfully downloaded image: {image.size}, {image.mode}")
            return image
        except Exception as e:
            logger.error(f"Failed to download image from {url}: {str(e)}")
            return None

    def generate_outline(
        self, project_context: ProjectContext, language: str = None
    ) -> List[Dict]:
        """
        Generate PPT outline from idea prompt
        Based on demo.py gen_outline()

        Args:
            project_context: 项目上下文对象，包含所有原始信息

        Returns:
            List of outline items (may contain parts with pages or direct pages)
        """
        outline_prompt = get_outline_generation_prompt(project_context, language)
        outline = self.generate_json(outline_prompt, thinking_budget=1000)
        return outline

    @staticmethod
    def parse_markdown_outline(markdown: str) -> List[Dict]:
        """
        Parse markdown outline into structured page data.

        Format:
          # Part Name        → sets current part
          ## Page Title       → starts a new page
          - Point text        → adds a bullet point to current page

        Returns list of dicts: [{"title": ..., "points": [...], "part": ...}, ...]
        """
        pages = []
        current_part = None
        current_page = None

        for line in markdown.split("\n"):
            stripped = line.strip()
            if not stripped:
                continue

            if stripped.startswith("# ") and not stripped.startswith("## "):
                # Part header
                current_part = stripped[2:].strip()
            elif stripped.startswith("## "):
                # New page — flush previous
                if current_page:
                    pages.append(current_page)
                current_page = {
                    "title": stripped[3:].strip(),
                    "points": [],
                }
                if current_part:
                    current_page["part"] = current_part
            elif stripped.startswith("- ") and current_page is not None:
                current_page["points"].append(stripped[2:].strip())

        # Flush last page
        if current_page:
            pages.append(current_page)

        return pages

    def generate_outline_stream(
        self, project_context: ProjectContext, language: str = None
    ):
        """
        Stream outline generation, yielding each completed page as it's detected.

        Yields dicts: {"title": ..., "points": [...], "part": ...}
        """
        creation_type = project_context.creation_type or "idea"

        if creation_type == "outline":
            prompt = get_outline_parsing_prompt_markdown(project_context, language)
        elif creation_type == "descriptions":
            prompt = get_description_to_outline_prompt_markdown(
                project_context, language
            )
        else:
            prompt = get_outline_generation_prompt_markdown(project_context, language)

        actual_budget = self._get_text_thinking_budget()
        buffer = ""
        current_part = None
        current_page = None
        stream_complete = False

        for chunk in self.text_provider.generate_text_stream(
            prompt, thinking_budget=actual_budget
        ):
            buffer += chunk

            # Process complete lines from buffer
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                stripped = line.strip()

                if not stripped:
                    continue

                if stripped == "<!-- END -->":
                    stream_complete = True
                    continue

                if stripped.startswith("# ") and not stripped.startswith("## "):
                    current_part = stripped[2:].strip()
                elif stripped.startswith("## "):
                    # New page detected — yield previous page
                    if current_page:
                        yield current_page
                    current_page = {
                        "title": stripped[3:].strip(),
                        "points": [],
                    }
                    if current_part:
                        current_page["part"] = current_part
                elif stripped.startswith("- ") and current_page is not None:
                    current_page["points"].append(stripped[2:].strip())

        # Process remaining buffer (same logic as main loop)
        if buffer.strip():
            buffer += "\n"
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                stripped = line.strip()
                if not stripped:
                    continue
                if stripped == "<!-- END -->":
                    stream_complete = True
                    continue
                if stripped.startswith("# ") and not stripped.startswith("## "):
                    current_part = stripped[2:].strip()
                elif stripped.startswith("## "):
                    if current_page:
                        yield current_page
                    current_page = {
                        "title": stripped[3:].strip(),
                        "points": [],
                    }
                    if current_part:
                        current_page["part"] = current_part
                elif stripped.startswith("- ") and current_page is not None:
                    current_page["points"].append(stripped[2:].strip())

        # Yield last page
        if current_page:
            yield current_page

        # Yield completion sentinel
        yield {"__stream_complete__": stream_complete}

    def generate_outline_stream_with_agent(
        self,
        project_context: ProjectContext,
        language: str = None,
    ):
        """
        Stream outline generation using the advanced Plan Agent.

        Falls back to simple generation if agent fails and OUTLINE_AGENT_FALLBACK is True.

        Yields dicts:
        - Progress: {"__progress__": {"stage": "...", "message": "..."}}
        - Page: {"title": ..., "points": [...], "part": ...}
        - Complete: {"__stream_complete__": True}
        """
        from flask import current_app
        from services.ppt_outline_agent.wrapper import (
            generate_outline_single_shot_sync,
            convert_outline_to_pages,
        )

        # 检查是否启用 agent
        use_agent = current_app.config.get("USE_OUTLINE_AGENT", True)

        if not use_agent:
            logger.info("Outline agent disabled, using simple generation")
            yield from self.generate_outline_stream(project_context, language)
            return

        # 尝试使用 agent
        try:
            logger.info("Using advanced outline agent for generation")

            # 构建用户请求
            user_request = project_context.idea_prompt or ""
            if project_context.outline_requirements:
                user_request += f"\n\n要求：{project_context.outline_requirements}"

            # 获取超时配置
            timeout = current_app.config.get("OUTLINE_AGENT_TIMEOUT", 120)

            # 使用队列实现实时进度发送
            import queue

            progress_queue = queue.Queue()

            def progress_callback(stage: str, message: str):
                """接收进度回调并立即放入队列"""
                progress_queue.put(
                    {"__progress__": {"stage": stage, "message": message}}
                )
                logger.info(f"Agent progress [{stage}]: {message}")

            # 在后台线程中启动 agent，同时持续 yield 进度事件
            import threading

            result_container = {"outline": None, "error": None}

            def run_agent():
                try:
                    outline_dict = generate_outline_single_shot_sync(
                        user_request=user_request,
                        topic=project_context.idea_prompt,
                        enable_research=True,
                        timeout=timeout,
                        progress_callback=progress_callback,
                        language=language,
                    )
                    result_container["outline"] = outline_dict
                    progress_queue.put({"__agent_done__": True})
                except Exception as e:
                    logger.error(f"Agent execution failed: {e}", exc_info=True)
                    result_container["error"] = e
                    progress_queue.put({"__agent_error__": True, "error": str(e)})

            # 启动 agent 线程
            agent_thread = threading.Thread(target=run_agent, daemon=True)
            agent_thread.start()

            # 持续 yield 进度事件，直到 agent 完成
            while True:
                try:
                    item = progress_queue.get(timeout=0.5)
                    yield item
                    # 检查是否 agent 完成或出错
                    if "__agent_done__" in item or "__agent_error__" in item:
                        break
                except queue.Empty:
                    # 检查 agent 线程是否仍在运行
                    if not agent_thread.is_alive():
                        break

            # 等待 agent 线程结束
            agent_thread.join()

            # 检查 agent 是否出错
            if result_container["error"]:
                raise Exception(result_container["error"])

            outline_dict = result_container["outline"]

            if not outline_dict:
                raise Exception("Agent failed to generate outline")

            logger.info(f"Agent returned outline_dict type: {type(outline_dict)}")
            logger.info(
                f"Agent returned outline_dict keys: {list(outline_dict.keys()) if isinstance(outline_dict, dict) else 'N/A'}"
            )

            if isinstance(outline_dict, dict):
                logger.info(f"Agent returned title: {outline_dict.get('title', 'N/A')}")
                logger.info(
                    f"Agent returned total_slides: {outline_dict.get('total_slides', 'N/A')}"
                )
                logger.info(
                    f"Agent returned slides count: {len(outline_dict.get('slides', []))}"
                )

            # 转换格式
            pages = convert_outline_to_pages(outline_dict)

            logger.info(f"Agent generated {len(pages)} pages")

            # 返回页面
            for page in pages:
                yield page

            # 发送完成标记
            yield {"__stream_complete__": True}

        except Exception as e:
            logger.error(f"Agent generation failed: {e}", exc_info=True)

            # 检查是否降级
            fallback = current_app.config.get("OUTLINE_AGENT_FALLBACK", True)

            if fallback:
                logger.warning("Falling back to simple outline generation")
                yield {"__agent_fallback__": True, "reason": str(e)}
                yield from self.generate_outline_stream(project_context, language)
            else:
                raise Exception(f"Agent generation failed and fallback disabled: {e}")

    def parse_outline_text(
        self, project_context: ProjectContext, language: str = None
    ) -> List[Dict]:
        """
        Parse user-provided outline text into structured outline format
        This method analyzes the text and splits it into pages without modifying the original text

        Args:
            project_context: 项目上下文对象，包含所有原始信息

        Returns:
            List of outline items (may contain parts with pages or direct pages)
        """
        parse_prompt = get_outline_parsing_prompt(project_context, language)
        outline = self.generate_json(parse_prompt, thinking_budget=1000)
        return outline

    def flatten_outline(self, outline: List[Dict]) -> List[Dict]:
        """
        Flatten outline structure to page list
        Based on demo.py flatten_outline()
        """
        pages = []
        for item in outline:
            if "part" in item and "pages" in item:
                # This is a part, expand its pages
                for page in item["pages"]:
                    page_with_part = page.copy()
                    page_with_part["part"] = item["part"]
                    pages.append(page_with_part)
            else:
                # This is a direct page
                pages.append(item)
        return pages

    def generate_page_description(
        self,
        project_context: ProjectContext,
        outline: List[Dict],
        page_outline: Dict,
        page_index: int,
        language="zh",
        detail_level: str = "default",
    ) -> str:
        """
        Generate description for a single page
        Based on demo.py gen_desc() logic

        Args:
            project_context: 项目上下文对象，包含所有原始信息
            outline: Complete outline
            page_outline: Outline for this specific page
            page_index: Page number (1-indexed)
            detail_level: Description detail level (concise/default/detailed)

        Returns:
            Text description for the page
        """
        part_info = (
            f"\nThis page belongs to: {page_outline['part']}"
            if "part" in page_outline
            else ""
        )

        desc_prompt = get_page_description_prompt(
            project_context=project_context,
            outline=outline,
            page_outline=page_outline,
            page_index=page_index,
            part_info=part_info,
            language=language,
            detail_level=detail_level,
        )

        # 根据 enable_text_reasoning 配置调整 thinking_budget
        actual_budget = self._get_text_thinking_budget()
        response_text = self.text_provider.generate_text(
            desc_prompt, thinking_budget=actual_budget
        )

        return dedent(response_text)

    def generate_outline_text(self, outline: List[Dict]) -> str:
        """
        Convert outline to text format for prompts
        Based on demo.py gen_outline_text()
        """
        text_parts = []
        for i, item in enumerate(outline, 1):
            if "part" in item and "pages" in item:
                text_parts.append(f"{i}. {item['part']}")
            else:
                text_parts.append(f"{i}. {item.get('title', 'Untitled')}")
        result = "\n".join(text_parts)
        return dedent(result)

    def generate_image_prompt(
        self,
        outline: List[Dict],
        page: Dict,
        page_desc: str,
        page_index: int,
        has_material_images: bool = False,
        extra_requirements: Optional[str] = None,
        language="zh",
        has_template: bool = True,
    ) -> str:
        """
        Generate image generation prompt for a page
        Based on demo.py gen_prompts()

        Args:
            outline: Complete outline
            page: Page outline data
            page_desc: Page description text
            page_index: Page number (1-indexed)
            has_material_images: 是否有素材图片（从项目描述中提取的图片）
            extra_requirements: Optional extra requirements to apply to all pages
            language: Output language
            has_template: 是否有模板图片（False表示无模板图模式）

        Returns:
            Image generation prompt
        """
        outline_text = self.generate_outline_text(outline)

        # Determine current section
        if "part" in page:
            current_section = page["part"]
        else:
            current_section = f"{page.get('title', 'Untitled')}"

        # 在传给文生图模型之前，移除 Markdown 图片链接
        # 图片本身已经通过 additional_ref_images 传递，只保留文字描述
        cleaned_page_desc = self.remove_markdown_images(page_desc)

        prompt = get_image_generation_prompt(
            page_desc=cleaned_page_desc,
            outline_text=outline_text,
            current_section=current_section,
            has_material_images=has_material_images,
            extra_requirements=extra_requirements,
            language=language,
            has_template=has_template,
            page_index=page_index,
        )

        return prompt

    def generate_image(
        self,
        prompt: str,
        ref_image_path: Optional[str] = None,
        aspect_ratio: str = "16:9",
        resolution: str = "2K",
        additional_ref_images: Optional[List[Union[str, Image.Image]]] = None,
    ) -> Optional[Image.Image]:
        """
        Generate image using configured image provider
        Based on gemini_genai.py gen_image()

        Args:
            prompt: Image generation prompt
            ref_image_path: Path to reference image (optional). If None, will generate based on prompt only.
            aspect_ratio: Image aspect ratio
            resolution: Image resolution (note: OpenAI format only supports 1K)
            additional_ref_images: 额外的参考图片列表，可以是本地路径、URL 或 PIL Image 对象

        Returns:
            PIL Image object or None if failed

        Raises:
            Exception with detailed error message if generation fails
        """
        try:
            logger.debug(f"Reference image: {ref_image_path}")
            if additional_ref_images:
                logger.debug(
                    f"Additional reference images: {len(additional_ref_images)}"
                )
            logger.debug(
                f"Config - aspect_ratio: {aspect_ratio}, resolution: {resolution}"
            )

            # 构建参考图片列表
            ref_images = []

            # 添加主参考图片（如果提供了路径）
            if ref_image_path:
                if not os.path.exists(ref_image_path):
                    raise FileNotFoundError(
                        f"Reference image not found: {ref_image_path}"
                    )
                main_ref_image = Image.open(ref_image_path)
                ref_images.append(main_ref_image)

            # 添加额外的参考图片
            if additional_ref_images:
                for ref_img in additional_ref_images:
                    if isinstance(ref_img, Image.Image):
                        # 已经是 PIL Image 对象
                        ref_images.append(ref_img)
                    elif isinstance(ref_img, str):
                        # 可能是本地路径或 URL
                        if os.path.exists(ref_img):
                            # 本地路径
                            ref_images.append(Image.open(ref_img))
                        elif ref_img.startswith("http://") or ref_img.startswith(
                            "https://"
                        ):
                            # URL，需要下载
                            downloaded_img = self.download_image_from_url(ref_img)
                            if downloaded_img:
                                ref_images.append(downloaded_img)
                            else:
                                logger.warning(
                                    f"Failed to download image from URL: {ref_img}, skipping..."
                                )
                        elif ref_img.startswith("/files/mineru/"):
                            # MinerU 本地文件路径，需要转换为文件系统路径（支持前缀匹配）
                            local_path = self._convert_mineru_path_to_local(ref_img)
                            if local_path and os.path.exists(local_path):
                                ref_images.append(Image.open(local_path))
                                logger.debug(
                                    f"Loaded MinerU image from local path: {local_path}"
                                )
                            else:
                                logger.warning(
                                    f"MinerU image file not found (with prefix matching): {ref_img}, skipping..."
                                )
                        elif ref_img.startswith("/files/"):
                            # 通用 /files/ 路径（materials、项目文件等），转换为文件系统路径
                            upload_folder = get_config().UPLOAD_FOLDER
                            relative_path = ref_img[len("/files/") :].lstrip("/")
                            local_path = os.path.abspath(
                                os.path.join(upload_folder, relative_path)
                            )
                            if not local_path.startswith(
                                os.path.abspath(upload_folder)
                            ):
                                logger.warning(
                                    f"Path traversal attempt blocked: {ref_img}, skipping..."
                                )
                            elif os.path.exists(local_path):
                                ref_images.append(Image.open(local_path))
                                logger.debug(
                                    f"Loaded image from local path: {local_path}"
                                )
                            else:
                                logger.warning(
                                    f"Local file not found: {local_path} (from {ref_img}), skipping..."
                                )
                        else:
                            logger.warning(
                                f"Invalid image reference: {ref_img}, skipping..."
                            )

            logger.debug(
                f"Calling image provider for generation with {len(ref_images)} reference images..."
            )
            logger.debug(
                f"Enable image reasoning/thinking: {self.enable_image_reasoning}, budget: {self._get_image_thinking_budget()}"
            )

            # 使用 image_provider 生成图片
            # 根据 enable_image_reasoning 配置控制图像生成的思考模式
            return self.image_provider.generate_image(
                prompt=prompt,
                ref_images=ref_images if ref_images else None,
                aspect_ratio=aspect_ratio,
                resolution=resolution,
                enable_thinking=self.enable_image_reasoning,
                thinking_budget=self._get_image_thinking_budget(),
            )

        except Exception as e:
            error_detail = f"Error generating image: {type(e).__name__}: {str(e)}"
            logger.error(error_detail, exc_info=True)
            raise Exception(error_detail) from e

    def edit_image(
        self,
        prompt: str,
        current_image_path: str,
        aspect_ratio: str = "16:9",
        resolution: str = "2K",
        original_description: str = None,
        additional_ref_images: Optional[List[Union[str, Image.Image]]] = None,
    ) -> Optional[Image.Image]:
        """
        Edit existing image with natural language instruction
        Uses current image as reference

        Args:
            prompt: Edit instruction
            current_image_path: Path to current page image
            aspect_ratio: Image aspect ratio
            resolution: Image resolution
            original_description: Original page description to include in prompt
            additional_ref_images: 额外的参考图片列表，可以是本地路径、URL 或 PIL Image 对象

        Returns:
            PIL Image object or None if failed
        """
        # Build edit instruction with original description if available
        edit_instruction = get_image_edit_prompt(
            edit_instruction=prompt, original_description=original_description
        )
        return self.generate_image(
            edit_instruction,
            current_image_path,
            aspect_ratio,
            resolution,
            additional_ref_images,
        )

    def parse_description_to_outline(
        self, project_context: ProjectContext, language="zh"
    ) -> List[Dict]:
        """
        从描述文本解析出大纲结构

        Args:
            project_context: 项目上下文对象，包含所有原始信息

        Returns:
            List of outline items (may contain parts with pages or direct pages)
        """
        parse_prompt = get_description_to_outline_prompt(project_context, language)
        outline = self.generate_json(parse_prompt, thinking_budget=1000)
        return outline

    def parse_description_to_page_descriptions(
        self, project_context: ProjectContext, outline: List[Dict], language="zh"
    ) -> List[str]:
        """
        从描述文本切分出每页描述

        Args:
            project_context: 项目上下文对象，包含所有原始信息
            outline: 已解析出的大纲结构

        Returns:
            List of page descriptions (strings), one for each page in the outline
        """
        split_prompt = get_description_split_prompt(project_context, outline, language)
        descriptions = self.generate_json(split_prompt, thinking_budget=1000)

        # 确保返回的是字符串列表
        if isinstance(descriptions, list):
            return [str(desc) for desc in descriptions]
        else:
            raise ValueError(
                "Expected a list of page descriptions, but got: "
                + str(type(descriptions))
            )

    def refine_outline(
        self,
        current_outline: List[Dict],
        user_requirement: str,
        project_context: ProjectContext,
        previous_requirements: Optional[List[str]] = None,
        enable_web_search: bool = True,
        language="zh",
    ) -> List[Dict]:
        """
        根据用户要求修改已有大纲

        Args:
            current_outline: 当前的大纲结构
            user_requirement: 用户的新要求
            project_context: 项目上下文对象，包含所有原始信息
            previous_requirements: 之前的修改要求列表（可选）
            enable_web_search: 是否启用联网搜索
            language: 输出语言

        Returns:
            修改后的大纲结构
        """
        web_search_results = None
        if enable_web_search:
            try:
                from .ppt_outline_agent.tools.web_search import web_search

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                search_results = loop.run_until_complete(
                    web_search(user_requirement, max_results=5)
                )
                web_search_results = search_results.get("results", [])
                logger.info(f"Web search found {len(web_search_results)} results")
            except Exception as e:
                logger.warning(
                    f"Web search failed: {e}, continuing without search results"
                )
                web_search_results = None

        refinement_prompt = get_outline_refinement_prompt(
            current_outline=current_outline,
            user_requirement=user_requirement,
            project_context=project_context,
            previous_requirements=previous_requirements,
            web_search_results=web_search_results,
            language=language,
        )
        outline = self.generate_json(refinement_prompt, thinking_budget=1000)
        return outline

    def refine_descriptions(
        self,
        current_descriptions: List[Dict],
        user_requirement: str,
        project_context: ProjectContext,
        outline: List[Dict] = None,
        previous_requirements: Optional[List[str]] = None,
        enable_web_search: bool = True,
        language="zh",
    ) -> List[str]:
        """
        根据用户要求修改已有页面描述

        Args:
            current_descriptions: 当前的页面描述列表，每个元素包含 {index, title, description_content}
            user_requirement: 用户的新要求
            project_context: 项目上下文对象，包含所有原始信息
            outline: 完整的大纲结构（可选）
            previous_requirements: 之前的修改要求列表（可选）
            enable_web_search: 是否启用联网搜索
            language: 输出语言

        Returns:
            修改后的页面描述列表（字符串列表）
        """
        web_search_results = None
        if enable_web_search:
            try:
                from .ppt_outline_agent.tools.web_search import web_search

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                search_results = loop.run_until_complete(
                    web_search(user_requirement, max_results=5)
                )
                web_search_results = search_results.get("results", [])
                logger.info(f"Web search found {len(web_search_results)} results")
            except Exception as e:
                logger.warning(
                    f"Web search failed: {e}, continuing without search results"
                )
                web_search_results = None

        refinement_prompt = get_descriptions_refinement_prompt(
            current_descriptions=current_descriptions,
            user_requirement=user_requirement,
            project_context=project_context,
            outline=outline,
            previous_requirements=previous_requirements,
            web_search_results=web_search_results,
            language=language,
        )
        descriptions = self.generate_json(refinement_prompt, thinking_budget=1000)

        # 确保返回的是字符串列表
        if isinstance(descriptions, list):
            return [str(desc) for desc in descriptions]
        else:
            raise ValueError(
                "Expected a list of page descriptions, but got: "
                + str(type(descriptions))
            )
        descriptions = self.generate_json(refinement_prompt, thinking_budget=1000)

        # 确保返回的是字符串列表
        if isinstance(descriptions, list):
            return [str(desc) for desc in descriptions]
        else:
            raise ValueError(
                "Expected a list of page descriptions, but got: "
                + str(type(descriptions))
            )

    def extract_page_content(self, markdown_text: str, language: str = "zh") -> Dict:
        """
        从 fileparser 解析出的 markdown 文本中提取页面结构化内容

        Args:
            markdown_text: 单页 PDF 解析出的 markdown 文本
            language: 输出语言

        Returns:
            Dict with keys: title, points, description
        """
        prompt = get_ppt_page_content_extraction_prompt(
            markdown_text, language=language
        )
        result = self.generate_json(prompt, thinking_budget=1000)

        # Ensure required fields exist
        if not isinstance(result, dict):
            raise ValueError(f"Expected dict, got {type(result)}")

        result.setdefault("title", "")
        result.setdefault("points", [])
        result.setdefault("description", "")

        return result

    def _generate_text_from_image(self, prompt: str, image_path: str) -> str:
        """Helper to generate text from a prompt and an image, using caption_provider."""
        actual_budget = self._get_text_thinking_budget()
        provider = self.caption_provider

        if hasattr(provider, "generate_with_image"):
            response_text = provider.generate_with_image(
                prompt=prompt, image_path=image_path, thinking_budget=actual_budget
            )
        elif hasattr(provider, "generate_text_with_images"):
            response_text = provider.generate_text_with_images(
                prompt=prompt, images=[image_path], thinking_budget=actual_budget
            )
        else:
            raise ValueError("caption_provider 不支持图片输入")

        return response_text.strip()

    def generate_layout_caption(self, image_path: str) -> str:
        """使用 caption model 描述 PPT 页面的排版布局"""
        return self._generate_text_from_image(get_layout_caption_prompt(), image)

    def extract_style_description(self, image_path: str) -> str:
        """从图片中提取风格描述"""
        return self._generate_text_from_image(get_style_extraction_prompt(), image_path)

    def refine_page_outline(
        self,
        page_outline: Dict,
        user_requirement: str,
        project_context: ProjectContext,
        enable_web_search: bool = True,
        language="zh",
    ) -> Dict:
        """
        根据用户要求修改单页大纲

        Args:
            page_outline: 当前页面的大纲结构
            user_requirement: 用户的新要求
            project_context: 项目上下文对象
            enable_web_search: 是否启用联网搜索
            language: 输出语言

        Returns:
            修改后的页面大纲结构
        """
        web_search_results = None
        if enable_web_search:
            try:
                from .ppt_outline_agent.tools.web_search import web_search

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                search_results = loop.run_until_complete(
                    web_search(user_requirement, max_results=5)
                )
                web_search_results = search_results.get("results", [])
                logger.info(f"Web search found {len(web_search_results)} results")
            except Exception as e:
                logger.warning(
                    f"Web search failed: {e}, continuing without search results"
                )
                web_search_results = None

        refinement_prompt = get_page_outline_refinement_prompt(
            page_outline=page_outline,
            user_requirement=user_requirement,
            project_context=project_context,
            web_search_results=web_search_results,
            language=language,
        )
        refined_outline = self.generate_json(refinement_prompt, thinking_budget=1000)
        return refined_outline

    def refine_page_description(
        self,
        page_description: str,
        page_outline: Dict,
        user_requirement: str,
        project_context: ProjectContext,
        enable_web_search: bool = True,
        language="zh",
    ) -> str:
        """
        根据用户要求修改单页描述

        Args:
            page_description: 当前页面的描述文本
            page_outline: 当前页面的大纲结构
            user_requirement: 用户的新要求
            project_context: 项目上下文对象
            enable_web_search: 是否启用联网搜索
            language: 输出语言

        Returns:
            修改后的页面描述文本
        """
        web_search_results = None
        if enable_web_search:
            try:
                from .ppt_outline_agent.tools.web_search import web_search

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                search_results = loop.run_until_complete(
                    web_search(user_requirement, max_results=5)
                )
                web_search_results = search_results.get("results", [])
                logger.info(f"Web search found {len(web_search_results)} results")
            except Exception as e:
                logger.warning(
                    f"Web search failed: {e}, continuing without search results"
                )
                web_search_results = None

        refinement_prompt = get_page_description_refinement_prompt(
            page_description=page_description,
            page_outline=page_outline,
            user_requirement=user_requirement,
            project_context=project_context,
            web_search_results=web_search_results,
            language=language,
        )
        refined_description = self.generate_json(
            refinement_prompt, thinking_budget=1000
        )

        # 确保返回字符串
        if isinstance(refined_description, str):
            return refined_description
        elif (
            isinstance(refined_description, dict)
            and "description" in refined_description
        ):
            return refined_description["description"]
        else:
            return str(refined_description)

    def refine_element(
        self,
        element: Dict,
        user_requirement: str,
        project_context: ProjectContext,
        enable_web_search: bool = True,
        language="zh",
    ) -> Dict:
        """
        根据用户要求修改单个element

        Args:
            element: 当前element的数据结构
            user_requirement: 用户的新要求
            project_context: 项目上下文对象
            enable_web_search: 是否启用联网搜索
            language: 输出语言

        Returns:
            修改后的element数据结构
        """
        web_search_results = None
        if enable_web_search:
            try:
                from .ppt_outline_agent.tools.web_search import web_search

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                search_results = loop.run_until_complete(
                    web_search(user_requirement, max_results=5)
                )
                web_search_results = search_results.get("results", [])
                logger.info(f"Web search found {len(web_search_results)} results")
            except Exception as e:
                logger.warning(
                    f"Web search failed: {e}, continuing without search results"
                )
                web_search_results = None

        refinement_prompt = get_element_refinement_prompt(
            element=element,
            user_requirement=user_requirement,
            project_context=project_context,
            web_search_results=web_search_results,
            language=language,
        )
        refined_element = self.generate_json(refinement_prompt, thinking_budget=1000)
        return refined_element
