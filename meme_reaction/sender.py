"""Meme sending through Hermes tools."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .routes import Route


@dataclass(slots=True, frozen=True)
class SendResult:
    success: bool
    target: str
    dry_run: bool = False
    error: str = ""


def target_from_route(route: Route) -> str:
    if route.thread_id is not None and str(route.thread_id):
        return f"{route.platform}:{route.chat_id}:{route.thread_id}"
    return f"{route.platform}:{route.chat_id}"


def send_meme(ctx: Any, cfg: Any, route: Route, item: Any) -> SendResult:
    target = target_from_route(route)
    if not cfg.target_allowed(target):
        return SendResult(success=False, target=target, error="target_denied")
    if cfg.dry_run:
        return SendResult(success=True, target=target, dry_run=True)
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
            return SendResult(success=True, target=target)
        error = result.get("error", "") if isinstance(result, dict) else str(result)
        return SendResult(success=False, target=target, error=error or "send_failed")
    except Exception as exc:
        return SendResult(success=False, target=target, error=str(exc) or "send_exception")
