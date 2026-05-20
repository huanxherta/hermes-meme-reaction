# Hermes Meme Reaction Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the Hermes meme reaction plugin into safer, smaller modules while keeping it easy to configure and never modifying Hermes core.

**Architecture:** Keep the root plugin entrypoint thin and move runtime behavior into focused modules for config, routes, state, decision, sending, tools, and hook orchestration. Remove route fallback behavior so sends require an exact session route, while empty allow/deny restrictions remain unrestricted for usability.

**Tech Stack:** Python 3.11+, Hermes plugin API (`register(ctx)`, hooks, tools, `ctx.llm`, `ctx.dispatch_tool`), pytest via `uv run --with pytest pytest`.

---

## Non-Negotiable Boundary

- Do not modify `~/.hermes/hermes-agent/**`.
- Do not run `hermes plugins enable`, `hermes plugins disable`, or any command that edits Hermes configuration.
- Do not edit `~/.hermes/config.yaml`.
- Only edit files under `/home/huanx/code/hermes-meme-reaction`.
- Do not delete or revert user changes. Inspect `git status --short` before each task.

## File Structure

- Modify `__init__.py`: keep it as a compatibility entrypoint exporting `register`.
- Create `meme_reaction/plugin.py`: `register(ctx)` and only registration wiring.
- Create `meme_reaction/runtime.py`: hook orchestration for pre-dispatch and post-LLM flows.
- Create `meme_reaction/routes.py`: route model, route key creation, exact route lookup.
- Create `meme_reaction/state.py`: JSON state persistence, cooldown storage, history append, optional file debug logging.
- Create `meme_reaction/decision.py`: LLM decision input and structured response parsing.
- Create `meme_reaction/sender.py`: target formatting, target allow/deny checks, dry-run and send dispatch.
- Create `meme_reaction/tools.py`: `meme_import` and `meme_search` handlers.
- Modify `meme_reaction/config.py`: add state paths, debug, dry-run, targets, import roots, and empty-means-unrestricted semantics.
- Keep `meme_reaction/index.py`, `meme_reaction/importer.py`, `meme_reaction/selector.py`, and `meme_reaction/prompts.py` focused on their current responsibilities.
- Modify tests under `tests/` to exercise the new module boundaries and safety behavior.
- Modify `README.md` after code behavior is verified.

### Task 1: Config Model and Empty-Means-Unrestricted Semantics

**Files:**
- Modify: `meme_reaction/config.py`
- Modify: `tests/test_meme_reaction_config.py`

- [ ] **Step 1: Write failing config tests**

Add these tests to `tests/test_meme_reaction_config.py`:

```python
def test_empty_restrictions_are_unrestricted(tmp_path):
    cfg = load_meme_reaction_config({
        "meme_reaction": {
            "platforms": {"allowed": [], "denied": []},
            "targets": {"allowed": [], "denied": []},
            "import": {"allowed_roots": []},
            "libraries": [{"name": "x", "path": str(tmp_path), "recursive": False}],
        }
    })
    assert cfg.platform_allowed("telegram") is True
    assert cfg.target_allowed("telegram:-100:42") is True
    assert cfg.import_path_allowed(tmp_path / "anywhere") is True


def test_target_deny_overrides_allow(tmp_path):
    cfg = load_meme_reaction_config({
        "meme_reaction": {
            "targets": {
                "allowed": ["telegram:-100"],
                "denied": ["telegram:-100:42"],
            },
            "libraries": [{"name": "x", "path": str(tmp_path), "recursive": False}],
        }
    })
    assert cfg.target_allowed("telegram:-100") is True
    assert cfg.target_allowed("telegram:-100:42") is False


def test_runtime_defaults_are_safe_and_file_debug_is_off():
    cfg = load_meme_reaction_config({})
    assert cfg.enabled is False
    assert cfg.dry_run is False
    assert cfg.debug_file_enabled is False
```

- [ ] **Step 2: Run config tests and verify failure**

Run: `uv run --with pytest pytest tests/test_meme_reaction_config.py -q`

Expected before implementation: FAIL with missing attributes such as `target_allowed`, `import_path_allowed`, `dry_run`, or `debug_file_enabled`.

- [ ] **Step 3: Implement config dataclasses and helpers**

In `meme_reaction/config.py`, add these dataclasses and methods:

```python
@dataclass(slots=True)
class MemeTargetsConfig:
    allowed: tuple[str, ...] = ()
    denied: tuple[str, ...] = ()


@dataclass(slots=True)
class MemeDebugConfig:
    file_enabled: bool = False
    path: Path = field(default_factory=lambda: get_hermes_home() / "meme_reaction" / "debug.log")
```

Extend `MemeImportConfig`:

```python
allowed_roots: tuple[Path, ...] = ()
```

Extend `MemeReactionConfig`:

```python
dry_run: bool = False
routes_path: Path = field(default_factory=lambda: get_hermes_home() / "meme_reaction" / "routes.json")
last_sent_path: Path = field(default_factory=lambda: get_hermes_home() / "meme_reaction" / "last_sent.json")
targets: MemeTargetsConfig = field(default_factory=MemeTargetsConfig)
debug: MemeDebugConfig = field(default_factory=MemeDebugConfig)
```

Add these methods to `MemeReactionConfig`:

```python
@property
def debug_file_enabled(self) -> bool:
    return self.debug.file_enabled


def target_allowed(self, target: Any) -> bool:
    normalized = str(target or "").lower()
    if not normalized:
        return False
    if normalized in self.targets.denied:
        return False
    if self.targets.allowed and normalized not in self.targets.allowed:
        return False
    return True


def import_path_allowed(self, path: str | Path) -> bool:
    if not self.import_config.allowed_roots:
        return True
    candidate = Path(path).expanduser().resolve()
    for root in self.import_config.allowed_roots:
        try:
            candidate.relative_to(root.expanduser().resolve())
            return True
        except ValueError:
            continue
    return False
```

Parse config keys in `load_meme_reaction_config`:

```python
targets_raw = raw.get("targets", {}) if isinstance(raw.get("targets", {}), dict) else {}
debug_raw = raw.get("debug", {}) if isinstance(raw.get("debug", {}), dict) else {}
allowed_roots_raw = import_raw.get("allowed_roots") or []
if not isinstance(allowed_roots_raw, (list, tuple)):
    allowed_roots_raw = []
allowed_roots = tuple(_expand_path(str(x), str(home / "memes")) for x in allowed_roots_raw)
```

Set constructor fields:

```python
dry_run=bool(raw.get("dry_run", False)),
routes_path=_expand_path(raw.get("routes_path"), str(home / "meme_reaction" / "routes.json")),
last_sent_path=_expand_path(raw.get("last_sent_path"), str(home / "meme_reaction" / "last_sent.json")),
targets=MemeTargetsConfig(
    allowed=tuple(str(x).lower() for x in targets_raw.get("allowed", []) if str(x).strip()),
    denied=tuple(str(x).lower() for x in targets_raw.get("denied", []) if str(x).strip()),
),
debug=MemeDebugConfig(
    file_enabled=bool(debug_raw.get("file_enabled", raw.get("debug_file_enabled", False))),
    path=_expand_path(debug_raw.get("path"), str(home / "meme_reaction" / "debug.log")),
),
```

Set `allowed_roots=allowed_roots` in `MemeImportConfig`.

- [ ] **Step 4: Run config tests and verify pass**

Run: `uv run --with pytest pytest tests/test_meme_reaction_config.py -q`

Expected: all config tests pass.

- [ ] **Step 5: Commit config changes**

```bash
git add meme_reaction/config.py tests/test_meme_reaction_config.py
git commit -m "refactor: add meme reaction runtime config"
```

### Task 2: State and Route Modules with Exact Lookup

**Files:**
- Create: `meme_reaction/state.py`
- Create: `meme_reaction/routes.py`
- Create: `tests/test_meme_reaction_routes.py`

- [ ] **Step 1: Write failing state and route tests**

Create `tests/test_meme_reaction_routes.py`:

```python
from types import SimpleNamespace

from meme_reaction.routes import Route, RouteStore, make_route_key
from meme_reaction.state import JsonState


def test_route_store_finds_exact_session_route(tmp_path):
    store = RouteStore(JsonState(tmp_path / "routes.json"))
    route = Route(
        platform="telegram",
        chat_id="-100",
        thread_id="42",
        user_id="u",
        user_name="U",
        timestamp=123.0,
    )
    store.save("telegram:-100:42", route, session_id="sid")

    assert store.find_exact("sid") == route
    assert store.find_exact("missing") is None


def test_make_route_key_uses_platform_chat_and_thread():
    source = SimpleNamespace(platform="Telegram", chat_id="-100", thread_id="42")
    assert make_route_key(source) == "telegram:-100:42"
```

- [ ] **Step 2: Run route tests and verify failure**

Run: `uv run --with pytest pytest tests/test_meme_reaction_routes.py -q`

Expected before implementation: FAIL because `meme_reaction.routes` and `meme_reaction.state` do not exist.

- [ ] **Step 3: Implement JSON state persistence**

Create `meme_reaction/state.py`:

```python
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any


logger = logging.getLogger(__name__)


class JsonState:
    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser()

    def load_dict(self) -> dict[str, Any]:
        try:
            if self.path.is_file():
                data = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return data
        except Exception:
            logger.debug("Failed to load JSON state from %s", self.path, exc_info=True)
        return {}

    def save_dict(self, data: dict[str, Any]) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        except Exception:
            logger.debug("Failed to save JSON state to %s", self.path, exc_info=True)


def append_jsonl(path: str | Path, payload: dict[str, Any]) -> None:
    p = Path(path).expanduser()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        logger.debug("Failed to append JSONL to %s", p, exc_info=True)


def load_float_map(path: str | Path) -> dict[str, float]:
    raw = JsonState(path).load_dict()
    out: dict[str, float] = {}
    for key, value in raw.items():
        try:
            out[str(key)] = float(value)
        except (TypeError, ValueError):
            continue
    return out
```

- [ ] **Step 4: Implement route model and exact store**

Create `meme_reaction/routes.py`:

```python
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .state import JsonState


@dataclass(slots=True, frozen=True)
class Route:
    platform: str
    chat_id: str
    thread_id: Any = None
    user_id: str = ""
    user_name: str = ""
    timestamp: float = 0.0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Route | None":
        platform = str(data.get("platform") or "").lower()
        chat_id = str(data.get("chat_id") or "")
        if not platform or not chat_id:
            return None
        return cls(
            platform=platform,
            chat_id=chat_id,
            thread_id=data.get("thread_id"),
            user_id=str(data.get("user_id") or ""),
            user_name=str(data.get("user_name") or ""),
            timestamp=float(data.get("timestamp") or 0.0),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def platform_name(platform: Any) -> str:
    return str(getattr(platform, "value", platform) or "").lower()


def make_route_key(source: Any) -> str:
    return ":".join([
        platform_name(getattr(source, "platform", "")),
        str(getattr(source, "chat_id", "") or ""),
        str(getattr(source, "thread_id", "") or ""),
    ])


def route_from_source(source: Any, timestamp: float) -> Route | None:
    platform = platform_name(getattr(source, "platform", ""))
    chat_id = str(getattr(source, "chat_id", "") or "")
    if not platform or not chat_id:
        return None
    return Route(
        platform=platform,
        chat_id=chat_id,
        thread_id=getattr(source, "thread_id", None),
        user_id=str(getattr(source, "user_id", "") or ""),
        user_name=str(getattr(source, "user_name", "") or ""),
        timestamp=timestamp,
    )


class RouteStore:
    def __init__(self, state: JsonState):
        self.state = state

    def save(self, route_key: str, route: Route, *, session_id: str = "") -> None:
        data = self.state.load_dict()
        payload = route.to_dict()
        data[route_key] = payload
        if session_id:
            data[session_id] = payload
        self.state.save_dict(data)

    def find_exact(self, session_id: str) -> Route | None:
        if not session_id:
            return None
        raw = self.state.load_dict().get(session_id)
        if not isinstance(raw, dict):
            return None
        return Route.from_dict(raw)
```

- [ ] **Step 5: Run route tests and verify pass**

Run: `uv run --with pytest pytest tests/test_meme_reaction_routes.py -q`

Expected: route tests pass.

- [ ] **Step 6: Commit route/state modules**

```bash
git add meme_reaction/state.py meme_reaction/routes.py tests/test_meme_reaction_routes.py
git commit -m "refactor: add exact route state store"
```

### Task 3: Decision and Sender Modules

**Files:**
- Create: `meme_reaction/decision.py`
- Create: `meme_reaction/sender.py`
- Create: `tests/test_meme_reaction_sender.py`

- [ ] **Step 1: Write failing sender tests**

Create `tests/test_meme_reaction_sender.py`:

```python
from dataclasses import dataclass

from meme_reaction.config import load_meme_reaction_config
from meme_reaction.routes import Route
from meme_reaction.sender import SendResult, send_meme


@dataclass
class Item:
    id: str = "m1"
    path: str = "/tmp/cat.webp"
    tags: list[str] = None
    moods: list[str] = None

    def __post_init__(self):
        self.tags = self.tags or ["cat"]
        self.moods = self.moods or ["playful"]


class FakeCtx:
    def __init__(self):
        self.sent = []

    def dispatch_tool(self, name, args, **kwargs):
        self.sent.append((name, args))
        return {"success": True}


def test_send_meme_dry_run_does_not_dispatch():
    cfg = load_meme_reaction_config({"meme_reaction": {"dry_run": True}})
    ctx = FakeCtx()
    route = Route(platform="telegram", chat_id="-100", thread_id="42")

    result = send_meme(ctx, cfg, route, Item())

    assert result == SendResult(success=True, target="telegram:-100:42", dry_run=True, error="")
    assert ctx.sent == []


def test_send_meme_blocks_denied_target():
    cfg = load_meme_reaction_config({
        "meme_reaction": {"targets": {"denied": ["telegram:-100:42"]}}
    })
    ctx = FakeCtx()
    route = Route(platform="telegram", chat_id="-100", thread_id="42")

    result = send_meme(ctx, cfg, route, Item())

    assert result.success is False
    assert result.error == "target_denied"
    assert ctx.sent == []
```

- [ ] **Step 2: Run sender tests and verify failure**

Run: `uv run --with pytest pytest tests/test_meme_reaction_sender.py -q`

Expected before implementation: FAIL because `meme_reaction.sender` does not exist.

- [ ] **Step 3: Move LLM decision helpers into `decision.py`**

Create `meme_reaction/decision.py` with the existing logic from `meme_reaction/__init__.py`:

```python
from __future__ import annotations

import json
import logging
from typing import Any

from .prompts import MOOD_DECISION_INSTRUCTIONS, MOOD_DECISION_SCHEMA
from .selector import MemeDecision


logger = logging.getLogger(__name__)


def build_decision_input(user_message: Any, assistant_response: str, history: list[dict[str, Any]]) -> str:
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


def decide_with_llm(ctx: Any, cfg: Any, *, user_message: Any, assistant_response: str, history: list[dict[str, Any]]) -> MemeDecision | None:
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
```

- [ ] **Step 4: Implement sender module**

Create `meme_reaction/sender.py`:

```python
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
```

- [ ] **Step 5: Run sender tests and verify pass**

Run: `uv run --with pytest pytest tests/test_meme_reaction_sender.py -q`

Expected: sender tests pass.

- [ ] **Step 6: Commit decision/sender modules**

```bash
git add meme_reaction/decision.py meme_reaction/sender.py tests/test_meme_reaction_sender.py
git commit -m "refactor: add decision and sender services"
```

### Task 4: Tool Module Cleanup and Import Behavior

**Files:**
- Create: `meme_reaction/tools.py`
- Create: `tests/test_meme_reaction_tools.py`

- [ ] **Step 1: Write failing tool tests**

Create `tests/test_meme_reaction_tools.py`:

```python
import json

from meme_reaction.config import load_meme_reaction_config
from meme_reaction.tools import handle_import


def test_import_tool_unrestricted_empty_roots_allows_path(tmp_path, monkeypatch):
    meme = tmp_path / "开心_猫猫.webp"
    meme.write_bytes(b"x")
    cfg = load_meme_reaction_config({
        "meme_reaction": {
            "index_path": str(tmp_path / "index.json"),
            "libraries": [{"name": "default", "path": str(tmp_path), "recursive": False}],
            "import": {"use_vision": False, "allowed_roots": []},
        }
    })
    monkeypatch.setattr("meme_reaction.tools.load_meme_reaction_config", lambda: cfg)

    result = json.loads(handle_import({"path": str(tmp_path), "recursive": False}))

    assert result["success"] is True
    assert result["count"] == 1


def test_import_tool_returns_error_for_disallowed_path(tmp_path, monkeypatch):
    allowed = tmp_path / "allowed"
    blocked = tmp_path / "blocked"
    allowed.mkdir()
    blocked.mkdir()
    cfg = load_meme_reaction_config({
        "meme_reaction": {
            "index_path": str(tmp_path / "index.json"),
            "libraries": [{"name": "default", "path": str(allowed), "recursive": False}],
            "import": {"allowed_roots": [str(allowed)]},
        }
    })
    monkeypatch.setattr("meme_reaction.tools.load_meme_reaction_config", lambda: cfg)

    result = json.loads(handle_import({"path": str(blocked), "recursive": False}))

    assert result["success"] is False
    assert result["error"] == "path_not_allowed"
```

- [ ] **Step 2: Run tool tests and verify failure**

Run: `uv run --with pytest pytest tests/test_meme_reaction_tools.py -q`

Expected before cleanup: FAIL because `handle_import` is not implemented in `meme_reaction.tools`.

- [ ] **Step 3: Move tool handlers into `tools.py`**

Replace `meme_reaction/tools.py` with:

```python
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
```

- [ ] **Step 4: Remove old tool code from `meme_reaction/__init__.py`**

Confirm `meme_reaction/__init__.py` contains only:

```python
from .plugin import register

__all__ = ["register"]
```

- [ ] **Step 5: Run tool and plugin tests**

Run: `uv run --with pytest pytest tests/test_meme_reaction_tools.py tests/test_meme_reaction_plugin.py -q`

Expected: tool and plugin tests pass.

- [ ] **Step 6: Commit tool module**

```bash
git add meme_reaction/tools.py tests/test_meme_reaction_tools.py
git commit -m "refactor: isolate meme reaction tools"
```

### Task 5: Runtime Hooks and Thin Plugin Entry

**Files:**
- Create: `meme_reaction/runtime.py`
- Create: `meme_reaction/plugin.py`
- Modify: `meme_reaction/__init__.py`
- Modify: `__init__.py`
- Modify: `tests/test_meme_reaction_plugin.py`

- [ ] **Step 1: Write failing plugin behavior tests**

Update `tests/test_meme_reaction_plugin.py` so plugin config is patched before registration:

```python
from meme_reaction.importer import import_libraries
```

Add these tests:

```python
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
    assert '"dry_run": true' in history_path.read_text(encoding="utf-8")
```

- [ ] **Step 2: Run plugin tests and verify failure**

Run: `uv run --with pytest pytest tests/test_meme_reaction_plugin.py -q`

Expected before runtime refactor: first new test fails because current code may fall back to a recent route; second test fails because dry-run is not wired into runtime.

- [ ] **Step 3: Implement runtime hooks**

Create `meme_reaction/runtime.py`:

```python
from __future__ import annotations

import logging
import time
from typing import Any, Callable

from .config import MemeReactionConfig, load_meme_reaction_config
from .decision import decide_with_llm
from .index import MemeIndex
from .routes import RouteStore, make_route_key, platform_name, route_from_source
from .sender import send_meme
from .selector import load_recent_history, select_meme
from .state import JsonState, append_jsonl, load_float_map


logger = logging.getLogger(__name__)


class MemeReactionRuntime:
    def __init__(self, ctx: Any, config_loader: Callable[[], MemeReactionConfig] = load_meme_reaction_config):
        self.ctx = ctx
        self.config_loader = config_loader

    def on_pre_gateway_dispatch(self, **kwargs: Any):
        event = kwargs.get("event")
        session_store = kwargs.get("session_store")
        source = getattr(event, "source", None)
        if source is None:
            return None

        cfg = self.config_loader()
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

        index = MemeIndex.load(cfg.index_path)
        if not index.items:
            return None

        decision = decide_with_llm(
            self.ctx,
            cfg,
            user_message=kwargs.get("user_message"),
            assistant_response=str(kwargs.get("assistant_response") or ""),
            history=kwargs.get("conversation_history") or [],
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
            last_sent[route_key] = now
            JsonState(cfg.last_sent_path).save_dict(last_sent)

        append_jsonl(
            cfg.history_path,
            {
                "ts": now,
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
```

- [ ] **Step 4: Implement plugin registration**

Create `meme_reaction/plugin.py`:

```python
from __future__ import annotations

from .config import load_meme_reaction_config
from .runtime import MemeReactionRuntime
from .tools import register_tools


def register(ctx) -> None:
    runtime = MemeReactionRuntime(ctx, config_loader=load_meme_reaction_config)
    ctx.register_hook("pre_gateway_dispatch", runtime.on_pre_gateway_dispatch)
    ctx.register_hook("post_llm_call", runtime.on_post_llm_call)
    register_tools(ctx)
```

- [ ] **Step 5: Replace package exports**

Replace `meme_reaction/__init__.py` content with:

```python
from .plugin import register

__all__ = ["register"]
```

Keep root `__init__.py` as:

```python
try:
    from .meme_reaction import register
except ImportError:
    from meme_reaction import register

__all__ = ["register"]
```

- [ ] **Step 6: Run plugin tests and verify pass**

Run: `uv run --with pytest pytest tests/test_meme_reaction_plugin.py -q`

Expected: plugin registration, exact route sending, missing route skip, and dry-run tests pass.

- [ ] **Step 7: Run all tests**

Run: `uv run --with pytest pytest -q`

Expected: all tests pass.

- [ ] **Step 8: Commit runtime refactor**

```bash
git add __init__.py meme_reaction/__init__.py meme_reaction/plugin.py meme_reaction/runtime.py tests/test_meme_reaction_plugin.py
git commit -m "refactor: split plugin runtime hooks"
```

### Task 6: File Debug Logging and State Isolation

**Files:**
- Modify: `meme_reaction/state.py`
- Modify: `meme_reaction/runtime.py`
- Create: `tests/test_meme_reaction_state.py`

- [ ] **Step 1: Write failing debug logging tests**

Create `tests/test_meme_reaction_state.py`:

```python
from meme_reaction.config import load_meme_reaction_config
from meme_reaction.state import debug_log


def test_debug_log_does_not_write_when_disabled(tmp_path):
    cfg = load_meme_reaction_config({
        "meme_reaction": {
            "debug": {"file_enabled": False, "path": str(tmp_path / "debug.log")}
        }
    })

    debug_log(cfg, "hello")

    assert not (tmp_path / "debug.log").exists()


def test_debug_log_writes_when_enabled(tmp_path):
    cfg = load_meme_reaction_config({
        "meme_reaction": {
            "debug": {"file_enabled": True, "path": str(tmp_path / "debug.log")}
        }
    })

    debug_log(cfg, "hello")

    assert "hello" in (tmp_path / "debug.log").read_text(encoding="utf-8")
```

- [ ] **Step 2: Run state tests and verify failure**

Run: `uv run --with pytest pytest tests/test_meme_reaction_state.py -q`

Expected before implementation: FAIL because `debug_log` does not exist.

- [ ] **Step 3: Implement debug logging helper**

Add to `meme_reaction/state.py`:

```python
import time


def debug_log(cfg: Any, message: str) -> None:
    if not getattr(cfg, "debug_file_enabled", False):
        return
    path = cfg.debug.path
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(f"{time.strftime('%H:%M:%S')} {message}\n")
    except Exception:
        logger.debug("Failed to write meme reaction debug log", exc_info=True)
```

- [ ] **Step 4: Wire debug logging into runtime without `/tmp`**

In `meme_reaction/runtime.py`, import `debug_log`:

```python
from .state import JsonState, append_jsonl, debug_log, load_float_map
```

Call it at the start of hooks:

```python
debug_log(cfg, "pre_gateway_dispatch")
```

and:

```python
debug_log(cfg, "post_llm_call")
```

Do not write to `/tmp/meme-reaction-debug.log` anywhere in the codebase.

- [ ] **Step 5: Run debug tests and grep for old log path**

Run: `uv run --with pytest pytest tests/test_meme_reaction_state.py -q`

Expected: state tests pass.

Run: `rg -n "/tmp/meme-reaction-debug.log|open\\(\"/tmp" meme_reaction tests`

Expected: no matches.

- [ ] **Step 6: Commit debug/state isolation**

```bash
git add meme_reaction/state.py meme_reaction/runtime.py tests/test_meme_reaction_state.py
git commit -m "refactor: make file debug logging opt in"
```

### Task 7: README and Full Regression

**Files:**
- Modify: `README.md`
- Modify: `tests/test_meme_reaction_plugin.py` only if README examples reveal a mismatch with plugin registration behavior

- [ ] **Step 1: Update README configuration section**

Replace the config example with this minimal shape:

```yaml
plugins:
  enabled:
    - meme-reaction

meme_reaction:
  enabled: true
  dry_run: false
  trigger_weight: 0.9
  threshold: 0.55
  cooldown_seconds: 90
  platforms:
    allowed: []
    denied: []
  targets:
    allowed: []
    denied: []
  debug:
    file_enabled: false
  llm:
    enabled: true
    timeout_seconds: 30
  libraries:
    - name: default
      path: ~/.hermes/memes
      recursive: true
      enabled: true
  import:
    allowed_roots: []
    use_vision: false
```

Add this note below it:

```markdown
Empty allow/deny lists are unrestricted. For example, `platforms.allowed: []` allows every platform and `targets.allowed: []` allows every chat target. The plugin still requires an exact Hermes session route before sending, so it will skip instead of guessing a recent chat.
```

- [ ] **Step 2: Document Hermes boundary**

Add this section to `README.md`:

```markdown
## Hermes safety boundary

This plugin does not modify Hermes core code. It registers hooks and tools through the Hermes plugin API and stores plugin-owned runtime files under `~/.hermes/meme_reaction/`.

Enabling the plugin with `hermes plugins enable meme-reaction` changes Hermes user configuration, but this repository does not edit `~/.hermes/hermes-agent/**`.
```

- [ ] **Step 3: Run full test suite**

Run: `uv run --with pytest pytest -q`

Expected: all tests pass.

- [ ] **Step 4: Verify Hermes core was not touched**

Run: `git status --short`

Expected: changes only inside `/home/huanx/code/hermes-meme-reaction`.

Run: `test ! -d ~/.hermes/hermes-agent/.git || git -C ~/.hermes/hermes-agent status --short`

Expected: no output attributable to this refactor. If Hermes has pre-existing changes, do not modify or revert them.

- [ ] **Step 5: Verify no generated caches remain**

Run: `find . -type d -name __pycache__ -prune -print`

Expected: no output. If output appears, remove only local plugin cache directories with `find . -type d -name __pycache__ -prune -exec rm -rf {} +`.

- [ ] **Step 6: Commit docs and regression updates**

```bash
git add README.md tests
git commit -m "docs: document safe meme reaction configuration"
```

### Task 8: Final Verification

**Files:**
- No new files expected.

- [ ] **Step 1: Run full tests fresh**

Run: `uv run --with pytest pytest -q`

Expected: all tests pass.

- [ ] **Step 2: Inspect plugin source for forbidden Hermes writes**

Run: `rg -n "~/.hermes/hermes-agent|hermes plugins enable|hermes plugins disable|config.yaml|/tmp/meme-reaction-debug.log" .`

Expected: matches may exist only in docs that describe forbidden actions or safety boundaries. No runtime code should write these paths or invoke these commands.

- [ ] **Step 3: Inspect final diff**

Run: `git status --short`

Expected: clean working tree after planned commits, or only intentional uncommitted changes if the user requested no commits during execution.

Run: `git log --oneline -5`

Expected: recent commits correspond to this plan's tasks.
