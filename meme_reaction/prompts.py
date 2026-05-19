"""Prompts for meme reaction LLM decisions and visual tagging."""

MOOD_DECISION_INSTRUCTIONS = """
你是 Hermes 的表情包发送判断器。根据用户消息、助手回复和近期氛围，判断是否应该在助手回复后追加一个表情包。

输出必须是 JSON，字段：
- should_send: boolean
- send_score: 0 到 1
- conversation_mood: 中文短语
- wanted_tags: 中文标签数组，3-6 个
- wanted_moods: 英文 mood key 数组，如 playful/comfort/confused/proud/serious/sad/angry
- intensity: 0 到 1，期望表情强度
- reason: 中文一句话理由

原则：
- 严肃事故、用户明显生气、隐私/安全敏感操作、失败排障高压阶段：低分或不发。
- 用户难过/疲惫时，只可低分选择低强度安慰类，不要搞笑冒犯。
- 日常调侃、任务完成、轻松吐槽、称赞、可爱互动：可以积极发送。
- 不要为了热闹强行发；表情包应该像自然的补一句。
""".strip()

VISION_TAGGING_INSTRUCTIONS = """
请识别这张表情包/贴纸的聊天用途。输出 JSON：
- caption: 一句话描述画面
- tags: 中文标签，3-8 个
- moods: 英文 mood key，如 playful/comfort/confused/proud/sad/angry/serious
- safe_for: 适合的中文聊天场景
- avoid_for: 不适合的中文聊天场景
- intensity: 0 到 1，情绪强度
不要编造人物身份；只描述表情和适用场景。
""".strip()

MOOD_DECISION_SCHEMA = {
    "type": "object",
    "properties": {
        "should_send": {"type": "boolean"},
        "send_score": {"type": "number", "minimum": 0, "maximum": 1},
        "user_mood": {"type": "string"},
        "assistant_mood": {"type": "string"},
        "relationship": {"type": "string"},
        "conversation_mood": {"type": "string"},
        "wanted_tags": {"type": "array", "items": {"type": "string"}},
        "wanted_moods": {"type": "array", "items": {"type": "string"}},
        "intensity": {"type": "number", "minimum": 0, "maximum": 1},
        "reason": {"type": "string"},
    },
    "required": ["should_send", "send_score", "conversation_mood", "wanted_tags", "wanted_moods", "intensity", "reason"],
}

VISION_TAGGING_SCHEMA = {
    "type": "object",
    "properties": {
        "caption": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string"}},
        "moods": {"type": "array", "items": {"type": "string"}},
        "safe_for": {"type": "array", "items": {"type": "string"}},
        "avoid_for": {"type": "array", "items": {"type": "string"}},
        "intensity": {"type": "number", "minimum": 0, "maximum": 1},
    },
    "required": ["caption", "tags", "moods", "safe_for", "avoid_for", "intensity"],
}
