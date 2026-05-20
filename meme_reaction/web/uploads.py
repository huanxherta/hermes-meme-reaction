"""Persistent workspace for pending web uploads."""

from __future__ import annotations

import json
import os
import re
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence
from uuid import uuid4

from meme_reaction.config import MemeLibraryConfig, MemeReactionConfig
from meme_reaction.importer import apply_metadata
from meme_reaction.index import MemeIndex, stat_item
from meme_reaction.vision import VisionTaggingResult

_UNSAFE_FILENAME_RE = re.compile(r'[\\/:*?"<>|]+')


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_text_list(value: Any) -> list[str]:
    if value is None:
        return []
    raw_values = value if isinstance(value, list) else [value]
    seen: set[str] = set()
    out: list[str] = []
    for raw in raw_values:
        text = str(raw or "").strip()
        key = text.lower()
        if not text or key in seen:
            continue
        seen.add(key)
        out.append(text)
    return out


def _sanitize_filename(name: str) -> str:
    basename = Path(name or "upload").name.strip() or "upload"
    safe = _UNSAFE_FILENAME_RE.sub("-", basename)
    return safe or "upload"


@dataclass(slots=True)
class PendingUploadItem:
    id: str
    library: str
    original_name: str
    staged_path: str
    content_type: str = ""
    size: int = 0
    status: str = "queued"
    error: str = ""
    caption: str = ""
    tags: list[str] = field(default_factory=list)
    moods: list[str] = field(default_factory=list)
    safe_for: list[str] = field(default_factory=list)
    avoid_for: list[str] = field(default_factory=list)
    intensity: float = 0.5
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PendingUploadItem":
        item = cls(
            id=str(data.get("id") or uuid4().hex),
            library=str(data.get("library") or "default"),
            original_name=str(data.get("original_name") or "upload"),
            staged_path=str(data.get("staged_path") or ""),
            content_type=str(data.get("content_type") or ""),
            size=int(data.get("size") or 0),
            status=str(data.get("status") or "queued"),
            error=str(data.get("error") or ""),
            caption=str(data.get("caption") or ""),
            tags=_normalize_text_list(data.get("tags")),
            moods=_normalize_text_list(data.get("moods")),
            safe_for=_normalize_text_list(data.get("safe_for")),
            avoid_for=_normalize_text_list(data.get("avoid_for")),
            intensity=float(data.get("intensity") or 0.5),
            created_at=str(data.get("created_at") or _now_iso()),
            updated_at=str(data.get("updated_at") or _now_iso()),
        )
        item.intensity = max(0.0, min(1.0, item.intensity))
        return item


@dataclass(slots=True)
class ImportBatchResult:
    imported_ids: list[str] = field(default_factory=list)
    failed: dict[str, str] = field(default_factory=dict)


class PendingUploadWorkspace:
    """Small persistent queue for staged uploads awaiting import."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve()
        self.staging_dir = self.root / "staging"
        self.index_path = self.root / "pending.json"
        self.staging_dir.mkdir(parents=True, exist_ok=True)

    def list_items(self) -> list[PendingUploadItem]:
        return self._load_items()

    def get_item(self, item_id: str) -> PendingUploadItem | None:
        for item in self._load_items():
            if item.id == item_id:
                return item
        return None

    def allocate_staged_path(self, filename: str) -> Path:
        safe = _sanitize_filename(filename)
        stem = Path(safe).stem or "upload"
        suffix = Path(safe).suffix.lower()
        return self.staging_dir / f"{stem}-{uuid4().hex[:10]}{suffix}"

    def add_staged_file(
        self,
        *,
        original_name: str,
        staged_path: str | Path,
        library: str,
        content_type: str,
        size: int,
    ) -> PendingUploadItem:
        items = self._load_items()
        now = _now_iso()
        item = PendingUploadItem(
            id=uuid4().hex,
            library=str(library or "default"),
            original_name=_sanitize_filename(original_name),
            staged_path=str(Path(staged_path).expanduser().resolve()),
            content_type=str(content_type or ""),
            size=int(size or 0),
            status="queued",
            created_at=now,
            updated_at=now,
        )
        items.append(item)
        self._save_items(items)
        return item

    def mark_processing(self, item_id: str) -> None:
        self._update_item(item_id, status="processing", error="")

    def mark_ready(self, item_id: str, result: VisionTaggingResult) -> None:
        self._update_item(
            item_id,
            status="ready",
            error="",
            caption=result.caption,
            tags=list(result.tags),
            moods=list(result.moods),
            safe_for=list(result.safe_for),
            avoid_for=list(result.avoid_for),
            intensity=float(result.intensity),
        )

    def mark_failed(self, item_id: str, error: str) -> None:
        self._update_item(item_id, status="failed", error=str(error or "unknown error"))

    def remove_items(self, item_ids: Iterable[str]) -> None:
        doomed = {str(item_id) for item_id in item_ids}
        kept: list[PendingUploadItem] = []
        for item in self._load_items():
            if item.id in doomed:
                Path(item.staged_path).unlink(missing_ok=True)
                continue
            kept.append(item)
        self._save_items(kept)

    def import_items(self, cfg: MemeReactionConfig, item_ids: Sequence[str]) -> ImportBatchResult:
        items = self._load_items()
        item_map = {item.id: item for item in items}
        kept = [item for item in items if item.id not in set(item_ids)]
        index = MemeIndex.load(cfg.index_path)
        by_path = {Path(item.path).expanduser().resolve(): item for item in index.items if item.path}
        result = ImportBatchResult()

        for item_id in item_ids:
            item = item_map.get(str(item_id))
            if item is None:
                result.failed[str(item_id)] = "missing upload item"
                continue

            if item.status != "ready":
                result.failed[item.id] = "item is not ready for import"
                kept.append(item)
                continue

            staged_path = Path(item.staged_path).expanduser().resolve()
            if not staged_path.is_file():
                result.failed[item.id] = "staged file is missing"
                kept.append(item)
                continue

            library = _find_library(cfg.libraries, item.library)
            if library is None:
                result.failed[item.id] = "target library not found"
                kept.append(item)
                continue
            if not cfg.import_path_allowed(library.path):
                result.failed[item.id] = "target library path is not allowed"
                kept.append(item)
                continue

            destination = _allocate_destination(library.path, item.original_name)
            destination.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.move(str(staged_path), str(destination))
                _write_sidecar(destination, item)
                meme_item = stat_item(destination, library=library.name, root=library.path)
                apply_metadata(
                    meme_item,
                    {
                        "caption": item.caption,
                        "tags": item.tags,
                        "moods": item.moods,
                        "safe_for": item.safe_for,
                        "avoid_for": item.avoid_for,
                        "intensity": item.intensity,
                    },
                    source="upload",
                    overwrite=True,
                )
                by_path[Path(meme_item.path).expanduser().resolve()] = meme_item
                result.imported_ids.append(item.id)
            except Exception as exc:
                result.failed[item.id] = str(exc)
                kept.append(item)

        index.items = list(by_path.values())
        index.save(cfg.index_path)
        self._save_items(kept)
        return result

    def _load_items(self) -> list[PendingUploadItem]:
        if not self.index_path.is_file():
            return []
        try:
            raw = json.loads(self.index_path.read_text(encoding="utf-8"))
        except Exception:
            return []
        if not isinstance(raw, list):
            return []
        return [PendingUploadItem.from_dict(item) for item in raw if isinstance(item, dict)]

    def _save_items(self, items: Sequence[PendingUploadItem]) -> None:
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        payload = [asdict(item) for item in items]
        tmp_path = self.index_path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp_path, self.index_path)

    def _update_item(self, item_id: str, **updates: Any) -> None:
        items = self._load_items()
        for item in items:
            if item.id != item_id:
                continue
            for key, value in updates.items():
                setattr(item, key, value)
            item.updated_at = _now_iso()
            self._save_items(items)
            return
        raise KeyError(item_id)


def workspace_root_for_config(cfg: MemeReactionConfig) -> Path:
    return cfg.cache_dir / "web_uploads"


def workspace_for_config(cfg: MemeReactionConfig) -> PendingUploadWorkspace:
    return PendingUploadWorkspace(workspace_root_for_config(cfg))


def _find_library(libraries: Sequence[MemeLibraryConfig], name: str) -> MemeLibraryConfig | None:
    wanted = str(name or "").strip().lower()
    for library in libraries:
        if library.name.lower() == wanted:
            return library
    return None


def _allocate_destination(library_root: Path, original_name: str) -> Path:
    safe_name = _sanitize_filename(original_name)
    candidate = Path(library_root).expanduser().resolve() / safe_name
    stem = candidate.stem or "upload"
    suffix = candidate.suffix
    counter = 2
    while candidate.exists():
        candidate = candidate.with_name(f"{stem}-{counter}{suffix}")
        counter += 1
    return candidate


def _write_sidecar(path: Path, item: PendingUploadItem) -> None:
    payload = {
        "caption": item.caption,
        "tags": item.tags,
        "moods": item.moods,
        "safe_for": item.safe_for,
        "avoid_for": item.avoid_for,
        "intensity": item.intensity,
    }
    path.with_suffix(".json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
