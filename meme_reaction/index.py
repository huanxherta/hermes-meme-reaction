"""Meme index models and persistence."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


INDEX_VERSION = 1


@dataclass(slots=True)
class MemeItem:
    id: str
    path: str
    library: str = "default"
    relpath: str = ""
    sha256: str = ""
    mtime: float = 0.0
    size: int = 0
    caption: str = ""
    tags: list[str] = field(default_factory=list)
    moods: list[str] = field(default_factory=list)
    safe_for: list[str] = field(default_factory=list)
    avoid_for: list[str] = field(default_factory=list)
    intensity: float = 0.5
    source: list[str] = field(default_factory=list)
    enabled: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MemeItem":
        allowed = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        kwargs = {k: v for k, v in (data or {}).items() if k in allowed}
        item = cls(id=str(kwargs.get("id") or kwargs.get("path") or ""), path=str(kwargs.get("path") or ""))
        for key, value in kwargs.items():
            setattr(item, key, value)
        item.tags = _string_list(item.tags)
        item.moods = _string_list(item.moods)
        item.safe_for = _string_list(item.safe_for)
        item.avoid_for = _string_list(item.avoid_for)
        item.source = _string_list(item.source)
        try:
            item.intensity = max(0.0, min(1.0, float(item.intensity)))
        except (TypeError, ValueError):
            item.intensity = 0.5
        return item

    def exists(self) -> bool:
        return bool(self.path) and Path(self.path).is_file()


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, Iterable):
        return [str(x).strip() for x in value if str(x).strip()]
    return []


@dataclass(slots=True)
class MemeIndex:
    items: list[MemeItem] = field(default_factory=list)
    version: int = INDEX_VERSION
    generated_at: str = ""

    @classmethod
    def load(cls, path: str | Path) -> "MemeIndex":
        p = Path(path).expanduser()
        if not p.is_file():
            return cls()
        with p.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        raw_items = data.get("items", []) if isinstance(data, dict) else []
        return cls(
            items=[MemeItem.from_dict(x) for x in raw_items if isinstance(x, dict)],
            version=int(data.get("version", INDEX_VERSION)) if isinstance(data, dict) else INDEX_VERSION,
            generated_at=str(data.get("generated_at", "")) if isinstance(data, dict) else "",
        )

    def save(self, path: str | Path) -> None:
        p = Path(path).expanduser()
        p.parent.mkdir(parents=True, exist_ok=True)
        self.generated_at = datetime.now(timezone.utc).isoformat()
        payload = {
            "version": self.version,
            "generated_at": self.generated_at,
            "items": [asdict(item) for item in self.items],
        }
        tmp = p.with_suffix(p.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, p)

    def by_id(self) -> dict[str, MemeItem]:
        return {item.id: item for item in self.items}

    def existing_enabled(self) -> list[MemeItem]:
        return [item for item in self.items if item.enabled and item.exists()]


def file_sha256(path: str | Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as fh:
        while True:
            chunk = fh.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def stat_item(path: str | Path, *, library: str = "default", root: str | Path | None = None) -> MemeItem:
    p = Path(path).expanduser().resolve()
    st = p.stat()
    sha = file_sha256(p)
    relpath = ""
    if root is not None:
        try:
            relpath = str(p.relative_to(Path(root).expanduser().resolve()))
        except Exception:
            relpath = p.name
    return MemeItem(
        id=f"sha256:{sha}",
        path=str(p),
        library=library,
        relpath=relpath or p.name,
        sha256=sha,
        mtime=st.st_mtime,
        size=st.st_size,
        source=[],
    )
