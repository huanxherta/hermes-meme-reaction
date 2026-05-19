"""Runtime meme selection."""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import MemeReactionConfig
from .index import MemeIndex, MemeItem


@dataclass(slots=True)
class MemeDecision:
    should_send: bool = False
    send_score: float = 0.0
    conversation_mood: str = ""
    wanted_tags: list[str] = field(default_factory=list)
    wanted_moods: list[str] = field(default_factory=list)
    intensity: float = 0.5
    reason: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MemeDecision":
        def _list(key: str) -> list[str]:
            raw = data.get(key) or []
            if isinstance(raw, str):
                return [raw]
            if isinstance(raw, list):
                return [str(x).strip() for x in raw if str(x).strip()]
            return []

        try:
            score = float(data.get("send_score", 0.0))
        except (TypeError, ValueError):
            score = 0.0
        try:
            intensity = float(data.get("intensity", 0.5))
        except (TypeError, ValueError):
            intensity = 0.5
        return cls(
            should_send=bool(data.get("should_send", False)),
            send_score=max(0.0, min(1.0, score)),
            conversation_mood=str(data.get("conversation_mood") or ""),
            wanted_tags=_list("wanted_tags"),
            wanted_moods=_list("wanted_moods"),
            intensity=max(0.0, min(1.0, intensity)),
            reason=str(data.get("reason") or ""),
        )

    def final_score(self, cfg: MemeReactionConfig) -> float:
        return self.send_score * cfg.trigger_weight

    def passes(self, cfg: MemeReactionConfig) -> bool:
        return self.should_send and self.final_score(cfg) >= cfg.threshold


def load_recent_history(path: str | Path, limit: int = 50) -> list[dict[str, Any]]:
    p = Path(path).expanduser()
    if not p.is_file():
        return []
    try:
        lines = p.read_text(encoding="utf-8").splitlines()[-limit:]
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for line in lines:
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            out.append(item)
    return out


def _norm_set(values: list[str]) -> set[str]:
    return {str(v).lower().strip() for v in values if str(v).strip()}


def _format_allowed(item: MemeItem, cfg: MemeReactionConfig) -> bool:
    suffix = Path(item.path).suffix.lower()
    if suffix == ".gif" and not cfg.selection.allow_gif:
        return False
    if suffix == ".webp" and not cfg.selection.allow_webp:
        return False
    if suffix in {".jpg", ".jpeg", ".png"} and not cfg.selection.allow_static_image:
        return False
    return True


def score_item(item: MemeItem, decision: MemeDecision, recent: list[dict[str, Any]]) -> float:
    wanted_tags = _norm_set(decision.wanted_tags)
    wanted_moods = _norm_set(decision.wanted_moods)
    item_tags = _norm_set(item.tags)
    item_moods = _norm_set(item.moods)
    safe_for = _norm_set(item.safe_for)
    avoid_for = _norm_set(item.avoid_for)
    mood_text = decision.conversation_mood.lower()

    score = 0.0
    score += 2.0 * len(wanted_tags & item_tags)
    score += 2.5 * len(wanted_moods & item_moods)
    score += 0.8 * sum(1 for s in safe_for if s and s in mood_text)
    score -= 2.5 * sum(1 for s in avoid_for if s and s in mood_text)
    score -= abs(float(item.intensity) - float(decision.intensity))

    recent_ids = [str(x.get("id") or "") for x in recent]
    if item.id in recent_ids[-10:]:
        score -= 3.0
    recent_tags: list[str] = []
    for entry in recent[-10:]:
        raw_tags = entry.get("tags") or []
        if isinstance(raw_tags, list):
            recent_tags.extend(str(x).lower() for x in raw_tags)
    overlap_recent = len(item_tags & set(recent_tags))
    if overlap_recent:
        score -= min(2.0, overlap_recent * 0.25)
    return score


def select_meme(
    decision: MemeDecision,
    index: MemeIndex,
    cfg: MemeReactionConfig,
    *,
    recent: list[dict[str, Any]] | None = None,
    rng: random.Random | None = None,
) -> MemeItem | None:
    if not decision.passes(cfg):
        return None
    recent = recent or []
    rng = rng or random.Random()
    candidates: list[tuple[float, MemeItem]] = []
    for item in index.existing_enabled():
        if not _format_allowed(item, cfg):
            continue
        score = score_item(item, decision, recent)
        if score > -1.5:
            candidates.append((score, item))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0], reverse=True)
    top = candidates[: cfg.selection.top_k]
    min_score = min(score for score, _ in top)
    weights = [max(0.05, score - min_score + 0.1) for score, _ in top]
    return rng.choices([item for _, item in top], weights=weights, k=1)[0]
