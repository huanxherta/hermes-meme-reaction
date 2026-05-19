from pathlib import Path

from gateway.meme_reaction.config import load_meme_reaction_config


def test_default_config_is_disabled_and_has_paths(tmp_path, monkeypatch):
    cfg = load_meme_reaction_config({})
    assert cfg.enabled is False
    assert cfg.trigger_weight == 0.9
    assert cfg.threshold == 0.55
    assert cfg.libraries[0].name == "default"


def test_config_parses_libraries_and_platforms(tmp_path):
    cfg = load_meme_reaction_config({
        "meme_reaction": {
            "enabled": True,
            "trigger_weight": 0.7,
            "allowed_platforms": ["qqonebot", "telegram"],
            "libraries": [{"name": "x", "path": str(tmp_path), "recursive": False}],
            "import": {"supported_exts": ["png", ".webp"]},
        }
    })
    assert cfg.enabled is True
    assert cfg.trigger_weight == 0.7
    assert cfg.platform_allowed("telegram") is True
    assert cfg.platform_allowed("feishu") is False
    assert cfg.libraries[0].path == Path(tmp_path)
    assert cfg.import_config.supported_exts == (".png", ".webp")
