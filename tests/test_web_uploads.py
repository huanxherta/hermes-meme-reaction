from __future__ import annotations

import json
import unittest
from pathlib import Path

from meme_reaction.config import load_meme_reaction_config
from meme_reaction.index import MemeIndex
from meme_reaction.vision import VisionTaggingResult
from meme_reaction.web.uploads import PendingUploadWorkspace


class PendingUploadWorkspaceTest(unittest.TestCase):
    def test_workspace_persists_pending_items_and_recognition_status(self) -> None:
        with self.subTest("create and reload"):
            import tempfile

            with tempfile.TemporaryDirectory() as tmpdir:
                root = Path(tmpdir)
                staged = root / "staging" / "happy.gif"
                staged.parent.mkdir(parents=True, exist_ok=True)
                staged.write_bytes(b"gif")

                workspace = PendingUploadWorkspace(root)
                item = workspace.add_staged_file(
                    original_name="happy.gif",
                    staged_path=staged,
                    library="default",
                    content_type="image/gif",
                    size=staged.stat().st_size,
                )
                workspace.mark_ready(
                    item.id,
                    VisionTaggingResult(
                        caption="开心摇头",
                        tags=["开心"],
                        moods=["playful"],
                        safe_for=["活跃聊天"],
                        avoid_for=[],
                        intensity=0.6,
                    ),
                )

                reloaded = PendingUploadWorkspace(root).list_items()

                self.assertEqual(len(reloaded), 1)
                self.assertEqual(reloaded[0].status, "ready")
                self.assertEqual(reloaded[0].caption, "开心摇头")
                self.assertEqual(reloaded[0].tags, ["开心"])

        with self.subTest("failed recognition"):
            import tempfile

            with tempfile.TemporaryDirectory() as tmpdir:
                root = Path(tmpdir)
                staged = root / "staging" / "sad.png"
                staged.parent.mkdir(parents=True, exist_ok=True)
                staged.write_bytes(b"png")

                workspace = PendingUploadWorkspace(root)
                item = workspace.add_staged_file(
                    original_name="sad.png",
                    staged_path=staged,
                    library="default",
                    content_type="image/png",
                    size=staged.stat().st_size,
                )
                workspace.mark_failed(item.id, "missing api key")

                reloaded = PendingUploadWorkspace(root).list_items()

                self.assertEqual(reloaded[0].status, "failed")
                self.assertEqual(reloaded[0].error, "missing api key")

    def test_import_items_moves_files_writes_sidecar_and_updates_index(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            library_dir = root / "library"
            library_dir.mkdir()
            staged = root / "staging" / "angry-cat.gif"
            staged.parent.mkdir(parents=True, exist_ok=True)
            staged.write_bytes(b"gif89a")

            cfg = load_meme_reaction_config(
                {
                    "meme_reaction": {
                        "index_path": str(root / "index.json"),
                        "libraries": [{"name": "default", "path": str(library_dir), "recursive": False}],
                    }
                }
            )

            workspace = PendingUploadWorkspace(root)
            item = workspace.add_staged_file(
                original_name="angry-cat.gif",
                staged_path=staged,
                library="default",
                content_type="image/gif",
                size=staged.stat().st_size,
            )
            workspace.mark_ready(
                item.id,
                VisionTaggingResult(
                    caption="生气猫猫",
                    tags=["生气", "猫猫"],
                    moods=["angry"],
                    safe_for=["吐槽"],
                    avoid_for=["安慰"],
                    intensity=0.9,
                ),
            )

            result = workspace.import_items(cfg, [item.id])

            self.assertEqual(result.imported_ids, [item.id])
            self.assertEqual(result.failed, {})
            self.assertFalse(staged.exists())
            self.assertEqual(PendingUploadWorkspace(root).list_items(), [])

            imported_files = [path for path in library_dir.iterdir() if path.suffix == ".gif"]
            self.assertEqual(len(imported_files), 1)
            sidecar = imported_files[0].with_suffix(".json")
            self.assertTrue(sidecar.is_file())
            self.assertEqual(json.loads(sidecar.read_text(encoding="utf-8"))["caption"], "生气猫猫")

            index = MemeIndex.load(cfg.index_path)
            self.assertEqual(len(index.items), 1)
            self.assertEqual(index.items[0].caption, "生气猫猫")
            self.assertEqual(index.items[0].tags, ["生气", "猫猫"])

    def test_import_items_rejects_library_outside_allowed_roots(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            allowed_root = root / "allowed"
            allowed_root.mkdir()
            library_dir = root / "outside-library"
            library_dir.mkdir()
            staged = root / "staging" / "angry-cat.gif"
            staged.parent.mkdir(parents=True, exist_ok=True)
            staged.write_bytes(b"gif89a")

            cfg = load_meme_reaction_config(
                {
                    "meme_reaction": {
                        "index_path": str(root / "index.json"),
                        "libraries": [{"name": "default", "path": str(library_dir), "recursive": False}],
                        "import": {"allowed_roots": [str(allowed_root)]},
                    }
                }
            )

            workspace = PendingUploadWorkspace(root)
            item = workspace.add_staged_file(
                original_name="angry-cat.gif",
                staged_path=staged,
                library="default",
                content_type="image/gif",
                size=staged.stat().st_size,
            )
            workspace.mark_ready(
                item.id,
                VisionTaggingResult(
                    caption="生气猫猫",
                    tags=["生气"],
                    moods=["angry"],
                ),
            )

            result = workspace.import_items(cfg, [item.id])

            self.assertEqual(result.imported_ids, [])
            self.assertIn(item.id, result.failed)
            self.assertIn("not allowed", result.failed[item.id])
            self.assertTrue(staged.exists())
            self.assertEqual(len(PendingUploadWorkspace(root).list_items()), 1)
            self.assertEqual(MemeIndex.load(cfg.index_path).items, [])


if __name__ == "__main__":
    unittest.main()
