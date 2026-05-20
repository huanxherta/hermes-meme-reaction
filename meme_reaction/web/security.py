"""Web auth and theme helpers for the NiceGUI dashboard."""

from __future__ import annotations

import hashlib
import hmac
from typing import Any

from fastapi import Request
from nicegui import app as nicegui_app

from meme_reaction.config import MemeReactionConfig

AUTH_STORAGE_KEY = "meme_reaction_web_authenticated"
THEME_STORAGE_KEY = "meme_reaction_web_theme_mode"
USERNAME_STORAGE_KEY = "meme_reaction_web_username"


def normalize_theme_mode(value: Any, default: str = "light") -> str:
    normalized = str(value or default).strip().lower()
    if normalized in {"light", "dark"}:
        return normalized
    return default


def build_storage_secret(cfg: MemeReactionConfig) -> str:
    configured = cfg.web.session_secret.strip()
    if configured:
        return configured
    material = "|".join(
        [
            "hermes-meme-reaction-web",
            cfg.web.auth.username.strip(),
            cfg.web.auth.password,
            str(cfg.index_path),
            str(cfg.history_path),
        ]
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def is_web_auth_configured(cfg: MemeReactionConfig) -> bool:
    return cfg.web.auth.configured


def verify_web_login(cfg: MemeReactionConfig, username: str, password: str) -> bool:
    if not cfg.web.auth.enabled:
        return True
    if not is_web_auth_configured(cfg):
        return False
    return hmac.compare_digest(str(username or ""), cfg.web.auth.username) and hmac.compare_digest(
        str(password or ""), cfg.web.auth.password
    )


def is_request_authenticated(request: Request | Any, cfg: MemeReactionConfig) -> bool:
    if not cfg.web.auth.enabled:
        return True
    session = getattr(request, "session", None) or {}
    session_id = session.get("id")
    if not session_id:
        return False
    user_storage = nicegui_app.storage._users.get(session_id)
    if user_storage is None:
        return False
    return bool(user_storage.get(AUTH_STORAGE_KEY))
