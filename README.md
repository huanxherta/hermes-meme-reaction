# hermes-meme-reaction

Hermes Agent gateway 插件：LLM 判断后自动发送表情包/贴纸尾巴。

## 工作原理

1. **`pre_gateway_dispatch`** — 缓存当前精确路由（session_id + platform + chat_id + thread_id）到插件状态文件，跨重启持久化
2. **`post_llm_call`** — 助手回复完成后，只固定 route 和对话快照，然后投递后台任务，避免阻塞主回复链路
3. 后台任务用 `ctx.llm`（零配置，复用 gateway 自身 LLM）判断是否需要发送表情包
4. LLM 返回决策（是否发送、情绪、标签）→ 从索引中选取最匹配的表情包 → 通过 `ctx.dispatch_tool("send_message")` 跨平台发送

## 特性

- ✅ **零额外配置** — LLM 调用通过 `ctx.llm` 复用 gateway 的 provider/model/auth，不需要自己的 API key
- ✅ **全平台** — 通过 Hermes 统一 `send_message` 工具发送，支持 QQ、Telegram、Discord 等所有已连接平台
- ✅ **精确路由** — 只在匹配到当前 Hermes session 路由时发送，找不到就跳过，不猜最近聊天
- ✅ **路由持久化** — 缓存到 `~/.hermes/meme_reaction/routes.json`，网关重启后不丢失
- ✅ **冷却机制** — 同一群/频道内避免短时间内连续发送
- ✅ **LLM 决策** — 不是随机发图，而是根据对话情绪、语境精准匹配
- ✅ **后台执行** — LLM 决策和发送在后台线程里执行，不拖慢主回复
- ✅ **dry-run** — 可完整跑决策和选图但不实际发送，便于调试

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
  dry_run: false
  trigger_weight: 0.9
  threshold: 0.55
  cooldown_seconds: 90
  platforms:
    allowed: []
    denied: []
  targets:
    allowed: []
    denied: []
  debug:
    file_enabled: false
  llm:
    enabled: true
    timeout_seconds: 30
  libraries:
    - name: default
      path: ~/.hermes/memes
      recursive: true
      enabled: true
  import:
    allowed_roots: []
    use_vision: false
```

空的 allow/deny 列表表示不限制。例如 `platforms.allowed: []` 允许所有平台，`targets.allowed: []` 允许所有聊天目标，`import.allowed_roots: []` 允许 `meme_import` 扫描任意可读本地路径。即使目标不限制，自动发送仍然必须匹配当前 Hermes session 的精确路由；找不到精确路由时会跳过，不会用最近聊天兜底。

## Hermes 安全边界

这个仓库不修改 Hermes 本体代码。插件只通过 Hermes 插件 API 注册 hooks/tools，并把插件自己的运行状态写到 `~/.hermes/meme_reaction/`。

运行 `hermes plugins enable meme-reaction` 会修改 Hermes 用户配置用于启用插件；本插件代码不会写 `~/.hermes/hermes-agent/**`。

## 文件结构

```
hermes-meme-reaction/
├── meme_reaction/
│   ├── __init__.py       # 包入口：导出 register
│   ├── config.py         # 配置加载与数据类
│   ├── decision.py       # ctx.llm 结构化决策
│   ├── importer.py       # 表情包文件夹扫描 + Vision 标注
│   ├── index.py          # 索引结构 + 查询
│   ├── plugin.py         # Hermes register(ctx)
│   ├── prompts.py        # LLM 决策 prompt + JSON schema
│   ├── routes.py         # 路由模型与精确查找
│   ├── runtime.py        # hooks 编排
│   ├── sender.py         # dry-run / send_message 发送
│   ├── state.py          # 插件状态文件
│   ├── tools.py          # meme_import / meme_search
│   └── selector.py       # 基于决策选取最匹配的表情包
├── tests/
├── plugin.yaml           # 插件清单
└── README.md
```

## 致谢

- [Hermes Agent](https://github.com/NousResearch/hermes-agent) — 插件系统、gateway、ctx.llm

## License

MIT
