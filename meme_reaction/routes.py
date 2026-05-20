"""Route persistence and exact route lookup."""

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
