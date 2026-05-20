import json

from meme_reaction.config import load_meme_reaction_config
from meme_reaction.tools import handle_import


def test_import_tool_unrestricted_empty_roots_allows_path(tmp_path, monkeypatch):
    meme = tmp_path / "开心_猫猫.webp"
    meme.write_bytes(b"x")
    cfg = load_meme_reaction_config({
        "meme_reaction": {
            "index_path": str(tmp_path / "index.json"),
            "libraries": [{"name": "default", "path": str(tmp_path), "recursive": False}],
            "import": {"use_vision": False, "allowed_roots": []},
        }
    })
    monkeypatch.setattr("meme_reaction.tools.load_meme_reaction_config", lambda: cfg)

    result = json.loads(handle_import({"path": str(tmp_path), "recursive": False}))

    assert result["success"] is True
    assert result["count"] == 1


def test_import_tool_returns_error_for_disallowed_path(tmp_path, monkeypatch):
    allowed = tmp_path / "allowed"
    blocked = tmp_path / "blocked"
    allowed.mkdir()
    blocked.mkdir()
    cfg = load_meme_reaction_config({
        "meme_reaction": {
            "index_path": str(tmp_path / "index.json"),
            "libraries": [{"name": "default", "path": str(allowed), "recursive": False}],
            "import": {"allowed_roots": [str(allowed)]},
        }
    })
    monkeypatch.setattr("meme_reaction.tools.load_meme_reaction_config", lambda: cfg)

    result = json.loads(handle_import({"path": str(blocked), "recursive": False}))

    assert result["success"] is False
    assert result["error"] == "path_not_allowed"
