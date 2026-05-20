import importlib.util
import json
from pathlib import Path
import sys
import time
import types
from types import SimpleNamespace
from unittest.mock import Mock

from meme_reaction.importer import import_libraries


def load_plugin():
    parent = "hermes_plugins"
    if parent not in sys.modules:
        pkg = types.ModuleType(parent)
        pkg.__path__ = []
        sys.modules[parent] = pkg
    module_name = "hermes_plugins.meme_reaction_test"
    sys.modules.pop(module_name, None)
    plugin_dir = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location(
        module_name,
        plugin_dir / "__init__.py",
        submodule_search_locations=[str(plugin_dir)],
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = module_name
    mod.__path__ = [str(plugin_dir)]
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


class FakeCtx:
    def __init__(self):
        self.hooks = {}
        self.tools = {}
        self.sent = []
        self.llm = SimpleNamespace(complete_structured=self.complete_structured)

    def register_hook(self, name, cb):
        self.hooks[name] = cb

    def register_tool(self, name, toolset, schema, handler, **kwargs):
        self.tools[name] = handler

    def dispatch_tool(self, name, args, **kwargs):
        self.sent.append((name, args))
        return json.dumps({"success": True})

    def complete_structured(self, **kwargs):
        return SimpleNamespace(parsed={
            "should_send": True,
            "send_score": 1.0,
            "conversation_mood": "轻松吐槽",
            "wanted_tags": ["吐槽"],
            "wanted_moods": ["playful"],
            "intensity": 0.4,
            "reason": "test",
        })


class SlowCtx(FakeCtx):
    def __init__(self):
        super().__init__()
        self.decision_calls = 0

    def complete_structured(self, **kwargs):
        self.decision_calls += 1
        time.sleep(0.2)
        return super().complete_structured(**kwargs)


def wait_until(predicate, timeout=1.0):
    deadline = time.perf_counter() + timeout
    while time.perf_counter() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


def test_plugin_registers_hooks_and_tools():
    mod = load_plugin()
    ctx = FakeCtx()
    mod.register(ctx)
    assert "pre_gateway_dispatch" in ctx.hooks
    assert "post_llm_call" in ctx.hooks
    assert "meme_import" in ctx.tools
    assert "meme_search" in ctx.tools


def test_plugin_captures_route_and_sends_media(tmp_path, monkeypatch):
    mod = load_plugin()
    impl = sys.modules[mod.register.__module__]

    meme = tmp_path / "吐槽_猫猫.webp"
    meme.write_bytes(b"x")
    index_path = tmp_path / "index.json"
    history_path = tmp_path / "history.jsonl"
    routes_path = tmp_path / "routes.json"
    last_sent_path = tmp_path / "last_sent.json"

    cfg = impl.load_meme_reaction_config({
        "meme_reaction": {
            "enabled": True,
            "trigger_weight": 1,
            "threshold": 0.1,
            "cooldown_seconds": 0,
            "routes_path": str(routes_path),
            "last_sent_path": str(last_sent_path),
            "index_path": str(index_path),
            "history_path": str(history_path),
            "libraries": [{"name": "t", "path": str(tmp_path), "recursive": False}],
            "import": {"use_vision": False},
        }
    })
    import_libraries(cfg)
    monkeypatch.setattr(impl, "load_meme_reaction_config", lambda: cfg)

    ctx = FakeCtx()
    mod.register(ctx)
    source = SimpleNamespace(platform="telegram", chat_id="-100", thread_id="42", user_id="u", user_name="U")
    event = SimpleNamespace(source=source, text="继续")
    entry = SimpleNamespace(session_id="sid", session_key="sk")
    store = SimpleNamespace(get_or_create_session=Mock(return_value=entry))

    ctx.hooks["pre_gateway_dispatch"](event=event, session_store=store)
    ctx.hooks["post_llm_call"](
        session_id="sid",
        user_message="继续",
        assistant_response="完成啦",
        conversation_history=[],
        platform="telegram",
    )
    assert wait_until(lambda: bool(ctx.sent))
    assert ctx.sent[0][0] == "send_message"
    assert ctx.sent[0][1]["target"] == "telegram:-100:42"
    assert ctx.sent[0][1]["message"].startswith("MEDIA:")
    assert routes_path.exists()
    assert wait_until(lambda: last_sent_path.exists())


def test_post_llm_call_without_exact_session_route_does_not_send(tmp_path, monkeypatch):
    mod = load_plugin()
    impl = sys.modules[mod.register.__module__]

    meme = tmp_path / "吐槽_猫猫.webp"
    meme.write_bytes(b"x")
    cfg = impl.load_meme_reaction_config({
        "meme_reaction": {
            "enabled": True,
            "trigger_weight": 1,
            "threshold": 0.1,
            "cooldown_seconds": 0,
            "routes_path": str(tmp_path / "routes.json"),
            "last_sent_path": str(tmp_path / "last_sent.json"),
            "index_path": str(tmp_path / "index.json"),
            "history_path": str(tmp_path / "history.jsonl"),
            "libraries": [{"name": "t", "path": str(tmp_path), "recursive": False}],
            "import": {"use_vision": False},
        }
    })
    import_libraries(cfg)
    monkeypatch.setattr(impl, "load_meme_reaction_config", lambda: cfg)

    ctx = FakeCtx()
    mod.register(ctx)
    ctx.hooks["post_llm_call"](
        session_id="missing",
        user_message="继续",
        assistant_response="完成啦",
        conversation_history=[],
        platform="telegram",
    )

    assert ctx.sent == []


def test_dry_run_records_history_without_dispatch(tmp_path, monkeypatch):
    mod = load_plugin()
    impl = sys.modules[mod.register.__module__]

    meme = tmp_path / "吐槽_猫猫.webp"
    meme.write_bytes(b"x")
    history_path = tmp_path / "history.jsonl"
    cfg = impl.load_meme_reaction_config({
        "meme_reaction": {
            "enabled": True,
            "dry_run": True,
            "trigger_weight": 1,
            "threshold": 0.1,
            "cooldown_seconds": 0,
            "routes_path": str(tmp_path / "routes.json"),
            "last_sent_path": str(tmp_path / "last_sent.json"),
            "index_path": str(tmp_path / "index.json"),
            "history_path": str(history_path),
            "libraries": [{"name": "t", "path": str(tmp_path), "recursive": False}],
            "import": {"use_vision": False},
        }
    })
    import_libraries(cfg)
    monkeypatch.setattr(impl, "load_meme_reaction_config", lambda: cfg)

    ctx = FakeCtx()
    mod.register(ctx)
    source = SimpleNamespace(platform="telegram", chat_id="-100", thread_id="42", user_id="u", user_name="U")
    event = SimpleNamespace(source=source, text="继续")
    entry = SimpleNamespace(session_id="sid", session_key="sk")
    store = SimpleNamespace(get_or_create_session=Mock(return_value=entry))

    ctx.hooks["pre_gateway_dispatch"](event=event, session_store=store)
    ctx.hooks["post_llm_call"](
        session_id="sid",
        user_message="继续",
        assistant_response="完成啦",
        conversation_history=[],
        platform="telegram",
    )

    assert ctx.sent == []
    assert wait_until(lambda: history_path.exists())
    assert '"dry_run": true' in history_path.read_text(encoding="utf-8")


def test_post_llm_call_returns_before_slow_decision_finishes(tmp_path, monkeypatch):
    mod = load_plugin()
    impl = sys.modules[mod.register.__module__]

    meme = tmp_path / "吐槽_猫猫.webp"
    meme.write_bytes(b"x")
    cfg = impl.load_meme_reaction_config({
        "meme_reaction": {
            "enabled": True,
            "trigger_weight": 1,
            "threshold": 0.1,
            "cooldown_seconds": 0,
            "routes_path": str(tmp_path / "routes.json"),
            "last_sent_path": str(tmp_path / "last_sent.json"),
            "index_path": str(tmp_path / "index.json"),
            "history_path": str(tmp_path / "history.jsonl"),
            "libraries": [{"name": "t", "path": str(tmp_path), "recursive": False}],
            "import": {"use_vision": False},
        }
    })
    import_libraries(cfg)
    monkeypatch.setattr(impl, "load_meme_reaction_config", lambda: cfg)

    ctx = SlowCtx()
    mod.register(ctx)
    source = SimpleNamespace(platform="telegram", chat_id="-100", thread_id="42", user_id="u", user_name="U")
    event = SimpleNamespace(source=source, text="继续")
    entry = SimpleNamespace(session_id="sid", session_key="sk")
    store = SimpleNamespace(get_or_create_session=Mock(return_value=entry))

    ctx.hooks["pre_gateway_dispatch"](event=event, session_store=store)
    started = time.perf_counter()
    ctx.hooks["post_llm_call"](
        session_id="sid",
        user_message="继续",
        assistant_response="完成啦",
        conversation_history=[],
        platform="telegram",
    )

    assert time.perf_counter() - started < 0.1
    assert wait_until(lambda: bool(ctx.sent))


def test_post_llm_call_does_not_queue_duplicate_pending_reactions(tmp_path, monkeypatch):
    mod = load_plugin()
    impl = sys.modules[mod.register.__module__]

    meme = tmp_path / "吐槽_猫猫.webp"
    meme.write_bytes(b"x")
    cfg = impl.load_meme_reaction_config({
        "meme_reaction": {
            "enabled": True,
            "trigger_weight": 1,
            "threshold": 0.1,
            "cooldown_seconds": 0,
            "routes_path": str(tmp_path / "routes.json"),
            "last_sent_path": str(tmp_path / "last_sent.json"),
            "index_path": str(tmp_path / "index.json"),
            "history_path": str(tmp_path / "history.jsonl"),
            "libraries": [{"name": "t", "path": str(tmp_path), "recursive": False}],
            "import": {"use_vision": False},
        }
    })
    import_libraries(cfg)
    monkeypatch.setattr(impl, "load_meme_reaction_config", lambda: cfg)

    ctx = SlowCtx()
    mod.register(ctx)
    source = SimpleNamespace(platform="telegram", chat_id="-100", thread_id="42", user_id="u", user_name="U")
    event = SimpleNamespace(source=source, text="继续")
    entry = SimpleNamespace(session_id="sid", session_key="sk")
    store = SimpleNamespace(get_or_create_session=Mock(return_value=entry))

    ctx.hooks["pre_gateway_dispatch"](event=event, session_store=store)
    for _ in range(3):
        ctx.hooks["post_llm_call"](
            session_id="sid",
            user_message="继续",
            assistant_response="完成啦",
            conversation_history=[],
            platform="telegram",
        )

    assert wait_until(lambda: bool(ctx.sent))
    assert len(ctx.sent) == 1
    assert ctx.decision_calls == 1
