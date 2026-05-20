from __future__ import annotations

import builtins
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from meme_reaction.config import get_hermes_config_path, load_meme_reaction_config, load_root_config_file, save_root_config_file


class ConfigLoaderFallbackTest(unittest.TestCase):
    def test_load_config_falls_back_to_local_yaml_when_hermes_cli_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            hermes_home = Path(tmpdir) / ".hermes"
            hermes_home.mkdir(parents=True)
            (hermes_home / "config.yaml").write_text(
                """
meme_reaction:
  enabled: true
  threshold: 0.72
  libraries:
    - name: local
      path: /tmp/local-memes
      recursive: false
""".strip(),
                encoding="utf-8",
            )

            original_import = builtins.__import__

            def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
                if name == "hermes_cli.config":
                    raise ModuleNotFoundError(name)
                return original_import(name, globals, locals, fromlist, level)

            with mock.patch("meme_reaction.config.get_hermes_home", return_value=hermes_home):
                with mock.patch("builtins.__import__", side_effect=fake_import):
                    cfg = load_meme_reaction_config()

            self.assertTrue(cfg.enabled)
            self.assertEqual(cfg.threshold, 0.72)
            self.assertEqual(cfg.libraries[0].name, "local")
            self.assertEqual(cfg.libraries[0].path, Path("/tmp/local-memes"))

    def test_root_config_helpers_use_hermes_home(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            hermes_home = Path(tmpdir) / "custom-home"
            expected_path = hermes_home / "config.yaml"

            with mock.patch("meme_reaction.config.get_hermes_home", return_value=hermes_home):
                self.assertEqual(get_hermes_config_path(), expected_path)
                written_path = save_root_config_file({"meme_reaction": {"enabled": True}})
                loaded = load_root_config_file()

            self.assertEqual(written_path, expected_path)
            self.assertEqual(loaded["meme_reaction"]["enabled"], True)
            self.assertTrue(expected_path.is_file())


if __name__ == "__main__":
    unittest.main()
