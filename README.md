# hermes-meme-reaction

Hermes Agent gateway 插件：LLM 判断后自动发送表情包/贴纸尾巴。

## 工作原理

1. **`pre_gateway_dispatch`** — 缓存当前路由（platform + chat_id + thread_id）到文件，跨重启持久化
2. **`post_llm_call`** — 助手回复完成后，用 `ctx.llm`（零配置，复用 gateway 自身 LLM）判断是否需要发送表情包
3. LLM 返回决策（是否发送、情绪、标签）→ 从索引中选取最匹配的表情包 → 通过 `ctx.dispatch_tool("send_message")` 跨平台发送

## 特性

- ✅ **零额外配置** — LLM 调用通过 `ctx.llm` 复用 gateway 的 provider/model/auth，不需要自己的 API key
- ✅ **全平台** — 通过 Hermes 统一 `send_message` 工具发送，支持 QQ、Telegram、Discord 等所有已连接平台
- ✅ **路由持久化** — 缓存到 `~/.hermes/meme_reaction/routes.json`，网关重启后不丢失
- ✅ **冷却机制** — 同一群/频道内避免短时间内连续发送
- ✅ **LLM 决策** — 不是随机发图，而是根据对话情绪、语境精准匹配

## 安装

```bash
# 克隆到 Hermes 插件目录
cd ~/.hermes/plugins
git clone https://github.com/huanxherta/hermes-meme-reaction.git meme-reaction

# 启用插件
hermes plugins enable meme-reaction

# 重启网关让插件生效
hermes gateway restart
```

## 导入表情包

在对话中使用 `meme_import` 工具：

```
meme_import(path="/path/to/sticker/folder", recursive=true)
```

或用 `meme_search` 搜索已索引的表情包：

```
meme_search(query="happy", tags=["庆祝", "开心"])
```

## 配置

在 `~/.hermes/config.yaml` 中：

```yaml
plugins:
  enabled:
    - meme-reaction

meme_reaction:
  enabled: true
  trigger_weight: 0.9
  threshold: 0.55
  cooldown_seconds: 90
  llm:
    enabled: true
    timeout_seconds: 30
  libraries:
    - name: default
      path: ~/.hermes/memes
      recursive: true
      enabled: true
  platforms:
    allowed: ["qqonebot", "telegram", "discord"]
```

## 文件结构

```
hermes-meme-reaction/
├── meme_reaction/
│   ├── __init__.py       # 主入口：hooks + 发送逻辑
│   ├── config.py         # 配置加载与数据类
│   ├── importer.py       # 表情包文件夹扫描 + Vision 标注
│   ├── index.py          # 索引结构 + 查询
│   ├── prompts.py        # LLM 决策 prompt + JSON schema
│   └ selector.py         # 基于决策选取最匹配的表情包
├── tests/
├── plugin.yaml           # 插件清单
└── README.md
```

## 致谢

- [Hermes Agent](https://github.com/NousResearch/hermes-agent) — 插件系统、gateway、ctx.llm

## License

MIT