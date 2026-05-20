from __future__ import annotations

import base64
import unittest
from io import BytesIO
from pathlib import Path
from unittest import mock

from PIL import Image

from meme_reaction.config import load_meme_reaction_config
from meme_reaction.vision import (
    VisionTaggingResult,
    ensure_vision_settings,
    prepare_vision_data_url,
    resolve_vision_settings,
)


class VisionHelpersTest(unittest.TestCase):
    def test_prepare_vision_data_url_preserves_static_png(self) -> None:
        with BytesIO() as buffer:
            Image.new("RGB", (16, 16), color="red").save(buffer, format="PNG")
            png_bytes = buffer.getvalue()

        path = Path(self.id().replace(".", "_") + ".png")
        try:
            path.write_bytes(png_bytes)
            data_url = prepare_vision_data_url(path)
        finally:
            path.unlink(missing_ok=True)

        self.assertTrue(data_url.startswith("data:image/png;base64,"))
        self.assertEqual(base64.b64decode(data_url.split(",", 1)[1]), png_bytes)

    def test_prepare_vision_data_url_flattens_animated_gif_to_png(self) -> None:
        frame_a = Image.new("RGB", (12, 12), color="blue")
        frame_b = Image.new("RGB", (12, 12), color="green")
        path = Path(self.id().replace(".", "_") + ".gif")
        try:
            frame_a.save(path, format="GIF", save_all=True, append_images=[frame_b], loop=0, duration=80)
            data_url = prepare_vision_data_url(path)
        finally:
            path.unlink(missing_ok=True)

        self.assertTrue(data_url.startswith("data:image/png;base64,"))

    def test_vision_result_normalizes_lists_and_clamps_intensity(self) -> None:
        result = VisionTaggingResult.from_payload(
            {
                "caption": "猫猫坏笑",
                "tags": [" 坏笑 ", "坏笑", "", "猫猫"],
                "moods": "playful",
                "safe_for": ["调侃", "调侃"],
                "avoid_for": None,
                "intensity": 3,
            }
        )

        self.assertEqual(result.caption, "猫猫坏笑")
        self.assertEqual(result.tags, ["坏笑", "猫猫"])
        self.assertEqual(result.moods, ["playful"])
        self.assertEqual(result.safe_for, ["调侃"])
        self.assertEqual(result.avoid_for, [])
        self.assertEqual(result.intensity, 1.0)

    def test_resolve_vision_settings_prefers_plugin_overrides(self) -> None:
        cfg = load_meme_reaction_config(
            {
                "model": {
                    "default": "host-model",
                    "provider": "host-provider",
                    "base_url": "http://host/v1",
                    "api_key": "host-key",
                },
                "auxiliary": {
                    "vision": {
                        "provider": "aux-provider",
                        "model": "aux-model",
                        "base_url": "http://aux/v1",
                        "api_key": "aux-key",
                        "timeout": 12,
                    }
                },
                "meme_reaction": {
                    "vision": {
                        "provider": "plugin-provider",
                        "model": "plugin-model",
                        "base_url": "http://plugin/v1",
                        "api_key": "plugin-key",
                    }
                },
            }
        )

        resolved = resolve_vision_settings(cfg)

        self.assertEqual(resolved.provider, "plugin-provider")
        self.assertEqual(resolved.model, "plugin-model")
        self.assertEqual(resolved.base_url, "http://plugin/v1")
        self.assertEqual(resolved.api_key, "plugin-key")
        self.assertEqual(resolved.timeout_seconds, 12.0)

    def test_resolve_vision_settings_inherits_auxiliary_then_model(self) -> None:
        cfg = load_meme_reaction_config(
            {
                "model": {
                    "default": "host-model",
                    "provider": "host-provider",
                    "base_url": "http://host/v1",
                    "api_key": "host-key",
                },
                "auxiliary": {
                    "vision": {
                        "provider": "aux-provider",
                        "model": "",
                        "base_url": "",
                        "api_key": "",
                        "timeout": 9,
                    }
                },
                "meme_reaction": {},
            }
        )

        with mock.patch.dict("os.environ", {"OPENAI_VISION_MODEL": "env-model"}, clear=False):
            resolved = resolve_vision_settings(cfg)

        self.assertEqual(resolved.provider, "aux-provider")
        self.assertEqual(resolved.model, "")
        self.assertEqual(resolved.base_url, "http://host/v1")
        self.assertEqual(resolved.api_key, "host-key")
        self.assertEqual(resolved.timeout_seconds, 9.0)

    def test_ensure_vision_settings_raises_clear_error_when_model_missing(self) -> None:
        cfg = load_meme_reaction_config(
            {
                "model": {
                    "default": "host-model",
                    "provider": "host-provider",
                    "base_url": "http://host/v1",
                    "api_key": "host-key",
                },
                "auxiliary": {"vision": {"model": "", "api_key": ""}},
                "meme_reaction": {},
            }
        )

        with self.assertRaisesRegex(RuntimeError, "未配置视觉模型"):
            ensure_vision_settings(resolve_vision_settings(cfg))

    def test_resolve_vision_settings_does_not_fall_back_to_plugin_llm_model(self) -> None:
        cfg = load_meme_reaction_config(
            {
                "meme_reaction": {
                    "llm": {
                        "model": "legacy-llm-model",
                    },
                    "vision": {
                        "model": "",
                    },
                },
                "auxiliary": {
                    "vision": {
                        "model": "",
                    }
                },
            }
        )

        resolved = resolve_vision_settings(cfg)

        self.assertEqual(resolved.model, "")


if __name__ == "__main__":
    unittest.main()
