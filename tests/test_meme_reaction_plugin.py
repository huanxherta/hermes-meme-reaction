import importlib.util
import json
import sys
import types
from types import SimpleNamespace
from unittest.mock import Mock


def load_plugin():
    parent = "hermes_plugins"
    if parent not in sys.modules:
        pkg = types.ModuleType(parent)
        pkg.__path__ = []
        sys.modules[parent] = pkg
    module_name = "hermes_plugins.meme_reaction_test"
    sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(
        module_name,
        "plugins/meme-reaction/__init__.py",
        submodule_search_locations=["plugins/meme-reaction"],
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = module_name
    mod.__path__ = ["plugins/meme-reaction"]
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
    ctx = FakeCtx()
    mod.register(ctx)

    meme = tmp_path / "吐槽_猫猫.webp"
    meme.write_bytes(b"x")
    index_path = tmp_path / "index.json"
    history_path = tmp_path / "history.jsonl"

    cfg = mod.load_meme_reaction_config({
        "meme_reaction": {
            "enabled": True,
            "trigger_weight": 1,
            "threshold": 0.1,
            "cooldown_seconds": 0,
            "index_path": str(index_path),
            "history_path": str(history_path),
            "libraries": [{"name": "t", "path": str(tmp_path), "recursive": False}],
            "import": {"use_vision": False},
        }
    })
    mod.import_libraries(cfg)
    monkeypatch.setattr(mod, "load_meme_reaction_config", lambda: cfg)

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
    assert ctx.sent
    assert ctx.sent[0][0] == "send_message"
    assert ctx.sent[0][1]["target"] == "telegram:-100:42"
    assert ctx.sent[0][1]["message"].startswith("MEDIA:")
