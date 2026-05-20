# hermes-meme-reaction

Hermes Agent gateway 插件：在助手回复完成后，按对话语气和上下文自动补一张表情包 / 贴纸尾巴。

## 它现在能做什么

- 复用 Hermes 宿主自己的 `ctx.llm`，判断这轮回复要不要发图
- 只走当前 Hermes session 对应的精确路由，不猜“最近一个聊天”
- 在后台线程里跑判定和发送，不阻塞主回复
- 扫描本地表情库，按标签 / 情绪 / 强度选图
- 提供 NiceGUI Web 面板，支持：
  - 控制开关、阈值、LLM 超时等运行设置
  - 浏览、搜索、编辑、启用/禁用正式表情库
  - 删除正式表情素材（删原图、删同名 sidecar、退索引）
  - 上传图片 / GIF 到待导入区
  - 自动跑视觉识别，人工确认后再正式入库
  - Web 登录保护与主题记忆

## 工作链路

1. `pre_gateway_dispatch`
   记录当前精确路由：`session_id + platform + chat_id + thread_id`
2. `post_llm_call`
   只保存当前 route 和对话快照，然后把表情判定任务丢进后台
3. 后台任务
   用 `ctx.llm` 做结构化判定，得到“发不发 / 想要什么情绪和标签”
4. 选图并发送
   从索引里挑最匹配的素材，通过 Hermes `send_message` 发出

## 安装

推荐优先使用 Hermes 官方插件安装方式：

```bash
hermes plugins install huanxherta/hermes-meme-reaction
hermes plugins enable meme-reaction
hermes gateway restart
```

如果你想手动控制目录：

```bash
cd ~/.hermes/plugins
git clone https://github.com/huanxherta/hermes-meme-reaction.git meme-reaction
hermes plugins enable meme-reaction
hermes gateway restart
```

## 快速开始

先在 `~/.hermes/config.yaml` 里启用插件并指向你的表情库：

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
  llm:
    enabled: true
    timeout_seconds: 30
  libraries:
    - name: default
      path: ~/.hermes/memes
      recursive: true
      enabled: true
```

然后导入现有表情库：

```text
meme_import(path="/path/to/memes", recursive=true)
```

或搜索已索引素材：

```text
meme_search(query="happy", tags=["庆祝", "开心"])
```

## Web 面板

启动：

```bash
python start_dashboard.py --host 127.0.0.1 --port 8000
```

面板主要有 5 页：

- `控制台`：插件即时状态和关键旋钮
- `表情库`：搜索、编辑、启用/禁用、删除正式素材
- `上传入库`：上传图片 / GIF，自动识别，手动确认入库
- `历史`：查看触发和发送记录
- `设置`：选图参数、视觉识别、Web 登录保护、表情库目录

### 上传入库怎么工作

1. 文件先进入插件自己的待导入工作区
2. 后台自动跑视觉识别
3. 面板展示识别结果：`caption / tags / moods / safe_for / avoid_for / intensity`
4. 你手动点“导入”或“导入选中”，才会真正进入正式表情库

说明：

- 动画 `GIF / WebP` 做视觉识别时只取第一帧送模型
- 正式入库时保留原文件，不会改成静态图
- 待导入项可以删；正式表情库里的素材也可以删

## 完整配置

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

  vision:
    provider: ""
    model: ""
    base_url: ""
    api_key: ""
    timeout_seconds: 30

  web:
    session_secret: ""
    auth:
      enabled: false
      username: admin
      password: change-me
    theme:
      default_mode: light

  libraries:
    - name: default
      path: ~/.hermes/memes
      recursive: true
      enabled: true

  import:
    allowed_roots: []
    use_vision: false
```

## 配置说明

### 平台 / 目标过滤

- `platforms.allowed: []` 表示不限制平台
- `targets.allowed: []` 表示不限制聊天目标
- 即使目标不限制，自动发送也仍然必须命中当前 Hermes session 的精确 route

### `import.allowed_roots`

空列表表示不限制。

如果配置了，它现在会同时限制：

- `meme_import` 手动导入
- Web 面板里保存表情库目录
- Web 面板上传入库时选择的目标表情库
- 正式入库落盘

也就是说，Web 不再能绕过这个边界。

### Web 鉴权

```yaml
meme_reaction:
  web:
    auth:
      enabled: true
      username: admin
      password: your-password
```

开启后，以下入口都会一起受保护：

- `/`
- 表情原图接口
- 待导入素材原图接口

`theme.default_mode` 只影响首次访问；之后浏览器会记住用户自己切换过的主题。

### 视觉识别配置继承

Web 上传识别用的是插件自己的视觉链路，不走 `ctx.llm`。

当前继承规则是：

1. 优先读 `meme_reaction.vision.*`
2. 留空时回退 Hermes 的 `auxiliary.vision.*`
3. 其中：
   - `model` 只回退到 `auxiliary.vision.model`
   - `api_key` 会回退到 `auxiliary.vision.api_key`，再回退 `model.api_key`
   - `base_url` 会回退到 `auxiliary.vision.base_url`，再回退 `model.base_url`
   - `provider` 会回退到 `auxiliary.vision.provider`，再回退 `model.provider`
4. 视觉模型仍然为空时，识别任务会直接报错，不会偷偷猜模型名

## 安全边界

这个仓库不修改 Hermes 本体代码。

插件只会：

- 通过 Hermes 插件 API 注册 hooks / tools
- 把自己的状态写到 `~/.hermes/meme_reaction/`
- 在需要时更新 Hermes 用户配置 `config.yaml`

它不会写：

- `~/.hermes/hermes-agent/**`

## 仓库结构

```text
hermes-meme-reaction/
├── meme_reaction/
│   ├── config.py
│   ├── decision.py
│   ├── importer.py
│   ├── index.py
│   ├── plugin.py
│   ├── prompts.py
│   ├── routes.py
│   ├── runtime.py
│   ├── selector.py
│   ├── sender.py
│   ├── state.py
│   ├── tools.py
│   ├── vision.py
│   └── web/
├── tests/
├── start_dashboard.py
├── plugin.yaml
└── README.md
```

## 致谢

- [Hermes Agent](https://github.com/NousResearch/hermes-agent)

## License

MIT
