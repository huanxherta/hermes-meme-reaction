from meme_reaction.config import load_meme_reaction_config
from meme_reaction.importer import import_libraries, infer_tags_from_filename
from meme_reaction.index import MemeIndex, MemeItem, delete_meme_item


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


def test_delete_meme_item_removes_file_sidecar_and_index_entry(tmp_path):
    meme = tmp_path / "安慰_摸摸头_猫猫.webp"
    sidecar = meme.with_suffix(".json")
    meme.write_bytes(b"fake")
    sidecar.write_text('{"caption":"old"}', encoding="utf-8")
    index_path = tmp_path / "index-out.json"
    cfg = load_meme_reaction_config({
        "meme_reaction": {
            "index_path": str(index_path),
            "libraries": [{"name": "test", "path": str(tmp_path), "recursive": False}],
            "import": {"use_vision": False},
        }
    })
    index = import_libraries(cfg)

    result = delete_meme_item(cfg, index.items[0].id)

    assert result.success is True
    assert meme.exists() is False
    assert sidecar.exists() is False
    assert MemeIndex.load(index_path).items == []


def test_delete_meme_item_rejects_paths_outside_library_roots(tmp_path):
    library_root = tmp_path / "library"
    library_root.mkdir()
    outside = tmp_path / "outside.webp"
    outside.write_bytes(b"fake")
    index_path = tmp_path / "index-out.json"
    cfg = load_meme_reaction_config({
        "meme_reaction": {
            "index_path": str(index_path),
            "libraries": [{"name": "test", "path": str(library_root), "recursive": False}],
            "import": {"use_vision": False},
        }
    })
    MemeIndex(items=[
        MemeItem(
            id="x",
            path=str(outside.resolve()),
            library="test",
            relpath=outside.name,
            size=outside.stat().st_size,
        )
    ]).save(index_path)

    result = delete_meme_item(cfg, "x")

    assert result.success is False
    assert result.error == "item_path_not_in_library"
    assert outside.exists() is True
