"""Plan Agent — LangGraph ReAct agent for conversational outline generation."""
from __future__ import annotations

import json
import logging
import re
import uuid

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.types import interrupt
from pydantic import ValidationError

from .prompts import PLAN_SYSTEM_PROMPT
from .state import PlanState
from ..tools.plan_tools import PLAN_TOOLS
from ..config import settings

logger = logging.getLogger(__name__)

# Types that should not receive enrichment
_SKIP_ENRICH_TYPES = {"cover", "closing", "section_header", "toc"}


def _enrich_sparse_slides(outline: dict) -> dict:
    """Scan outline and auto-add visual placeholders to text-only content slides.

    This ensures every content slide has at least one visual element before
    it reaches the Build Agent, which will generate real data for it.
    """
    text_types = {"text", "bullet_list", "subtitle", "title"}
    visual_types = {"chart", "table", "image"}

    for slide in outline.get("slides", []):
        stype = slide.get("slide_type", "content")
        if stype in _SKIP_ENRICH_TYPES:
            continue

        elements = slide.get("elements", [])
        types_present = {e.get("type", "text") for e in elements}

        has_text = bool(types_present & text_types)
        has_visual = bool(types_present & visual_types)

        # Text-only → add a chart placeholder
        if has_text and not has_visual:
            elements.append({
                "type": "chart",
                "chart_type": "bar",
                "content": slide.get("title", ""),
            })

        # Empty slide → add bullet_list + chart placeholder
        if not elements:
            elements.append({"type": "bullet_list", "bullet_items": []})
            elements.append({
                "type": "chart",
                "chart_type": "bar",
                "content": slide.get("title", ""),
            })

        slide["elements"] = elements

    return outline


# Tool name -> parameter names for recovering malformed tool calls
_TOOL_SCHEMAS: dict[str, list[str]] = {
    t.name: list(
        t.args_schema.model_json_schema().get("properties", {}).keys()
    )
    for t in PLAN_TOOLS
    if hasattr(t, "args_schema") and t.args_schema
}


def _get_model():
    """Create the LLM with tool-calling bound."""
    try:
        llm = ChatOpenAI(
            base_url=settings.chat_model_base_url,
            api_key=settings.chat_model_api_key,
            model=settings.chat_model_name,
            max_tokens=16384,
            temperature=0.7,
            default_headers={"User-Agent": "AutoSlides/1.0"},
        )
        return llm.bind_tools(PLAN_TOOLS)
    except Exception as e:
        logger.error("Failed to create ChatOpenAI model: %s", str(e)[:500])
        # Fallback to direct API call
        return _create_requests_model()


def _create_requests_model():
    """Create a simple model wrapper that uses requests for API calls."""
    import requests

    class RequestsModel:
        """Simple wrapper using requests for LLM calls."""

        def __init__(self):
            self.session = requests.Session()
            self.session.verify = False
            self.session.headers.update({
                'Content-Type': 'application/json',
                'User-Agent': 'AutoSlides/1.0',
            })

        async def ainvoke(self, messages):
            """Invoke model using requests."""
            url = f"{settings.chat_model_base_url}/chat/completions"

            # Convert messages to OpenAI format
            oai_messages = []
            for m in messages:
                if isinstance(m, SystemMessage):
                    oai_messages.append({"role": "system", "content": m.content})
                elif isinstance(m, HumanMessage):
                    oai_messages.append({"role": "user", "content": m.content})
                elif isinstance(m, AIMessage):
                    msg_dict: dict = {"role": "assistant", "content": m.content or ""}
                    if m.tool_calls:
                        msg_dict["tool_calls"] = [
                            {
                                "id": tc.get("id", f"call_{uuid.uuid4().hex[:12]}"),
                                "type": "function",
                                "function": {
                                    "name": tc["name"],
                                    "arguments": json.dumps(tc["args"], ensure_ascii=False),
                                },
                            }
                            for tc in m.tool_calls
                        ]
                    oai_messages.append(msg_dict)
                elif isinstance(m, ToolMessage):
                    oai_messages.append({
                        "role": "tool",
                        "tool_call_id": m.tool_call_id,
                        "content": m.content,
                    })

            # Build tool definitions
            tool_defs = []
            for t in PLAN_TOOLS:
                schema = t.args_schema.model_json_schema() if hasattr(t, "args_schema") and t.args_schema else {}
                props = schema.get("properties", {})
                required = schema.get("required", [])
                tool_defs.append({
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description or "",
                        "parameters": {
                            "type": "object",
                            "properties": props,
                            "required": required,
                        },
                    },
                })

            payload = {
                "model": settings.chat_model_name,
                "messages": oai_messages,
                "tools": tool_defs,
                "max_tokens": 16384,
                "temperature": 0.7,
            }

            def make_request():
                self.session.headers['Authorization'] = f"Bearer {settings.chat_model_api_key}"
                resp = self.session.post(url, json=payload, timeout=60)
                resp.raise_for_status()
                return resp.json()

            try:
                import asyncio
                data = await asyncio.to_thread(make_request)

                choice = data["choices"][0]
                raw_msg = choice.message

                # Build tool_calls
                tool_calls = []
                if raw_msg.tool_calls:
                    for tc in raw_msg.tool_calls:
                        tc_id = tc.id or f"call_{uuid.uuid4().hex[:12]}"
                        name = tc.function.name
                        raw_args_str = tc.function.arguments

                        # Parse args
                        try:
                            parsed = json.loads(raw_args_str) if isinstance(raw_args_str, str) else raw_args_str
                        except json.JSONDecodeError:
                            repaired = _repair_json(raw_args_str)
                            if repaired:
                                parsed = json.loads(repaired)
                            else:
                                parsed = {"_raw": raw_args_str}

                        fixed_args = _fix_tool_call_args(name, parsed)
                        tool_calls.append({"name": name, "args": fixed_args, "id": tc_id})

                return AIMessage(
                    content=raw_msg.content or "",
                    tool_calls=tool_calls,
                )

            except Exception as e:
                logger.error("Requests model invoke failed: %s", str(e)[:500])
                raise

    return RequestsModel()


def _repair_json(s: str) -> str | None:
    """Try to repair truncated or malformed JSON from LLM tool call args."""
    s = s.strip()
    if not s:
        return None
    
    # Remove common prefix issues (e.g., "e" before JSON)
    if s.startswith("e"):
        s = s[1:].strip()
    if s and s[0] not in ('{', '[', '"', 'n', 't', 'f', 'N', 'T', 'F'):
        # Find first valid JSON character
        for i in range(len(s)):
            if s[i] in ('{', '[', '"'):
                s = s[i:]
                break
    
    if not s:
        return None
    
    # Try as-is first
    try:
        json.loads(s)
        return s
    except json.JSONDecodeError:
        pass
    
    # Try appending missing closing brackets/braces
    for suffix in ['"}', '"}]}', '"}]}]}', '"}]}]}]}', '}', ']}', ']}]}', ']}]}]}']:
        try:
            json.loads(s + suffix)
            return s + suffix
        except json.JSONDecodeError:
            continue
    
    # Try removing trailing garbage after last valid structure
    # Find the last } or ] and try truncating there
    for i in range(len(s) - 1, -1, -1):
        if s[i] in ('}', ']'):
            candidate = s[: i + 1]
            try:
                json.loads(candidate)
                return candidate
            except json.JSONDecodeError:
                continue
    
    return None


def _fix_tool_call_args(tool_name: str, args: dict | list | str) -> dict:
    """Fix tool call args that may be a list instead of a dict (GLM quirk)."""
    if isinstance(args, dict):
        return args

    if isinstance(args, str):
        repaired = _repair_json(args)
        if repaired:
            try:
                args = json.loads(repaired)
            except json.JSONDecodeError:
                logger.warning("Could not repair JSON args for tool %s", tool_name)
                return {"_raw": args}
        else:
            return {"_raw": args}

    if isinstance(args, list):
        # GLM sometimes wraps the args dict in a list
        if len(args) == 1 and isinstance(args[0], dict):
            return args[0]
        # Or returns the slides list as the top-level args
        schema_keys = _TOOL_SCHEMAS.get(tool_name, [])
        if "slides" in schema_keys:
            # Assume the list is the slides array
            return {"title": "Untitled", "slides": args}
        return {"_raw_list": args}

    return {"_raw": str(args)}


async def _safe_model_invoke(model, messages) -> AIMessage:
    """Invoke the model with error recovery for malformed tool call responses.

    Some LLM APIs (e.g. GLM) may return tool_calls with args as a list instead
    of a dict, or with truncated/malformed JSON. This wrapper catches those
    errors and attempts to recover by making a raw API call and manually
    constructing the AIMessage.
    """
    try:
        return await model.ainvoke(messages)
    except (ValidationError, Exception) as exc:
        error_str = str(exc)
        logger.error("Model invoke error for %s: %s", settings.chat_model_name, error_str[:1000])
        
        # Check for specific error: invalid character 'e' or bad_response_body
        # This typically means the model/API doesn't support the request format
        if "invalid character 'e'" in error_str or "bad_response_body" in error_str or "bad_request" in error_str:
            logger.warning("Model %s may not support tools or request format, trying simple request", settings.chat_model_name)
            # Try calling model without tools and minimal parameters
            try:
                import openai
                client = openai.AsyncOpenAI(
                    base_url=settings.chat_model_base_url,
                    api_key=settings.chat_model_api_key,
                    default_headers={"User-Agent": "AutoSlides/1.0"},
                )
                
                # Convert to simple message format
                user_content = "\n\n".join([
                    f"{m.get('role', '')}: {m.get('content', '')[:200]}"
                    for m in messages if m.get('role') in ['user', 'system']
                ])
                
                raw_response = await client.chat.completions.create(
                    model=settings.chat_model_name,
                    messages=[{"role": "user", "content": user_content}],
                    max_tokens=1000,  # Use smaller limit to avoid issues
                    temperature=0.7,
                )
                
                content = raw_response.choices[0].message.content or ""
                logger.info("Simple request successful, response: %s", content[:200])
                return AIMessage(content=content)
            except Exception as e2:
                logger.error("Simple request also failed: %s", str(e2)[:500])
                raise exc from e2
        
        if "tool_calls" not in error_str and "dict_type" not in error_str:
            raise  # Not a tool-call format issue, re-raise

        logger.warning("LLM returned malformed tool_calls, attempting recovery: %s", error_str[:200])

        # Fall back to raw OpenAI-compatible API call
        import openai

        client = openai.AsyncOpenAI(
            base_url=settings.chat_model_base_url,
            api_key=settings.chat_model_api_key,
            default_headers={"User-Agent": "AutoSlides/1.0"},
        )

        # Convert LangChain messages to OpenAI format
        oai_messages = []
        for m in messages:
            if isinstance(m, SystemMessage):
                oai_messages.append({"role": "system", "content": m.content})
            elif isinstance(m, HumanMessage):
                oai_messages.append({"role": "user", "content": m.content})
            elif isinstance(m, AIMessage):
                msg_dict: dict = {"role": "assistant", "content": m.content or ""}
                if m.tool_calls:
                    msg_dict["tool_calls"] = [
                        {
                            "id": tc.get("id", f"call_{uuid.uuid4().hex[:12]}"),
                            "type": "function",
                            "function": {
                                "name": tc["name"],
                                "arguments": json.dumps(tc["args"], ensure_ascii=False),
                            },
                        }
                        for tc in m.tool_calls
                    ]
                oai_messages.append(msg_dict)
            elif isinstance(m, ToolMessage):
                oai_messages.append({
                    "role": "tool",
                    "tool_call_id": m.tool_call_id,
                    "content": m.content,
                })

        # Build tool definitions
        tool_defs = []
        for t in PLAN_TOOLS:
            schema = t.args_schema.model_json_schema() if hasattr(t, "args_schema") and t.args_schema else {}
            props = schema.get("properties", {})
            required = schema.get("required", [])
            tool_defs.append({
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description or "",
                    "parameters": {
                        "type": "object",
                        "properties": props,
                        "required": required,
                    },
                },
            })

        raw_response = await client.chat.completions.create(
            model=settings.chat_model_name,
            messages=oai_messages,
            tools=tool_defs,
            max_tokens=16384,
            temperature=0.7,
        )

        choice = raw_response.choices[0]
        raw_msg = choice.message

        # Build tool_calls with fixed args
        tool_calls = []
        invalid_tool_calls = []
        if raw_msg.tool_calls:
            for tc in raw_msg.tool_calls:
                tc_id = tc.id or f"call_{uuid.uuid4().hex[:12]}"
                name = tc.function.name
                raw_args_str = tc.function.arguments

                # Parse and fix args
                try:
                    parsed = json.loads(raw_args_str) if isinstance(raw_args_str, str) else raw_args_str
                except json.JSONDecodeError:
                    repaired = _repair_json(raw_args_str)
                    if repaired:
                        parsed = json.loads(repaired)
                    else:
                        logger.error("Unrecoverable JSON in tool call %s", name)
                        invalid_tool_calls.append({
                            "name": name, "args": raw_args_str, "id": tc_id, "error": "Invalid JSON",
                        })
                        continue

                fixed_args = _fix_tool_call_args(name, parsed)
                tool_calls.append({"name": name, "args": fixed_args, "id": tc_id})

        return AIMessage(
            content=raw_msg.content or "",
            tool_calls=tool_calls,
            invalid_tool_calls=invalid_tool_calls,
        )

    except Exception as exc:
        error_str = str(exc)
        logger.error("Model invoke error for %s: %s", settings.chat_model_name, error_str[:1000])

        # Final fallback: use requests
        logger.warning("All OpenAI client attempts failed, using requests as final fallback")
        try:
            import asyncio

            import requests

            url = f"{settings.chat_model_base_url}/chat/completions"

            # Convert LangChain messages to OpenAI format
            oai_messages = []
            for m in messages:
                if isinstance(m, SystemMessage):
                    oai_messages.append({"role": "system", "content": m.content})
                elif isinstance(m, HumanMessage):
                    oai_messages.append({"role": "user", "content": m.content})
                elif isinstance(m, AIMessage):
                    msg_dict: dict = {"role": "assistant", "content": m.content or ""}
                    if m.tool_calls:
                        msg_dict["tool_calls"] = [
                            {
                                "id": tc.get("id", f"call_{uuid.uuid4().hex[:12]}"),
                                "type": "function",
                                "function": {
                                    "name": tc["name"],
                                    "arguments": json.dumps(tc["args"], ensure_ascii=False),
                                },
                            }
                            for tc in m.tool_calls
                        ]
                    oai_messages.append(msg_dict)
                elif isinstance(m, ToolMessage):
                    oai_messages.append({
                        "role": "tool",
                        "tool_call_id": m.tool_call_id,
                        "content": m.content,
                    })

            # Build tool definitions
            tool_defs = []
            for t in PLAN_TOOLS:
                schema = t.args_schema.model_json_schema() if hasattr(t, "args_schema") and t.args_schema else {}
                props = schema.get("properties", {})
                required = schema.get("required", [])
                tool_defs.append({
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description or "",
                        "parameters": {
                            "type": "object",
                            "properties": props,
                            "required": required,
                        },
                    },
                })

            payload = {
                "model": settings.chat_model_name,
                "messages": oai_messages,
                "tools": tool_defs,
                "max_tokens": 16384,
                "temperature": 0.7,
            }

            # Make request in thread to avoid blocking
            def make_request():
                session = requests.Session()
                session.verify = False
                session.headers.update({
                    'Authorization': f"Bearer {settings.chat_model_api_key}",
                    'Content-Type': 'application/json',
                    'User-Agent': 'AutoSlides/1.0',
                })
                resp = session.post(url, json=payload, timeout=60)
                resp.raise_for_status()
                return resp.json()

            data = await asyncio.to_thread(make_request)

            choice = data["choices"][0]
            raw_msg = choice.message

            # Build tool_calls
            tool_calls = []
            if raw_msg.tool_calls:
                for tc in raw_msg.tool_calls:
                    tc_id = tc.id or f"call_{uuid.uuid4().hex[:12]}"
                    name = tc.function.name
                    raw_args_str = tc.function.arguments

                    # Parse and fix args
                    try:
                        parsed = json.loads(raw_args_str) if isinstance(raw_args_str, str) else raw_args_str
                    except json.JSONDecodeError:
                        repaired = _repair_json(raw_args_str)
                        if repaired:
                            parsed = json.loads(repaired)
                        else:
                            logger.error("Unrecoverable JSON in tool call %s", name)
                            continue

                    fixed_args = _fix_tool_call_args(name, parsed)
                    tool_calls.append({"name": name, "args": fixed_args, "id": tc_id})

            return AIMessage(
                content=raw_msg.content or "",
                tool_calls=tool_calls,
            )

        except Exception as e2:
            logger.error("Requests fallback failed: %s", str(e2)[:500])
            raise exc from e2


# ── Node Functions ───────────────────────────────────────────────


async def agent_node(state: PlanState) -> dict:
    """Core agent node: call the LLM, which decides to respond or call tools."""
    model = _get_model()

    messages = list(state["messages"])

    # Build dynamic system prompt with current outline
    outline_context = ""
    if state.get("outline"):
        outline_context = (
            "\n\n## Current Outline\n```json\n"
            + json.dumps(state["outline"], ensure_ascii=False, indent=2)
            + "\n```"
        )

    sys_content = PLAN_SYSTEM_PROMPT + outline_context

    # Replace or insert system message at the beginning
    if messages and isinstance(messages[0], SystemMessage):
        messages[0] = SystemMessage(content=sys_content)
    else:
        messages.insert(0, SystemMessage(content=sys_content))

    response = await _safe_model_invoke(model, messages)
    return {"messages": [response]}


async def process_tool_results(state: PlanState) -> dict:
    """After tools execute, process their results to update state."""
    messages = state["messages"]
    result: dict = {}
    
    # Look at the most recent tool messages
    for msg in reversed(messages):
        if not isinstance(msg, ToolMessage):
            break
        
        logger.debug("Processing tool message: %s", msg.content[:200] if msg.content else "empty")
        
        try:
            data = json.loads(msg.content)
        except (json.JSONDecodeError, TypeError) as e:
            logger.debug("Tool result is not JSON: %s, content type: %s", e, type(msg.content))
            continue
        
        # Ensure data is a dict
        if not isinstance(data, dict):
            logger.warning("Tool result is not a dict: %s", type(data))
            continue
        
        # Handle create_outline result (has "title" and "slides" keys)
        if "title" in data and "slides" in data:
            result["outline"] = _enrich_sparse_slides(data)
            result["phase"] = "planning"
            continue
        
        # Handle modify_outline result (has "action" key)
        if "action" in data:
            current_outline = state.get("outline")
            
            # Ensure outline is a dict
            if current_outline is None:
                logger.warning("Outline is None, cannot modify. Skipping modify_outline tool result.")
                continue
                
            if not isinstance(current_outline, dict):
                logger.warning("Outline is not a dict: %s. Skipping modify_outline tool result.", type(current_outline))
                continue
                
            outline = dict(current_outline)
            
            if "slides" in outline:
                slides = list(outline.get("slides", []))
                action = data["action"]
                
                if action == "add":
                    idx = data.get("slide_index", -1)
                    new_slide = data.get("slide_data") or {}
                    if idx == -1 or idx >= len(slides):
                        slides.append(new_slide)
                    else:
                        slides.insert(idx, new_slide)
                    for i, s in enumerate(slides):
                        s["slide_index"] = i
                
                elif action == "remove":
                    idx = data.get("slide_index", -1)
                    if 0 <= idx < len(slides):
                        slides.pop(idx)
                    for i, s in enumerate(slides):
                        s["slide_index"] = i
                
                elif action == "move":
                    from_idx = data.get("slide_index", -1)
                    to_idx = data.get("target_index", -1)
                    if 0 <= from_idx < len(slides) and 0 <= to_idx <= len(slides):
                        moved = slides.pop(from_idx)
                        slides.insert(to_idx, moved)
                    for i, s in enumerate(slides):
                        s["slide_index"] = i
                
                elif action == "edit":
                    idx = data.get("slide_index", -1)
                    updates = data.get("updates") or {}
                    if 0 <= idx < len(slides):
                        slides[idx].update(updates)
                
                elif action == "edit_title":
                    updates = data.get("updates") or {}
                    if "title" in updates:
                        outline["title"] = updates["title"]
                    if "subtitle" in updates:
                        outline["subtitle"] = updates["subtitle"]
                
                outline["slides"] = slides
                outline["total_slides"] = len(slides)
                result["outline"] = outline
            continue
        
        # Handle confirm_outline result
        if data.get("confirmed"):
            result["outline_confirmed"] = True
            result["phase"] = "confirmed"
    
    return result


async def human_node(state: PlanState) -> dict:
    """Interrupt for human input. Resumes with user's message."""
    user_input = interrupt({
        "type": "wait_for_input",
        "phase": state.get("phase", "planning"),
        "has_outline": state.get("outline") is not None,
    })
    return {"messages": [HumanMessage(content=user_input)]}


# ── Routing Logic ────────────────────────────────────────────────


def should_continue(state: PlanState) -> str:
    """Route after agent_node: call tools, ask human, or end."""
    # If the outline is confirmed, we are done
    if state.get("outline_confirmed"):
        return "end"

    messages = state["messages"]
    last_message = messages[-1]

    # If the LLM wants to call tools, route to tool_node
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"

    # Otherwise, the LLM produced a text response -> wait for human
    return "human"


# ── Graph Construction ───────────────────────────────────────────


def build_plan_graph():
    """Build the Plan Agent as a ReAct agent graph."""
    graph = StateGraph(PlanState)

    tool_node = ToolNode(PLAN_TOOLS)

    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)
    graph.add_node("process_tools", process_tool_results)
    graph.add_node("human", human_node)

    # START -> agent (initial greeting)
    graph.add_edge(START, "agent")

    # agent -> tools | human | END
    graph.add_conditional_edges("agent", should_continue, {
        "tools": "tools",
        "human": "human",
        "end": END,
    })

    # tools -> process_tools -> agent (ReAct loop)
    graph.add_edge("tools", "process_tools")
    graph.add_edge("process_tools", "agent")

    # human -> agent (user input goes back to agent)
    graph.add_edge("human", "agent")

    return graph.compile(checkpointer=MemorySaver())
