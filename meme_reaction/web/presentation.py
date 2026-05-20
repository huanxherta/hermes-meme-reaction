"""Pure presentation helpers for the Hermes meme reaction web dashboard."""

from __future__ import annotations

from typing import Iterable, Sequence

from meme_reaction.config import MemeLibraryConfig, MemeReactionConfig
from meme_reaction.index import MemeItem
from meme_reaction.web.security import normalize_theme_mode


def split_csv(raw: str | None) -> list[str]:
    if not raw:
        return []
    seen: set[str] = set()
    values: list[str] = []
    for part in raw.split(","):
        item = part.strip()
        if not item:
            continue
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        values.append(item)
    return values


def join_csv(values: Sequence[str] | Iterable[str]) -> str:
    return ", ".join([str(value).strip() for value in values if str(value).strip()])


def filter_memes(
    items: Iterable[MemeItem],
    *,
    query: str = "",
    tag: str = "",
    library: str = "",
    enabled: str = "",
) -> list[MemeItem]:
    q = query.strip().lower()
    wanted_tag = tag.strip().lower()
    wanted_library = library.strip().lower()
    enabled_value = enabled.strip().lower()

    out: list[MemeItem] = []
    for item in items:
        if wanted_library and item.library.lower() != wanted_library:
            continue
        if enabled_value in {"true", "false"} and str(item.enabled).lower() != enabled_value:
            continue

        haystack = " ".join(
            [item.path, item.caption, item.library, *item.tags, *item.moods, *item.safe_for, *item.avoid_for]
        ).lower()
        if q and q not in haystack:
            continue

        if wanted_tag:
            tag_pool = {value.lower() for value in [*item.tags, *item.moods]}
            if wanted_tag not in tag_pool:
                continue

        out.append(item)
    return out


def build_runtime_payload(*, enabled: bool, dry_run: bool, cooldown_seconds: int) -> dict[str, object]:
    return {
        "meme_reaction": {
            "enabled": bool(enabled),
            "dry_run": bool(dry_run),
            "cooldown_seconds": int(cooldown_seconds),
        }
    }


def build_threshold_payload(*, trigger_weight: float, threshold: float) -> dict[str, object]:
    return {
        "meme_reaction": {
            "trigger_weight": float(trigger_weight),
            "threshold": float(threshold),
        }
    }


def build_selection_payload(
    *,
    top_k: int,
    repeat_penalty: float,
    max_same_tag_recent: int,
    allow_gif: bool,
    allow_webp: bool,
    allow_static_image: bool,
    llm_enabled: bool,
    llm_timeout_seconds: float,
) -> dict[str, object]:
    return {
        "meme_reaction": {
            "selection": {
                "top_k": int(top_k),
                "repeat_penalty": float(repeat_penalty),
                "max_same_tag_recent": int(max_same_tag_recent),
                "allow_gif": bool(allow_gif),
                "allow_webp": bool(allow_webp),
                "allow_static_image": bool(allow_static_image),
            },
            "llm": {
                "enabled": bool(llm_enabled),
                "timeout_seconds": float(llm_timeout_seconds),
            },
        }
    }


def build_vision_payload(
    *,
    provider: str,
    model: str,
    base_url: str,
    api_key: str,
) -> dict[str, object]:
    return {
        "meme_reaction": {
            "vision": {
                "provider": str(provider or "").strip(),
                "model": str(model or "").strip(),
                "base_url": str(base_url or "").strip(),
                "api_key": str(api_key or "").strip(),
            }
        }
    }


def build_web_payload(
    *,
    auth_enabled: bool,
    username: str,
    password: str,
    default_theme_mode: str,
) -> dict[str, object]:
    return {
        "meme_reaction": {
            "web": {
                "auth": {
                    "enabled": bool(auth_enabled),
                    "username": str(username or "").strip(),
                    "password": str(password or ""),
                },
                "theme": {
                    "default_mode": normalize_theme_mode(default_theme_mode, "light"),
                },
            }
        }
    }


def build_libraries_payload(libraries: Sequence[MemeLibraryConfig]) -> dict[str, object]:
    return {
        "meme_reaction": {
            "libraries": [
                {
                    "name": lib.name,
                    "path": str(lib.path),
                    "recursive": lib.recursive,
                    "enabled": lib.enabled,
                }
                for lib in libraries
            ]
        }
    }


def find_disallowed_library(
    cfg: MemeReactionConfig,
    libraries: Sequence[MemeLibraryConfig],
) -> MemeLibraryConfig | None:
    for library in libraries:
        if not cfg.import_path_allowed(library.path):
            return library
    return None


def build_config_payload(
    cfg: MemeReactionConfig,
    allowed_platforms: str,
    denied_platforms: str,
    allowed_targets: str,
    denied_targets: str,
) -> dict[str, object]:
    libraries = [
        {
            "name": lib.name,
            "path": str(lib.path),
            "recursive": lib.recursive,
            "enabled": lib.enabled,
        }
        for lib in cfg.libraries
    ]
    return {
        "meme_reaction": {
            "enabled": cfg.enabled,
            "dry_run": cfg.dry_run,
            "cooldown_seconds": cfg.cooldown_seconds,
            "trigger_weight": cfg.trigger_weight,
            "threshold": cfg.threshold,
            "platforms": {
                "allowed": [x.lower() for x in split_csv(allowed_platforms)],
                "denied": [x.lower() for x in split_csv(denied_platforms)],
            },
            "targets": {
                "allowed": [x.lower() for x in split_csv(allowed_targets)],
                "denied": [x.lower() for x in split_csv(denied_targets)],
            },
            "libraries": libraries,
            "selection": {
                "top_k": cfg.selection.top_k,
                "repeat_penalty": cfg.selection.repeat_penalty,
                "max_same_tag_recent": cfg.selection.max_same_tag_recent,
                "allow_gif": cfg.selection.allow_gif,
                "allow_webp": cfg.selection.allow_webp,
                "allow_static_image": cfg.selection.allow_static_image,
            },
            "llm": {
                "enabled": cfg.llm.enabled,
                "timeout_seconds": cfg.llm.timeout_seconds,
                "provider": cfg.llm.provider,
                "model": cfg.llm.model,
            },
            "vision": {
                "provider": cfg.vision.provider,
                "model": cfg.vision.model,
                "base_url": cfg.vision.base_url,
                "api_key": cfg.vision.api_key,
            },
            "web": {
                "session_secret": cfg.web.session_secret,
                "auth": {
                    "enabled": cfg.web.auth.enabled,
                    "username": cfg.web.auth.username,
                    "password": cfg.web.auth.password,
                },
                "theme": {
                    "default_mode": cfg.web.theme.default_mode,
                },
            },
            "import": {
                "allowed_roots": [str(path) for path in cfg.import_config.allowed_roots],
                "use_vision": cfg.import_config.use_vision,
            },
        }
    }


def merge_config_payload(existing: dict[str, object] | None, update: dict[str, object]) -> dict[str, object]:
    """Merge a config payload into an existing Hermes config without dropping unrelated keys."""
    base = dict(existing or {})
    for key, value in update.items():
        current = base.get(key)
        if isinstance(current, dict) and isinstance(value, dict):
            base[key] = merge_config_payload(current, value)
        else:
            base[key] = value
    return base
