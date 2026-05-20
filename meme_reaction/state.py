"""Plugin-owned state persistence."""

from __future__ import annotations

import json
import logging
import time
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
