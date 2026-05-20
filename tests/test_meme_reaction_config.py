from pathlib import Path

from meme_reaction.config import load_meme_reaction_config


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


def test_config_accepts_readme_platform_shape(tmp_path):
    cfg = load_meme_reaction_config({
        "meme_reaction": {
            "platforms": {
                "allowed": ["qqonebot", "telegram"],
                "denied": ["discord"],
            },
            "libraries": [{"name": "x", "path": str(tmp_path), "recursive": False}],
        }
    })
    assert cfg.platform_allowed("telegram") is True
    assert cfg.platform_allowed("discord") is False
    assert cfg.platform_allowed("feishu") is False


def test_empty_restrictions_are_unrestricted(tmp_path):
    cfg = load_meme_reaction_config({
        "meme_reaction": {
            "platforms": {"allowed": [], "denied": []},
            "targets": {"allowed": [], "denied": []},
            "import": {"allowed_roots": []},
            "libraries": [{"name": "x", "path": str(tmp_path), "recursive": False}],
        }
    })
    assert cfg.platform_allowed("telegram") is True
    assert cfg.target_allowed("telegram:-100:42") is True
    assert cfg.import_path_allowed(tmp_path / "anywhere") is True


def test_target_deny_overrides_allow(tmp_path):
    cfg = load_meme_reaction_config({
        "meme_reaction": {
            "targets": {
                "allowed": ["telegram:-100"],
                "denied": ["telegram:-100:42"],
            },
            "libraries": [{"name": "x", "path": str(tmp_path), "recursive": False}],
        }
    })
    assert cfg.target_allowed("telegram:-100") is True
    assert cfg.target_allowed("telegram:-100:42") is False


def test_runtime_defaults_are_safe_and_file_debug_is_off():
    cfg = load_meme_reaction_config({})
    assert cfg.enabled is False
    assert cfg.dry_run is False
    assert cfg.debug_file_enabled is False
