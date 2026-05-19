"""meme-reaction plugin.

Pure-plugin automatic meme/sticker reactions:
- pre_gateway_dispatch caches the current route to a file (survives restarts).
- post_llm_call uses ctx.llm (host-owned, zero-config) to decide whether
  the assistant reply should get a meme tail.
- selected media is sent through Hermes' cross-platform send_message tool
  using MEDIA:<path>, never through a platform-specific API.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from .config import load_meme_reaction_config, _as_float, _as_int
from .importer import import_libraries
from .index import MemeIndex
from .prompts import MOOD_DECISION_INSTRUCTIONS, MOOD_DECISION_SCHEMA
from .selector import MemeDecision, load_recent_history, select_meme

logger = logging.getLogger(__name__)

_ROUTES_FILE = Path.home() / ".hermes" / "meme_reaction" / "routes.json"
_LAST_SENT_FILE = Path.home() / ".hermes" / "meme_reaction" / "last_sent.json"
_CTX = None


def _log(msg: str) -> None:
    try:
        with open("/tmp/meme-reaction-debug.log", "a") as f:
            f.write(f"{time.strftime('%H:%M:%S')} {msg}\n")
    except Exception:
        pass
    logger.debug("[meme-reaction] %s", msg)


def _load_routes() -> dict[str, dict[str, Any]]:
    try:
        if _ROUTES_FILE.is_file():
            data = json.loads(_ROUTES_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


def _save_routes(routes: dict[str, dict[str, Any]]) -> None:
    try:
        _ROUTES_FILE.parent.mkdir(parents=True, exist_ok=True)
        _ROUTES_FILE.write_text(json.dumps(routes, ensure_ascii=False), encoding="utf-8")
    except Exception:
        logger.debug("Failed to save routes file", exc_info=True)


def _load_last_sent() -> dict[str, float]:
    try:
        if _LAST_SENT_FILE.is_file():
            data = json.loads(_LAST_SENT_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return {k: float(v) for k, v in data.items()}
    except Exception:
        pass
    return {}


def _save_last_sent(last_sent: dict[str, float]) -> None:
    try:
        _LAST_SENT_FILE.parent.mkdir(parents=True, exist_ok=True)
        _LAST_SENT_FILE.write_text(json.dumps(last_sent, ensure_ascii=False), encoding="utf-8")
    except Exception:
        logger.debug("Failed to save last_sent file", exc_info=True)


def _platform_name(platform: Any) -> str:
    return str(getattr(platform, "value", platform) or "").lower()


def _target_from_route(route: dict[str, Any]) -> str | None:
    platform = str(route.get("platform") or "").lower()
    chat_id = str(route.get("chat_id") or "")
    thread_id = route.get("thread_id")
    if not platform or not chat_id:
        return None
    if thread_id is not None and str(thread_id):
        return f"{platform}:{chat_id}:{thread_id}"
    return f"{platform}:{chat_id}"


# ============================================================================
# pre_gateway_dispatch — route caching (persisted to file)
# ============================================================================

def _on_pre_gateway_dispatch(**kwargs: Any):
    _log("pre_gateway_dispatch")

    event = kwargs.get("event")
    session_store = kwargs.get("session_store")
    source = getattr(event, "source", None)
    if source is None:
        _log("  no source, skip")
        return None

    cfg = load_meme_reaction_config()
    platform = _platform_name(getattr(source, "platform", ""))
    if not cfg.enabled or not cfg.platform_allowed(platform):
        _log(f"  disabled or platform '{platform}' not allowed")
        return None

    key = _make_route_key(source, session_store)
    if not key:
        _log("  no route key")
        return None

    route = {
        "platform": platform,
        "chat_id": str(getattr(source, "chat_id", "") or ""),
        "thread_id": getattr(source, "thread_id", None),
        "user_id": str(getattr(source, "user_id", "") or ""),
        "user_name": str(getattr(source, "user_name", "") or ""),
        "timestamp": time.time(),
    }

    routes = _load_routes()
    routes[key] = route

    # Also store by session_id if available
    if session_store is not None:
        try:
            entry = session_store.get_or_create_session(source)
            sid = str(getattr(entry, "session_id", "") or "")
            if sid:
                routes[sid] = route
                _log(f"  also cached by session_id={sid[:30]}")
        except Exception:
            pass

    _save_routes(routes)
    _log(f"  cached route: key={key[:40]} platform={platform} chat={route['chat_id']}")
    return None


def _make_route_key(source: Any, session_store: Any = None) -> str:
    parts = [
        _platform_name(getattr(source, "platform", "")),
        str(getattr(source, "chat_id", "") or ""),
        str(getattr(source, "thread_id", "") or ""),
    ]
    return ":".join(parts)


# ============================================================================
# LLM decision — uses ctx.llm (host-owned, zero extra key/config)
# ============================================================================

def _build_decision_input(
    user_message: Any,
    assistant_response: str,
    history: list[dict[str, Any]],
) -> str:
    recent = []
    for msg in (history or [])[-6:]:
        role = msg.get("role")
        content = msg.get("content")
        if isinstance(content, list):
            content = "[multimodal]"
        if isinstance(content, str):
            recent.append({"role": role, "content": content[:400]})
    return json.dumps(
        {
            "user_message": str(user_message)[:800],
            "assistant_response": assistant_response[:800],
            "recent_context": recent,
            "instruction": "表情包是助手回复后的尾巴；必须同时贴合用户情绪、助手回复语气、二者关系。",
        },
        ensure_ascii=False,
    )


def _decide_with_llm(
    ctx: Any,
    cfg,
    *,
    user_message: Any,
    assistant_response: str,
    history: list[dict[str, Any]],
) -> MemeDecision | None:
    if not cfg.llm.enabled:
        return None
    _log("  asking ctx.llm for mood decision...")
    try:
        result = ctx.llm.complete_structured(
            instructions=MOOD_DECISION_INSTRUCTIONS,
            input=[{"type": "text", "text": _build_decision_input(user_message, assistant_response, history)}],
            json_schema=MOOD_DECISION_SCHEMA,
            json_mode=True,
            timeout=cfg.llm.timeout_seconds,
            max_tokens=500,
            temperature=0.2,
            purpose="meme_reaction_decision",
        )
        _log(f"  ctx.llm returned: type={type(result).__name__}")
        parsed = getattr(result, "parsed", None)
        if isinstance(parsed, dict):
            decision = MemeDecision.from_dict(parsed)
        else:
            text = getattr(result, "text", "") or ""
            if not text:
                _log("  ctx.llm: empty response")
                return None
            text = text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[-1].rsplit("\n```", 1)[0]
            decision = MemeDecision.from_dict(json.loads(text))
        _log(f"  decision: should_send={decision.should_send} score={decision.send_score:.2f} mood={decision.conversation_mood}")
        return decision
    except Exception as exc:
        _log(f"  ctx.llm error: {exc}")
        logger.debug("meme-reaction ctx.llm decision failed", exc_info=True)
        return None


# ============================================================================
# post_llm_call — the main pipeline
# ============================================================================

def _on_post_llm_call(**kwargs: Any):
    _log("post_llm_call")
    ctx = _CTX
    if ctx is None:
        _log("  no ctx")
        return None

    cfg = load_meme_reaction_config()
    if not cfg.enabled or cfg.trigger_weight <= 0:
        _log(f"  disabled or weight={cfg.trigger_weight}")
        return None

    session_id = str(kwargs.get("session_id") or "")
    platform = str(kwargs.get("platform") or "").lower()

    routes = _load_routes()

    # Try session_id first, then fallback to any recent route on same platform
    route = routes.get(session_id)
    if route is None:
        candidates = [
            r
            for r in routes.values()
            if (not platform or r.get("platform") == platform)
        ]
        route = max(candidates, key=lambda r: r.get("timestamp", 0), default=None)

    if route is None:
        _log(f"  no route found for session_id={session_id[:30]} platform={platform}")
        return None

    if time.time() - float(route.get("timestamp") or 0) > 600:
        _log("  route too old")
        return None

    route_platform = route.get("platform", "")
    if not cfg.platform_allowed(route_platform):
        _log(f"  platform '{route_platform}' not allowed")
        return None

    # Cooldown
    now = time.time()
    route_key = str(route.get("chat_id") or session_id)
    last_sent = _load_last_sent()
    if cfg.cooldown_seconds and now - last_sent.get(route_key, 0) < cfg.cooldown_seconds:
        _log(f"  cooldown active, {cfg.cooldown_seconds}s")
        return None

    index = MemeIndex.load(cfg.index_path)
    if not index.items:
        _log("  index empty")
        return None

    _log(f"  index has {len(index.existing_enabled())} enabled memes")

    decision = _decide_with_llm(
        ctx,
        cfg,
        user_message=kwargs.get("user_message"),
        assistant_response=str(kwargs.get("assistant_response") or ""),
        history=kwargs.get("conversation_history") or [],
    )
    if decision is None or not decision.passes(cfg):
        final = decision.final_score(cfg) if decision else 0
        _log(f"  decision: skip (final_score={final:.2f}, threshold={cfg.threshold})")
        return None

    recent = load_recent_history(cfg.history_path)
    item = select_meme(decision, index, cfg, recent=recent)
    if item is None:
        _log("  no matching meme")
        return None

    target = _target_from_route(route)
    if not target:
        _log("  no send target")
        return None

    _log(f"  sending {item.path.split('/')[-1]} via send_message to {target}")

    # Cross-platform: use send_message tool with MEDIA: prefix
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
        success = isinstance(result, dict) and result.get("success")

        if success:
            last_sent = _load_last_sent()
            last_sent[route_key] = now
            _save_last_sent(last_sent)
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
            _log(f"  SENT OK: {item.path.split('/')[-1]}")
        else:
            err = result.get("error", "") if isinstance(result, dict) else str(result)
            _log(f"  send failed: {err}")
    except Exception as exc:
        _log(f"  send exception: {exc}")
        logger.debug("meme-reaction send failed", exc_info=True)
    return None


def _append_history(path: Path, payload: dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        logger.debug("Failed to append meme reaction history", exc_info=True)


# ============================================================================
# Tools
# ============================================================================

def _tool_import(params: dict[str, Any], **kwargs: Any) -> str:
    del kwargs
    cfg = load_meme_reaction_config()
    path = params.get("path")
    if path:
        from .config import MemeLibraryConfig
        cfg.libraries = (
            MemeLibraryConfig(
                name="manual",
                path=Path(str(path)).expanduser(),
                recursive=bool(params.get("recursive", True)),
            ),
        )
    index = import_libraries(cfg)
    return json.dumps(
        {"success": True, "count": len(index.items), "index_path": str(cfg.index_path)},
        ensure_ascii=False,
    )


def _tool_search(params: dict[str, Any], **kwargs: Any) -> str:
    del kwargs
    cfg = load_meme_reaction_config()
    tags = [str(x).lower() for x in (params.get("tags") or [])]
    query = str(params.get("query") or "").lower()
    items = []
    for item in MemeIndex.load(cfg.index_path).existing_enabled():
        hay = " ".join(item.tags + item.moods + item.safe_for + [item.caption]).lower()
        if (tags and not any(tag in hay for tag in tags)) or (
            query and query not in hay
        ):
            continue
        items.append(
            {
                "id": item.id,
                "path": item.path,
                "caption": item.caption,
                "tags": item.tags,
                "moods": item.moods,
            }
        )
        if len(items) >= _as_int(params.get("limit"), 10, minimum=1):
            break
    return json.dumps({"success": True, "items": items}, ensure_ascii=False)


# ============================================================================
# Plugin register
# ============================================================================

def register(ctx) -> None:
    global _CTX
    _CTX = ctx
    _log("register")
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
                    "path": {
                        "type": "string",
                        "description": "Folder path to import.",
                    },
                    "recursive": {
                        "type": "boolean",
                        "description": "Scan recursively.",
                    },
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