from __future__ import annotations

import unittest

from nicegui import app as nicegui_app

from meme_reaction.config import MemeReactionConfig, MemeWebAuthConfig, MemeWebConfig, MemeWebThemeConfig, load_meme_reaction_config
from meme_reaction.web.security import AUTH_STORAGE_KEY, build_storage_secret, is_request_authenticated, normalize_theme_mode, verify_web_login


class FakeRequest:
    def __init__(self, session_id: str | None) -> None:
        self.session = {}
        if session_id is not None:
            self.session["id"] = session_id


class WebSecurityTest(unittest.TestCase):
    def test_load_config_parses_web_auth_and_theme(self) -> None:
        cfg = load_meme_reaction_config(
            {
                "meme_reaction": {
                    "web": {
                        "auth": {
                            "enabled": True,
                            "username": "admin",
                            "password": "secret",
                        },
                        "theme": {
                            "default_mode": "dark",
                        },
                        "session_secret": "session-secret",
                    }
                }
            }
        )

        self.assertTrue(cfg.web.auth.enabled)
        self.assertEqual(cfg.web.auth.username, "admin")
        self.assertEqual(cfg.web.auth.password, "secret")
        self.assertEqual(cfg.web.theme.default_mode, "dark")
        self.assertEqual(cfg.web.session_secret, "session-secret")

    def test_normalize_theme_mode_defaults_to_light(self) -> None:
        self.assertEqual(normalize_theme_mode(None), "light")
        self.assertEqual(normalize_theme_mode(" DARK "), "dark")
        self.assertEqual(normalize_theme_mode("weird"), "light")

    def test_verify_web_login_requires_exact_credentials(self) -> None:
        cfg = MemeReactionConfig(
            web=MemeWebConfig(
                auth=MemeWebAuthConfig(enabled=True, username="admin", password="secret"),
                theme=MemeWebThemeConfig(default_mode="light"),
            )
        )

        self.assertTrue(verify_web_login(cfg, "admin", "secret"))
        self.assertFalse(verify_web_login(cfg, "Admin", "secret"))
        self.assertFalse(verify_web_login(cfg, "admin", "wrong"))

    def test_build_storage_secret_uses_configured_value(self) -> None:
        cfg = MemeReactionConfig(
            web=MemeWebConfig(
                session_secret="fixed-secret",
                auth=MemeWebAuthConfig(enabled=True, username="admin", password="secret"),
                theme=MemeWebThemeConfig(default_mode="light"),
            )
        )

        self.assertEqual(build_storage_secret(cfg), "fixed-secret")

    def test_request_auth_uses_user_storage_flag(self) -> None:
        cfg = MemeReactionConfig(
            web=MemeWebConfig(
                auth=MemeWebAuthConfig(enabled=True, username="admin", password="secret"),
                theme=MemeWebThemeConfig(default_mode="light"),
            )
        )
        users = nicegui_app.storage._users
        session_id = "test-session"
        users[session_id] = {AUTH_STORAGE_KEY: True}
        try:
            self.assertTrue(is_request_authenticated(FakeRequest(session_id), cfg))
            self.assertFalse(is_request_authenticated(FakeRequest("missing"), cfg))
            self.assertFalse(is_request_authenticated(FakeRequest(None), cfg))
        finally:
            users.pop(session_id, None)


if __name__ == "__main__":
    unittest.main()
