try:
    from .meme_reaction import register
except ImportError:
    from meme_reaction import register

__all__ = ["register"]
