"""Hermes tool handlers for meme reaction indexing and search."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import MemeLibraryConfig, _as_int, load_meme_reaction_config
from .importer import import_libraries
from .index import MemeIndex


def handle_import(params: dict[str, Any], **kwargs: Any) -> str:
    del kwargs
    cfg = load_meme_reaction_config()
    path = params.get("path")
    if path:
        import_path = Path(str(path)).expanduser()
        if not cfg.import_path_allowed(import_path):
            return json.dumps({"success": False, "error": "path_not_allowed"}, ensure_ascii=False)
        cfg.libraries = (
            MemeLibraryConfig(
                name="manual",
                path=import_path,
                recursive=bool(params.get("recursive", True)),
            ),
        )
    index = import_libraries(cfg)
    return json.dumps(
        {"success": True, "count": len(index.items), "index_path": str(cfg.index_path)},
        ensure_ascii=False,
    )


def handle_search(params: dict[str, Any], **kwargs: Any) -> str:
    del kwargs
    cfg = load_meme_reaction_config()
    tags = [str(x).lower() for x in (params.get("tags") or [])]
    query = str(params.get("query") or "").lower()
    items = []
    for item in MemeIndex.load(cfg.index_path).existing_enabled():
        hay = " ".join(item.tags + item.moods + item.safe_for + [item.caption]).lower()
        if (tags and not any(tag in hay for tag in tags)) or (query and query not in hay):
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


def register_tools(ctx) -> None:
    ctx.register_tool(
        name="meme_import",
        toolset="meme_reaction",
        schema={
            "name": "meme_import",
            "description": "Import a local meme/sticker folder into the meme reaction index.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Folder path to import."},
                    "recursive": {"type": "boolean", "description": "Scan recursively."},
                },
            },
        },
        handler=handle_import,
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
        handler=handle_search,
        description="Search indexed meme/sticker metadata.",
    )
