"""LLM decision helpers for meme reactions."""

from __future__ import annotations

import json
import logging
from typing import Any

from .prompts import MOOD_DECISION_INSTRUCTIONS, MOOD_DECISION_SCHEMA
from .selector import MemeDecision


logger = logging.getLogger(__name__)


def build_decision_input(
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


def decide_with_llm(
    ctx: Any,
    cfg: Any,
    *,
    user_message: Any,
    assistant_response: str,
    history: list[dict[str, Any]],
) -> MemeDecision | None:
    if not cfg.llm.enabled:
        return None
    try:
        result = ctx.llm.complete_structured(
            instructions=MOOD_DECISION_INSTRUCTIONS,
            input=[{"type": "text", "text": build_decision_input(user_message, assistant_response, history)}],
            json_schema=MOOD_DECISION_SCHEMA,
            json_mode=True,
            timeout=cfg.llm.timeout_seconds,
            max_tokens=500,
            temperature=0.2,
            purpose="meme_reaction_decision",
        )
        parsed = getattr(result, "parsed", None)
        if isinstance(parsed, dict):
            return MemeDecision.from_dict(parsed)
        text = (getattr(result, "text", "") or "").strip()
        if not text:
            return None
        if text.startswith("```"):
            text = text.split("\n", 1)[-1].rsplit("\n```", 1)[0]
        return MemeDecision.from_dict(json.loads(text))
    except Exception:
        logger.debug("meme-reaction ctx.llm decision failed", exc_info=True)
        return None
