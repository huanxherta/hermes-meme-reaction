from meme_reaction.config import load_meme_reaction_config
from meme_reaction.importer import import_libraries, infer_tags_from_filename
from meme_reaction.index import MemeIndex


def test_infer_tags_from_filename():
    assert infer_tags_from_filename("安慰_摸摸头_猫猫.webp") == ["安慰", "摸摸头", "猫猫"]


def test_import_libraries_uses_filename_tags(tmp_path):
    meme = tmp_path / "安慰_摸摸头_猫猫.webp"
    meme.write_bytes(b"fake")
    index_path = tmp_path / "index-out.json"
    cfg = load_meme_reaction_config({
        "meme_reaction": {
            "index_path": str(index_path),
            "libraries": [{"name": "test", "path": str(tmp_path), "recursive": False}],
            "import": {"use_vision": False},
        }
    })
    index = import_libraries(cfg)
    assert len(index.items) == 1
    assert "安慰" in index.items[0].tags
    assert index_path.exists()
    loaded = MemeIndex.load(index_path)
    assert loaded.items[0].library == "test"
