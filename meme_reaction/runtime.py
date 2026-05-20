"""Runtime hook orchestration for the meme reaction plugin."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import logging
import time
from threading import Lock
from typing import Any, Callable

from .config import MemeReactionConfig, load_meme_reaction_config
from .decision import decide_with_llm
from .index import MemeIndex
from .routes import RouteStore, make_route_key, platform_name, route_from_source
from .sender import send_meme
from .selector import load_recent_history, select_meme
from .state import JsonState, append_jsonl, debug_log, load_float_map


logger = logging.getLogger(__name__)


class MemeReactionRuntime:
    def __init__(
        self,
        ctx: Any,
        config_loader: Callable[[], MemeReactionConfig] = load_meme_reaction_config,
        executor: ThreadPoolExecutor | None = None,
    ):
        self.ctx = ctx
        self.config_loader = config_loader
        self.executor = executor or ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="meme-reaction",
        )
        self._pending_lock = Lock()
        self._pending_reactions: set[str] = set()

    def on_pre_gateway_dispatch(self, **kwargs: Any):
        event = kwargs.get("event")
        session_store = kwargs.get("session_store")
        source = getattr(event, "source", None)
        if source is None:
            return None

        cfg = self.config_loader()
        debug_log(cfg, "pre_gateway_dispatch")
        platform = platform_name(getattr(source, "platform", ""))
        if not cfg.enabled or not cfg.platform_allowed(platform):
            return None

        route = route_from_source(source, time.time())
        if route is None:
            return None

        session_id = ""
        if session_store is not None:
            try:
                entry = session_store.get_or_create_session(source)
                session_id = str(getattr(entry, "session_id", "") or "")
            except Exception:
                logger.debug("Failed to resolve Hermes session for meme route", exc_info=True)

        RouteStore(JsonState(cfg.routes_path)).save(make_route_key(source), route, session_id=session_id)
        return None

    def on_post_llm_call(self, **kwargs: Any):
        cfg = self.config_loader()
        debug_log(cfg, "post_llm_call")
        if not cfg.enabled or cfg.trigger_weight <= 0:
            return None

        session_id = str(kwargs.get("session_id") or "")
        route = RouteStore(JsonState(cfg.routes_path)).find_exact(session_id)
        if route is None:
            logger.debug("meme-reaction skipped: no exact route for session_id=%s", session_id[:30])
            return None

        if time.time() - float(route.timestamp or 0) > 600:
            return None
        if not cfg.platform_allowed(route.platform):
            return None

        now = time.time()
        route_key = str(route.chat_id or session_id)
        last_sent = load_float_map(cfg.last_sent_path)
        if cfg.cooldown_seconds and now - last_sent.get(route_key, 0) < cfg.cooldown_seconds:
            return None

        payload = {
            "user_message": kwargs.get("user_message"),
            "assistant_response": str(kwargs.get("assistant_response") or ""),
            "conversation_history": list(kwargs.get("conversation_history") or []),
        }
        with self._pending_lock:
            if route_key in self._pending_reactions:
                return None
            self._pending_reactions.add(route_key)
        self.executor.submit(self._run_reaction_task, cfg, route, route_key, now, payload)
        return None

    def _run_reaction_task(
        self,
        cfg: MemeReactionConfig,
        route: Any,
        route_key: str,
        started_at: float,
        payload: dict[str, Any],
    ) -> None:
        try:
            self._run_reaction_task_inner(cfg, route, route_key, started_at, payload)
        except Exception:
            logger.debug("meme-reaction background task failed", exc_info=True)
        finally:
            with self._pending_lock:
                self._pending_reactions.discard(route_key)

    def _run_reaction_task_inner(
        self,
        cfg: MemeReactionConfig,
        route: Any,
        route_key: str,
        started_at: float,
        payload: dict[str, Any],
    ) -> None:
        index = MemeIndex.load(cfg.index_path)
        if not index.items:
            return None

        decision = decide_with_llm(
            self.ctx,
            cfg,
            user_message=payload.get("user_message"),
            assistant_response=str(payload.get("assistant_response") or ""),
            history=payload.get("conversation_history") or [],
        )
        if decision is None or not decision.passes(cfg):
            return None

        item = select_meme(decision, index, cfg, recent=load_recent_history(cfg.history_path))
        if item is None:
            return None

        result = send_meme(self.ctx, cfg, route, item)
        if not result.success:
            logger.debug("meme-reaction send skipped or failed: %s", result.error)
            return None

        if not result.dry_run:
            current_last_sent = load_float_map(cfg.last_sent_path)
            current_last_sent[route_key] = started_at
            JsonState(cfg.last_sent_path).save_dict(current_last_sent)

        append_jsonl(
            cfg.history_path,
            {
                "ts": started_at,
                "id": item.id,
                "path": item.path,
                "tags": item.tags,
                "moods": item.moods,
                "target": result.target,
                "dry_run": result.dry_run,
                "decision": {
                    "score": decision.send_score,
                    "final_score": decision.final_score(cfg),
                    "reason": decision.reason,
                },
            },
        )
        return None
