from __future__ import annotations

import unittest
from pathlib import Path

from meme_reaction.config import MemeDebugConfig, MemeImportConfig, MemeLlmConfig, MemeLibraryConfig, MemeReactionConfig, MemeSelectionConfig, MemeTargetsConfig, MemeVisionConfig, MemeWebAuthConfig, MemeWebConfig, MemeWebThemeConfig
from meme_reaction.index import MemeItem
from meme_reaction.web.presentation import (
    find_disallowed_library,
    build_config_payload,
    build_libraries_payload,
    build_runtime_payload,
    build_selection_payload,
    build_threshold_payload,
    build_vision_payload,
    build_web_payload,
    filter_memes,
    merge_config_payload,
    split_csv,
)


class WebPresentationTest(unittest.TestCase):
    def test_split_csv_deduplicates_and_trims(self) -> None:
        self.assertEqual(split_csv("  qq, telegram ,qq , discord ,, "), ["qq", "telegram", "discord"])
        self.assertEqual(split_csv(""), [])
        self.assertEqual(split_csv(None), [])

    def test_filter_memes_matches_query_tag_library_and_enabled(self) -> None:
        items = [
            MemeItem(id="1", path="/memes/a.gif", library="default", caption="happy dog", tags=["happy"], moods=["playful"], enabled=True),
            MemeItem(id="2", path="/memes/b.gif", library="alt", caption="sad cat", tags=["sad"], moods=["sad"], enabled=False),
            MemeItem(id="3", path="/memes/c.gif", library="default", caption="angry bird", tags=["angry"], moods=["angry"], enabled=True),
        ]

        matched = filter_memes(items, query="bird", tag="angry", library="default", enabled="true")
        self.assertEqual([item.id for item in matched], ["3"])

    def test_build_config_payload_keeps_empty_lists_empty(self) -> None:
        cfg = MemeReactionConfig(
            enabled=True,
            trigger_weight=0.9,
            threshold=0.55,
            cooldown_seconds=90,
            dry_run=False,
            allowed_platforms=(),
            denied_platforms=(),
            libraries=(MemeLibraryConfig(name="default", path="/tmp/memes"),),
            import_config=MemeImportConfig(),
            selection=MemeSelectionConfig(),
            llm=MemeLlmConfig(),
            vision=MemeVisionConfig(model="vision-model", base_url="http://vision/v1"),
            targets=MemeTargetsConfig(allowed=(), denied=()),
            debug=MemeDebugConfig(),
            web=MemeWebConfig(
                auth=MemeWebAuthConfig(enabled=True, username="admin", password="secret"),
                theme=MemeWebThemeConfig(default_mode="dark"),
            ),
        )

        payload = build_config_payload(cfg, "", "", "", "")
        self.assertEqual(payload["meme_reaction"]["platforms"]["allowed"], [])
        self.assertEqual(payload["meme_reaction"]["platforms"]["denied"], [])
        self.assertEqual(payload["meme_reaction"]["targets"]["allowed"], [])
        self.assertEqual(payload["meme_reaction"]["targets"]["denied"], [])
        self.assertTrue(payload["meme_reaction"]["web"]["auth"]["enabled"])
        self.assertEqual(payload["meme_reaction"]["web"]["theme"]["default_mode"], "dark")
        self.assertEqual(payload["meme_reaction"]["vision"]["model"], "vision-model")

    def test_merge_config_payload_preserves_unrelated_sections(self) -> None:
        existing = {
            "plugins": {"enabled": ["meme-reaction", "qqonebot"]},
            "qqonebot": {"token": "secret"},
            "meme_reaction": {"enabled": False, "threshold": 0.1},
        }
        update = {
            "meme_reaction": {"enabled": True, "threshold": 0.6},
        }

        merged = merge_config_payload(existing, update)

        self.assertEqual(merged["plugins"]["enabled"], ["meme-reaction", "qqonebot"])
        self.assertEqual(merged["qqonebot"]["token"], "secret")
        self.assertTrue(merged["meme_reaction"]["enabled"])
        self.assertEqual(merged["meme_reaction"]["threshold"], 0.6)

    def test_section_payload_builders_are_scoped(self) -> None:
        runtime_payload = build_runtime_payload(enabled=True, dry_run=False, cooldown_seconds=120)
        self.assertEqual(
            runtime_payload,
            {"meme_reaction": {"enabled": True, "dry_run": False, "cooldown_seconds": 120}},
        )

        threshold_payload = build_threshold_payload(trigger_weight=0.95, threshold=0.6)
        self.assertEqual(
            threshold_payload,
            {"meme_reaction": {"trigger_weight": 0.95, "threshold": 0.6}},
        )

        selection_payload = build_selection_payload(
            top_k=12,
            repeat_penalty=0.4,
            max_same_tag_recent=2,
            allow_gif=False,
            allow_webp=True,
            allow_static_image=True,
            llm_enabled=False,
            llm_timeout_seconds=8.0,
        )
        self.assertEqual(selection_payload["meme_reaction"]["selection"]["top_k"], 12)
        self.assertEqual(selection_payload["meme_reaction"]["llm"]["timeout_seconds"], 8.0)
        self.assertNotIn("web", selection_payload["meme_reaction"])
        self.assertNotIn("vision", selection_payload["meme_reaction"])

        vision_payload = build_vision_payload(
            provider="custom",
            model="gpt-4.1-mini",
            base_url="http://vision/v1",
            api_key="secret",
        )
        self.assertEqual(vision_payload["meme_reaction"]["vision"]["provider"], "custom")
        self.assertEqual(vision_payload["meme_reaction"]["vision"]["model"], "gpt-4.1-mini")

        web_payload = build_web_payload(
            auth_enabled=True,
            username="admin",
            password="secret",
            default_theme_mode="dark",
        )
        self.assertEqual(web_payload["meme_reaction"]["web"]["auth"]["username"], "admin")
        self.assertEqual(web_payload["meme_reaction"]["web"]["theme"]["default_mode"], "dark")

    def test_build_libraries_payload_serializes_rows(self) -> None:
        payload = build_libraries_payload(
            [
                MemeLibraryConfig(name="a", path="/tmp/a", recursive=True, enabled=True),
                MemeLibraryConfig(name="b", path="/tmp/b", recursive=False, enabled=False),
            ]
        )

        self.assertEqual(
            payload,
            {
                "meme_reaction": {
                    "libraries": [
                        {"name": "a", "path": "/tmp/a", "recursive": True, "enabled": True},
                        {"name": "b", "path": "/tmp/b", "recursive": False, "enabled": False},
                    ]
                }
            },
        )

    def test_find_disallowed_library_respects_allowed_roots(self) -> None:
        cfg = MemeReactionConfig(
            import_config=MemeImportConfig(allowed_roots=(Path("/allowed"),)),
        )
        libraries = [
            MemeLibraryConfig(name="ok", path="/allowed/memes", recursive=True, enabled=True),
            MemeLibraryConfig(name="bad", path="/blocked/memes", recursive=True, enabled=True),
        ]

        blocked = find_disallowed_library(cfg, libraries)

        self.assertIsNotNone(blocked)
        self.assertEqual(blocked.name, "bad")


if __name__ == "__main__":
    unittest.main()
