"""Web Dashboard package for Hermes Meme Reaction plugin."""
from __future__ import annotations

from typing import Any


def start_server(*args: Any, **kwargs: Any) -> Any:
    from .server import start_server as _start_server

    return _start_server(*args, **kwargs)


__all__ = ["start_server"]
