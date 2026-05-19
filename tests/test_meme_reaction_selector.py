from gateway.meme_reaction.config import load_meme_reaction_config
from gateway.meme_reaction.index import MemeIndex, MemeItem
from gateway.meme_reaction.selector import MemeDecision, select_meme


def test_decision_weight_threshold():
    cfg = load_meme_reaction_config({"meme_reaction": {"trigger_weight": 0.5, "threshold": 0.6}})
    assert not MemeDecision(should_send=True, send_score=1.0).passes(cfg)
    cfg = load_meme_reaction_config({"meme_reaction": {"trigger_weight": 1.0, "threshold": 0.6}})
    assert MemeDecision(should_send=True, send_score=0.7).passes(cfg)


def test_select_meme_matches_tags(tmp_path):
    p1 = tmp_path / "cat.webp"
    p2 = tmp_path / "sad.webp"
    p1.write_bytes(b"x")
    p2.write_bytes(b"x")
    index = MemeIndex(items=[
        MemeItem(id="1", path=str(p1), tags=["猫", "吐槽"], moods=["playful"], intensity=0.4),
        MemeItem(id="2", path=str(p2), tags=["难过"], moods=["sad"], intensity=0.8),
    ])
    cfg = load_meme_reaction_config({"meme_reaction": {"trigger_weight": 1, "threshold": 0.1}})
    decision = MemeDecision(should_send=True, send_score=0.9, wanted_tags=["吐槽"], wanted_moods=["playful"], intensity=0.4)
    selected = select_meme(decision, index, cfg)
    assert selected is not None
    assert selected.id == "1"
