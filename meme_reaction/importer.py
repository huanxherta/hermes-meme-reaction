"""Import local meme folders into a searchable index."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .config import MemeReactionConfig
from .index import MemeIndex, MemeItem, stat_item

_SPLIT_RE = re.compile(r"[\s_\-+，,、|｜]+")
_RESERVED_NAMES = {"index", "memes", "metadata"}


def infer_tags_from_filename(path: str | Path) -> list[str]:
    stem = Path(path).stem
    parts = [p.strip() for p in _SPLIT_RE.split(stem) if p.strip()]
    return [p for p in parts if p.lower() not in _RESERVED_NAMES][:12]


def _merge_list(old: list[str], new: Any) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in list(old or []) + (new if isinstance(new, list) else ([new] if isinstance(new, str) else [])):
        text = str(value).strip()
        key = text.lower()
        if text and key not in seen:
            seen.add(key)
            out.append(text)
    return out


def apply_metadata(item: MemeItem, data: dict[str, Any], *, source: str, overwrite: bool = False) -> MemeItem:
    for attr in ("caption",):
        val = data.get(attr)
        if val and (overwrite or not getattr(item, attr)):
            setattr(item, attr, str(val))
    for attr in ("tags", "moods", "safe_for", "avoid_for"):
        merged = _merge_list([] if overwrite else getattr(item, attr), data.get(attr))
        setattr(item, attr, merged)
    if "intensity" in data and (overwrite or item.intensity == 0.5):
        try:
            item.intensity = max(0.0, min(1.0, float(data["intensity"])))
        except (TypeError, ValueError):
            pass
    if source not in item.source:
        item.source.append(source)
    return item


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _sidecar_for(path: Path) -> dict[str, Any] | None:
    return _load_json(path.with_suffix(".json"))


def _iter_files(root: Path, *, recursive: bool, exts: tuple[str, ...]):
    pattern = "**/*" if recursive else "*"
    for p in root.glob(pattern):
        if p.is_file() and p.suffix.lower() in exts:
            yield p


def import_libraries(cfg: MemeReactionConfig) -> MemeIndex:
    """Scan configured libraries and build an index.

    Vision tagging is intentionally left as a later extension point; this pass
    handles existing index metadata, sidecars, and filename inference.
    """
    existing = MemeIndex.load(cfg.index_path)
    by_path = {str(Path(item.path).expanduser().resolve()): item for item in existing.items if item.path}
    out: list[MemeItem] = []

    for lib in cfg.libraries:
        if not lib.enabled:
            continue
        root = lib.path.expanduser()
        if not root.is_dir():
            continue

        directory_metadata: dict[str, Any] = {}
        if cfg.import_config.use_existing_index:
            for name in ("index.json", "memes.json", "metadata.json"):
                data = _load_json(root / name)
                if data:
                    raw_items = data.get("items", [])
                    if isinstance(raw_items, list):
                        for raw in raw_items:
                            if not isinstance(raw, dict):
                                continue
                            rel = raw.get("relpath") or raw.get("path")
                            if rel:
                                directory_metadata[str(rel)] = raw
                    break

        for file_path in _iter_files(root, recursive=lib.recursive, exts=cfg.import_config.supported_exts):
            resolved = str(file_path.resolve())
            previous = by_path.get(resolved)
            try:
                st = file_path.stat()
            except OSError:
                continue
            if previous and previous.mtime == st.st_mtime and previous.size == st.st_size:
                item = previous
            else:
                item = stat_item(file_path, library=lib.name, root=root)

            rel = item.relpath or file_path.name
            meta = directory_metadata.get(rel) or directory_metadata.get(file_path.name)
            if isinstance(meta, dict):
                apply_metadata(item, meta, source="index", overwrite=cfg.import_config.overwrite_existing_tags)

            if cfg.import_config.use_sidecar_json:
                sidecar = _sidecar_for(file_path)
                if sidecar:
                    apply_metadata(item, sidecar, source="sidecar", overwrite=cfg.import_config.overwrite_existing_tags)

            if cfg.import_config.infer_from_filename:
                tags = infer_tags_from_filename(file_path)
                if tags:
                    apply_metadata(item, {"tags": tags}, source="filename", overwrite=False)

            out.append(item)

    index = MemeIndex(items=out)
    index.save(cfg.index_path)
    return index
