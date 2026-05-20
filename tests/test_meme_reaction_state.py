from meme_reaction.config import load_meme_reaction_config
from meme_reaction.state import debug_log


def test_debug_log_does_not_write_when_disabled(tmp_path):
    cfg = load_meme_reaction_config({
        "meme_reaction": {
            "debug": {"file_enabled": False, "path": str(tmp_path / "debug.log")}
        }
    })

    debug_log(cfg, "hello")

    assert not (tmp_path / "debug.log").exists()


def test_debug_log_writes_when_enabled(tmp_path):
    cfg = load_meme_reaction_config({
        "meme_reaction": {
            "debug": {"file_enabled": True, "path": str(tmp_path / "debug.log")}
        }
    })

    debug_log(cfg, "hello")

    assert "hello" in (tmp_path / "debug.log").read_text(encoding="utf-8")
