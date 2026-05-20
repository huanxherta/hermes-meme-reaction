from types import SimpleNamespace

from meme_reaction.routes import Route, RouteStore, make_route_key
from meme_reaction.state import JsonState


def test_route_store_finds_exact_session_route(tmp_path):
    store = RouteStore(JsonState(tmp_path / "routes.json"))
    route = Route(
        platform="telegram",
        chat_id="-100",
        thread_id="42",
        user_id="u",
        user_name="U",
        timestamp=123.0,
    )
    store.save("telegram:-100:42", route, session_id="sid")

    assert store.find_exact("sid") == route
    assert store.find_exact("missing") is None


def test_make_route_key_uses_platform_chat_and_thread():
    source = SimpleNamespace(platform="Telegram", chat_id="-100", thread_id="42")
    assert make_route_key(source) == "telegram:-100:42"
