from dataclasses import dataclass, field

from meme_reaction.config import load_meme_reaction_config
from meme_reaction.routes import Route
from meme_reaction.sender import SendResult, send_meme


@dataclass
class Item:
    id: str = "m1"
    path: str = "/tmp/cat.webp"
    tags: list[str] = field(default_factory=lambda: ["cat"])
    moods: list[str] = field(default_factory=lambda: ["playful"])


class FakeCtx:
    def __init__(self):
        self.sent = []

    def dispatch_tool(self, name, args, **kwargs):
        self.sent.append((name, args))
        return {"success": True}


def test_send_meme_dry_run_does_not_dispatch():
    cfg = load_meme_reaction_config({"meme_reaction": {"dry_run": True}})
    ctx = FakeCtx()
    route = Route(platform="telegram", chat_id="-100", thread_id="42")

    result = send_meme(ctx, cfg, route, Item())

    assert result == SendResult(success=True, target="telegram:-100:42", dry_run=True, error="")
    assert ctx.sent == []


def test_send_meme_blocks_denied_target():
    cfg = load_meme_reaction_config({
        "meme_reaction": {"targets": {"denied": ["telegram:-100:42"]}}
    })
    ctx = FakeCtx()
    route = Route(platform="telegram", chat_id="-100", thread_id="42")

    result = send_meme(ctx, cfg, route, Item())

    assert result.success is False
    assert result.error == "target_denied"
    assert ctx.sent == []
