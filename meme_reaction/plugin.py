"""Hermes plugin registration."""

from __future__ import annotations

from .config import load_meme_reaction_config
from .runtime import MemeReactionRuntime
from .tools import register_tools


def register(ctx) -> None:
    runtime = MemeReactionRuntime(ctx, config_loader=load_meme_reaction_config)
    ctx.register_hook("pre_gateway_dispatch", runtime.on_pre_gateway_dispatch)
    ctx.register_hook("post_llm_call", runtime.on_post_llm_call)
    register_tools(ctx)
