"""Helpers for multimodal meme tagging."""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

from openai import AsyncOpenAI
from pydantic import BaseModel, ConfigDict, Field, model_validator
from PIL import Image, UnidentifiedImageError

from .config import MemeReactionConfig
from .prompts import VISION_TAGGING_INSTRUCTIONS

_STATIC_MIME_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
}
_ANIMATED_EXTENSIONS = {".gif", ".webp"}
DEFAULT_VISION_TIMEOUT_SECONDS = 30.0


def _normalize_text_list(value: Any) -> list[str]:
    if value is None:
        return []
    raw_values = value if isinstance(value, list) else [value]
    seen: set[str] = set()
    out: list[str] = []
    for raw in raw_values:
        text = str(raw or "").strip()
        key = text.lower()
        if not text or key in seen:
            continue
        seen.add(key)
        out.append(text)
    return out


class VisionTaggingResult(BaseModel):
    """Normalized structured output for uploaded meme recognition."""

    model_config = ConfigDict(extra="ignore")

    caption: str = ""
    tags: list[str] = Field(default_factory=list)
    moods: list[str] = Field(default_factory=list)
    safe_for: list[str] = Field(default_factory=list)
    avoid_for: list[str] = Field(default_factory=list)
    intensity: float = 0.5

    @model_validator(mode="before")
    @classmethod
    def _normalize(cls, value: Any) -> dict[str, Any]:
        data = dict(value or {})
        data["caption"] = str(data.get("caption") or "").strip()
        data["tags"] = _normalize_text_list(data.get("tags"))
        data["moods"] = _normalize_text_list(data.get("moods"))
        data["safe_for"] = _normalize_text_list(data.get("safe_for"))
        data["avoid_for"] = _normalize_text_list(data.get("avoid_for"))
        try:
            data["intensity"] = max(0.0, min(1.0, float(data.get("intensity", 0.5))))
        except (TypeError, ValueError):
            data["intensity"] = 0.5
        return data

    @classmethod
    def from_payload(cls, payload: dict[str, Any] | None) -> "VisionTaggingResult":
        return cls.model_validate(payload or {})


@dataclass(slots=True)
class ResolvedVisionSettings:
    provider: str = ""
    model: str = ""
    base_url: str = ""
    api_key: str = ""
    timeout_seconds: float = DEFAULT_VISION_TIMEOUT_SECONDS


def _encode_data_url(raw: bytes, mime_type: str) -> str:
    encoded = base64.b64encode(raw).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _animated_image_to_png_bytes(path: Path) -> bytes:
    with Image.open(path) as image:
        image.seek(0)
        frame = image.convert("RGBA")
        with BytesIO() as buffer:
            frame.save(buffer, format="PNG")
            return buffer.getvalue()


def prepare_vision_data_url(path: str | Path) -> str:
    """Encode an image for the OpenAI vision API.

    Animated GIF/WebP inputs are flattened to the first frame because the vision
    API only documents support for non-animated GIF inputs.
    """

    image_path = Path(path).expanduser().resolve()
    suffix = image_path.suffix.lower()
    mime_type = _STATIC_MIME_TYPES.get(suffix, "image/png")

    if suffix in _ANIMATED_EXTENSIONS:
        try:
            with Image.open(image_path) as image:
                if getattr(image, "is_animated", False):
                    return _encode_data_url(_animated_image_to_png_bytes(image_path), "image/png")
        except (OSError, UnidentifiedImageError):
            pass

    return _encode_data_url(image_path.read_bytes(), mime_type)


def _root_section(root: dict[str, Any], *keys: str) -> dict[str, Any]:
    current: Any = root
    for key in keys:
        if not isinstance(current, dict):
            return {}
        current = current.get(key)
    return current if isinstance(current, dict) else {}


def _pick_text(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _pick_float(*values: Any, default: float) -> float:
    for value in values:
        if value in {None, ""}:
            continue
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            continue
        if parsed > 0:
            return parsed
    return default


def resolve_vision_settings(cfg: MemeReactionConfig | None = None) -> ResolvedVisionSettings:
    root = getattr(cfg, "root_config", {}) or {}
    auxiliary_vision = _root_section(root, "auxiliary", "vision")
    host_model = _root_section(root, "model")
    plugin_vision = getattr(cfg, "vision", None)

    return ResolvedVisionSettings(
        provider=_pick_text(
            getattr(plugin_vision, "provider", ""),
            auxiliary_vision.get("provider"),
            host_model.get("provider"),
        ),
        model=_pick_text(
            getattr(plugin_vision, "model", ""),
            auxiliary_vision.get("model"),
        ),
        base_url=_pick_text(
            getattr(plugin_vision, "base_url", ""),
            auxiliary_vision.get("base_url"),
            host_model.get("base_url"),
            os.getenv("OPENAI_BASE_URL"),
        ),
        api_key=_pick_text(
            getattr(plugin_vision, "api_key", ""),
            auxiliary_vision.get("api_key"),
            host_model.get("api_key"),
            os.getenv("OPENAI_API_KEY"),
        ),
        timeout_seconds=_pick_float(
            getattr(plugin_vision, "timeout_seconds", None),
            auxiliary_vision.get("timeout"),
            default=DEFAULT_VISION_TIMEOUT_SECONDS,
        ),
    )


def resolve_vision_model(cfg: MemeReactionConfig | None = None) -> str:
    return resolve_vision_settings(cfg).model


def ensure_vision_settings(settings: ResolvedVisionSettings) -> None:
    if not str(settings.model or "").strip():
        raise RuntimeError(
            "未配置视觉模型：请在 Web 面板填写“视觉 Model”，或在 Hermes 的 auxiliary.vision.model 中配置"
        )
    if not str(settings.api_key or "").strip():
        raise RuntimeError(
            "未配置视觉 API Key：请在 Web 面板填写“视觉 API Key”，或在 Hermes 的 auxiliary.vision.api_key / model.api_key 中配置"
        )


def _build_openai_client(settings: ResolvedVisionSettings) -> AsyncOpenAI:
    kwargs: dict[str, Any] = {
        "api_key": settings.api_key,
        "timeout": settings.timeout_seconds,
    }
    if settings.base_url:
        kwargs["base_url"] = settings.base_url
    organization = os.getenv("OPENAI_ORG_ID")
    if organization:
        kwargs["organization"] = organization
    project = os.getenv("OPENAI_PROJECT_ID")
    if project:
        kwargs["project"] = project
    return AsyncOpenAI(**kwargs)


async def tag_meme_image(
    path: str | Path,
    *,
    cfg: MemeReactionConfig | None = None,
    client: AsyncOpenAI | None = None,
) -> VisionTaggingResult:
    """Run multimodal tagging on a local meme image."""

    settings = resolve_vision_settings(cfg)
    ensure_vision_settings(settings)
    own_client = client is None
    openai_client = client or _build_openai_client(settings)
    try:
        response = await openai_client.responses.parse(
            model=settings.model,
            instructions=VISION_TAGGING_INSTRUCTIONS,
            input=[
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": "识别这张表情包的聊天用途，只返回结构化结果。"},
                        {"type": "input_image", "image_url": prepare_vision_data_url(path), "detail": "low"},
                    ],
                }
            ],
            text_format=VisionTaggingResult,
        )
        parsed = response.output_parsed
        if parsed is None:
            raise RuntimeError("vision response did not contain structured output")
        return parsed
    finally:
        if own_client:
            await openai_client.close()
