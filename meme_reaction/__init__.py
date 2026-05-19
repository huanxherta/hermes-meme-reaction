"""meme-reaction plugin.

Pure-plugin automatic meme/sticker reactions:
- pre_gateway_dispatch caches the current route for each session.
- post_llm_call asks the host LLM whether the just-finished assistant reply
  should get a meme tail.
- selected media is sent through Hermes' cross-platform send_message tool using
  MEDIA:<path>, never through a platform-specific API.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from .config import load_meme_reaction_config
from .importer import import_libraries
from .index import MemeIndex
from .prompts import MOOD_DECISION_INSTRUCTIONS, MOOD_DECISION_SCHEMA
from .selector import MemeDecision, load_recent_history, select_meme

logger = logging.getLogger(__name__)

_ROUTES: dict[str, dict[str, Any]] = {}
_LAST_SENT_AT: dict[str, float] = {}
_CTX = None


def _platform_name(platform: Any) -> str:
    return str(getattr(platform, "value", platform) or "").lower()


def _session_key_from_event(event: Any, session_store: Any = None) -> str:
    source = getattr(event, "source", None)
    if source is None:
        return ""
    try:
        if session_store is not None:
            entry = session_store.get_or_create_session(source)
            if getattr(entry, "session_id", None):
                return str(entry.session_id)
            if getattr(entry, "session_key", None):
                return str(entry.session_key)
    except Exception:
        pass
    parts = [
        _platform_name(getattr(source, "platform", "")),
        str(getattr(source, "chat_id", "") or ""),
        str(getattr(source, "thread_id", "") or ""),
        str(getattr(source, "user_id", "") or ""),
    ]
    return ":".join(parts)


def _target_from_route(route: dict[str, Any]) -> str | None:
    platform = str(route.get("platform") or "").lower()
    chat_id = str(route.get("chat_id") or "")
    thread_id = route.get("thread_id")
    if not platform or not chat_id:
        return None
    if thread_id is not None and str(thread_id):
        return f"{platform}:{chat_id}:{thread_id}"
    return f"{platform}:{chat_id}"


def _on_pre_gateway_dispatch(**kwargs: Any):
    event = kwargs.get("event")
    session_store = kwargs.get("session_store")
    source = getattr(event, "source", None)
    if source is None:
        return None
    cfg = load_meme_reaction_config()
    platform = _platform_name(getattr(source, "platform", ""))
    if not cfg.enabled or not cfg.platform_allowed(platform):
        return None
    key = _session_key_from_event(event, session_store)
    if not key:
        return None
    _ROUTES[key] = {
        "session_key": key,
        "platform": platform,
        "chat_id": str(getattr(source, "chat_id", "") or ""),
        "thread_id": getattr(source, "thread_id", None),
        "user_id": str(getattr(source, "user_id", "") or ""),
        "user_name": str(getattr(source, "user_name", "") or ""),
        "text": getattr(event, "text", "") or "",
        "timestamp": time.time(),
    }
    return None


def _build_decision_input(user_message: Any, assistant_response: str, history: list[dict[str, Any]]) -> str:
    recent = []
    for msg in (history or [])[-8:]:
        role = msg.get("role")
        content = msg.get("content")
        if isinstance(content, list):
            content = "[multimodal content]"
        if isinstance(content, str):
            recent.append({"role": role, "content": content[:500]})
    return json.dumps(
        {
            "user_message": user_message if isinstance(user_message, str) else str(user_message),
            "assistant_response": assistant_response,
            "recent_context": recent,
            "instruction": "表情包是助手回复后的尾巴；必须同时贴合用户情绪、助手回复语气、二者关系。",
        },
        ensure_ascii=False,
    )


def _decide_with_llm(ctx: Any, cfg, *, user_message: Any, assistant_response: str, history: list[dict[str, Any]]) -> MemeDecision | None:
    if not cfg.llm.enabled:
        return None
    try:
        result = ctx.llm.complete_structured(
            instructions=MOOD_DECISION_INSTRUCTIONS,
            input=[{"type": "text", "text": _build_decision_input(user_message, assistant_response, history)}],
            json_schema=MOOD_DECISION_SCHEMA,
            json_mode=True,
            provider=cfg.llm.provider,
            model=cfg.llm.model,
            timeout=cfg.llm.timeout_seconds,
            max_tokens=500,
            temperature=0.2,
            purpose="meme_reaction_decision",
        )
        parsed = getattr(result, "parsed", None)
        if isinstance(parsed, dict):
            return MemeDecision.from_dict(parsed)
        text = getattr(result, "text", "") or ""
        if text:
            return MemeDecision.from_dict(json.loads(text))
    except Exception as exc:
        logger.debug("meme-reaction LLM decision failed: %s", exc, exc_info=True)
    return None


def _append_history(path: Path, payload: dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        logger.debug("Failed to append meme reaction history", exc_info=True)


def _on_post_llm_call(**kwargs: Any):
    ctx = _CTX
    if ctx is None:
        return None
    cfg = load_meme_reaction_config()
    if not cfg.enabled or cfg.trigger_weight <= 0:
        return None

    session_id = str(kwargs.get("session_id") or "")
    route = _ROUTES.get(session_id)
    if route is None:
        # Fallback for stores that keyed pre-dispatch by route rather than final session id.
        platform = str(kwargs.get("platform") or "").lower()
        candidates = [r for r in _ROUTES.values() if (not platform or r.get("platform") == platform)]
        route = max(candidates, key=lambda r: r.get("timestamp", 0), default=None)
    if not route:
        return None
    if time.time() - float(route.get("timestamp") or 0) > 600:
        return None
    platform = route.get("platform")
    if not cfg.platform_allowed(platform):
        return None

    now = time.time()
    route_key = str(route.get("session_key") or session_id or _target_from_route(route) or "default")
    if cfg.cooldown_seconds and now - _LAST_SENT_AT.get(route_key, 0) < cfg.cooldown_seconds:
        return None

    index = MemeIndex.load(cfg.index_path)
    if not index.items:
        return None
    decision = _decide_with_llm(
        ctx,
        cfg,
        user_message=kwargs.get("user_message"),
        assistant_response=str(kwargs.get("assistant_response") or ""),
        history=kwargs.get("conversation_history") or [],
    )
    if decision is None or not decision.passes(cfg):
        return None

    recent = load_recent_history(cfg.history_path)
    item = select_meme(decision, index, cfg, recent=recent)
    if item is None:
        return None
    target = _target_from_route(route)
    if not target:
        return None

    try:
        result_raw = ctx.dispatch_tool(
            "send_message",
            {
                "action": "send",
                "target": target,
                "message": f"MEDIA:{item.path}",
            },
        )
        result = json.loads(result_raw) if isinstance(result_raw, str) else result_raw
        if isinstance(result, dict) and result.get("success"):
            _LAST_SENT_AT[route_key] = now
            _append_history(
                cfg.history_path,
                {
                    "ts": now,
                    "id": item.id,
                    "path": item.path,
                    "tags": item.tags,
                    "moods": item.moods,
                    "target": target,
                    "decision": {
                        "score": decision.send_score,
                        "final_score": decision.final_score(cfg),
                        "reason": decision.reason,
                    },
                },
            )
        else:
            logger.debug("meme-reaction send_message result: %s", result)
    except Exception as exc:
        logger.debug("meme-reaction send failed: %s", exc, exc_info=True)
    return None


def _tool_import(params: dict[str, Any], **kwargs: Any) -> str:
    del kwargs
    cfg = load_meme_reaction_config()
    path = params.get("path")
    if path:
        from .config import MemeLibraryConfig
        cfg.libraries = (MemeLibraryConfig(name="manual", path=Path(str(path)).expanduser(), recursive=bool(params.get("recursive", True))),)
    index = import_libraries(cfg)
    return json.dumps({"success": True, "count": len(index.items), "index_path": str(cfg.index_path)}, ensure_ascii=False)


def _tool_search(params: dict[str, Any], **kwargs: Any) -> str:
    del kwargs
    cfg = load_meme_reaction_config()
    tags = [str(x).lower() for x in (params.get("tags") or [])]
    query = str(params.get("query") or "").lower()
    items = []
    for item in MemeIndex.load(cfg.index_path).existing_enabled():
        hay = " ".join(item.tags + item.moods + item.safe_for + [item.caption]).lower()
        if (tags and not any(tag in hay for tag in tags)) or (query and query not in hay):
            continue
        items.append({"id": item.id, "path": item.path, "caption": item.caption, "tags": item.tags, "moods": item.moods})
        if len(items) >= int(params.get("limit") or 10):
            break
    return json.dumps({"success": True, "items": items}, ensure_ascii=False)


def register(ctx) -> None:
    global _CTX
    _CTX = ctx
    ctx.register_hook("pre_gateway_dispatch", _on_pre_gateway_dispatch)
    ctx.register_hook("post_llm_call", _on_post_llm_call)

    ctx.register_tool(
        name="meme_import",
        toolset="meme_reaction",
        schema={
            "name": "meme_import",
            "description": "Import a local meme/sticker folder into the meme reaction index.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Folder path to import. Defaults to configured libraries."},
                    "recursive": {"type": "boolean", "description": "Scan recursively when path is provided."},
                },
            },
        },
        handler=_tool_import,
        description="Import local meme/sticker folders into the meme reaction index.",
    )
    ctx.register_tool(
        name="meme_search",
        toolset="meme_reaction",
        schema={
            "name": "meme_search",
            "description": "Search the meme reaction index by tags or text.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "query": {"type": "string"},
                    "limit": {"type": "integer"},
                },
            },
        },
        handler=_tool_search,
        description="Search indexed meme/sticker metadata.",
    )
