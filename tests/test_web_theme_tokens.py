from meme_reaction.web.server import THEME_CSS


def test_light_theme_uses_soft_pink_blue_palette():
    assert "#f2a7b5" in THEME_CSS
    assert "#bfdcf4" in THEME_CSS
    assert "#4e4854" in THEME_CSS
    assert "#fbf8fb" in THEME_CSS
