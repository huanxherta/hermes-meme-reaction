"""Configuration helpers for gateway meme reactions."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    from hermes_constants import get_hermes_home
except ModuleNotFoundError:
    def get_hermes_home() -> Path:
        return Path.home() / ".hermes"


SUPPORTED_IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".gif")


def _expand_path(value: str | None, default: str) -> Path:
    raw = value or default
    return Path(str(raw).replace("~", str(Path.home()), 1)).expanduser()


def _as_float(value: Any, default: float, *, minimum: float = 0.0, maximum: float = 1.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


def _as_int(value: Any, default: int, *, minimum: int = 0) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, parsed)


@dataclass(slots=True)
class MemeLibraryConfig:
    name: str
    path: Path
    recursive: bool = True
    enabled: bool = True


@dataclass(slots=True)
class MemeImportConfig:
    use_existing_index: bool = True
    use_sidecar_json: bool = True
    infer_from_filename: bool = True
    use_vision: bool = True
    vision_batch_size: int = 1
    overwrite_existing_tags: bool = False
    supported_exts: tuple[str, ...] = SUPPORTED_IMAGE_EXTS
    allowed_roots: tuple[Path, ...] = ()


@dataclass(slots=True)
class MemeSelectionConfig:
    top_k: int = 8
    repeat_penalty: float = 0.8
    max_same_tag_recent: int = 3
    allow_gif: bool = True
    allow_webp: bool = True
    allow_static_image: bool = True


@dataclass(slots=True)
class MemeLlmConfig:
    enabled: bool = True
    timeout_seconds: float = 4.0
    provider: str | None = None
    model: str | None = None


@dataclass(slots=True)
class MemeTargetsConfig:
    allowed: tuple[str, ...] = ()
    denied: tuple[str, ...] = ()


@dataclass(slots=True)
class MemeDebugConfig:
    file_enabled: bool = False
    path: Path = field(default_factory=lambda: get_hermes_home() / "meme_reaction" / "debug.log")


@dataclass(slots=True)
class MemeReactionConfig:
    enabled: bool = False
    trigger_weight: float = 0.9
    threshold: float = 0.55
    cooldown_seconds: int = 90
    dry_run: bool = False
    allowed_platforms: tuple[str, ...] = ()
    denied_platforms: tuple[str, ...] = ()
    libraries: tuple[MemeLibraryConfig, ...] = field(default_factory=tuple)
    index_path: Path = field(default_factory=lambda: get_hermes_home() / "meme_reaction" / "index.json")
    cache_dir: Path = field(default_factory=lambda: get_hermes_home() / "meme_reaction" / "cache")
    history_path: Path = field(default_factory=lambda: get_hermes_home() / "meme_reaction" / "history.jsonl")
    routes_path: Path = field(default_factory=lambda: get_hermes_home() / "meme_reaction" / "routes.json")
    last_sent_path: Path = field(default_factory=lambda: get_hermes_home() / "meme_reaction" / "last_sent.json")
    import_config: MemeImportConfig = field(default_factory=MemeImportConfig)
    selection: MemeSelectionConfig = field(default_factory=MemeSelectionConfig)
    llm: MemeLlmConfig = field(default_factory=MemeLlmConfig)
    targets: MemeTargetsConfig = field(default_factory=MemeTargetsConfig)
    debug: MemeDebugConfig = field(default_factory=MemeDebugConfig)

    @property
    def debug_file_enabled(self) -> bool:
        return self.debug.file_enabled

    def platform_allowed(self, platform: Any) -> bool:
        name = getattr(platform, "value", platform)
        normalized = str(name or "").lower()
        if self.allowed_platforms and normalized not in self.allowed_platforms:
            return False
        return normalized not in self.denied_platforms

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


def load_meme_reaction_config(config: dict[str, Any] | None = None) -> MemeReactionConfig:
    """Load meme_reaction config from a Hermes config dict.

    Kept independent from DEFAULT_CONFIG so older configs work without migration.
    """
    if config is None:
        try:
            from hermes_cli.config import load_config
            config = load_config()
        except Exception:
            config = {}

    raw = (config or {}).get("meme_reaction", {})
    if not isinstance(raw, dict):
        raw = {}

    home = get_hermes_home()
    libraries_raw = raw.get("libraries") or []
    libraries: list[MemeLibraryConfig] = []
    if isinstance(libraries_raw, list):
        for idx, item in enumerate(libraries_raw):
            if not isinstance(item, dict):
                continue
            path = item.get("path")
            if not path:
                continue
            libraries.append(
                MemeLibraryConfig(
                    name=str(item.get("name") or f"library-{idx + 1}"),
                    path=_expand_path(str(path), str(home / "memes")),
                    recursive=bool(item.get("recursive", True)),
                    enabled=bool(item.get("enabled", True)),
                )
            )
    if not libraries:
        libraries.append(MemeLibraryConfig(name="default", path=home / "memes"))

    import_raw = raw.get("import", {}) if isinstance(raw.get("import", {}), dict) else {}
    allowed_roots_raw = import_raw.get("allowed_roots") or []
    if not isinstance(allowed_roots_raw, (list, tuple)):
        allowed_roots_raw = []
    allowed_roots = tuple(
        _expand_path(str(root), str(home / "memes"))
        for root in allowed_roots_raw
        if str(root).strip()
    )
    supported_exts = import_raw.get("supported_exts") or SUPPORTED_IMAGE_EXTS
    if not isinstance(supported_exts, (list, tuple)):
        supported_exts = SUPPORTED_IMAGE_EXTS
    normalized_exts = tuple(
        ext.lower() if str(ext).startswith(".") else f".{str(ext).lower()}"
        for ext in supported_exts
    )

    selection_raw = raw.get("selection", {}) if isinstance(raw.get("selection", {}), dict) else {}
    llm_raw = raw.get("llm", {}) if isinstance(raw.get("llm", {}), dict) else {}
    targets_raw = raw.get("targets", {}) if isinstance(raw.get("targets", {}), dict) else {}
    debug_raw = raw.get("debug", {}) if isinstance(raw.get("debug", {}), dict) else {}

    platforms_raw = raw.get("platforms", {}) if isinstance(raw.get("platforms", {}), dict) else {}
    allowed = raw.get("allowed_platforms", platforms_raw.get("allowed", [])) or []
    denied = raw.get("denied_platforms", platforms_raw.get("denied", [])) or []
    if not isinstance(allowed, (list, tuple)):
        allowed = []
    if not isinstance(denied, (list, tuple)):
        denied = []

    return MemeReactionConfig(
        enabled=bool(raw.get("enabled", False)),
        trigger_weight=_as_float(raw.get("trigger_weight", raw.get("probability", 0.9)), 0.9),
        threshold=_as_float(raw.get("threshold", 0.55), 0.55),
        cooldown_seconds=_as_int(raw.get("cooldown_seconds", 90), 90),
        dry_run=bool(raw.get("dry_run", False)),
        allowed_platforms=tuple(str(x).lower() for x in allowed),
        denied_platforms=tuple(str(x).lower() for x in denied),
        libraries=tuple(libraries),
        index_path=_expand_path(raw.get("index_path"), str(home / "meme_reaction" / "index.json")),
        cache_dir=_expand_path(raw.get("cache_dir"), str(home / "meme_reaction" / "cache")),
        history_path=_expand_path(raw.get("history_path"), str(home / "meme_reaction" / "history.jsonl")),
        routes_path=_expand_path(raw.get("routes_path"), str(home / "meme_reaction" / "routes.json")),
        last_sent_path=_expand_path(raw.get("last_sent_path"), str(home / "meme_reaction" / "last_sent.json")),
        import_config=MemeImportConfig(
            use_existing_index=bool(import_raw.get("use_existing_index", True)),
            use_sidecar_json=bool(import_raw.get("use_sidecar_json", True)),
            infer_from_filename=bool(import_raw.get("infer_from_filename", True)),
            use_vision=bool(import_raw.get("use_vision", True)),
            vision_batch_size=_as_int(import_raw.get("vision_batch_size", 1), 1, minimum=1),
            overwrite_existing_tags=bool(import_raw.get("overwrite_existing_tags", False)),
            supported_exts=normalized_exts,
            allowed_roots=allowed_roots,
        ),
        selection=MemeSelectionConfig(
            top_k=_as_int(selection_raw.get("top_k", 8), 8, minimum=1),
            repeat_penalty=_as_float(selection_raw.get("repeat_penalty", 0.8), 0.8),
            max_same_tag_recent=_as_int(selection_raw.get("max_same_tag_recent", 3), 3),
            allow_gif=bool(selection_raw.get("allow_gif", True)),
            allow_webp=bool(selection_raw.get("allow_webp", True)),
            allow_static_image=bool(selection_raw.get("allow_static_image", True)),
        ),
        llm=MemeLlmConfig(
            enabled=bool(llm_raw.get("enabled", True)),
            timeout_seconds=float(llm_raw.get("timeout_seconds", 4) or 4),
            provider=llm_raw.get("provider"),
            model=llm_raw.get("model"),
        ),
        targets=MemeTargetsConfig(
            allowed=tuple(str(x).lower() for x in targets_raw.get("allowed", []) if str(x).strip()),
            denied=tuple(str(x).lower() for x in targets_raw.get("denied", []) if str(x).strip()),
        ),
        debug=MemeDebugConfig(
            file_enabled=bool(debug_raw.get("file_enabled", raw.get("debug_file_enabled", False))),
            path=_expand_path(debug_raw.get("path"), str(home / "meme_reaction" / "debug.log")),
        ),
    )
