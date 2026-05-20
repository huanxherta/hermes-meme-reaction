# Web Upload Ingest Design

## Scope

只改这个插件仓库，不改 Hermes 本体，不改 `~/.hermes/hermes-agent/**`。

目标是在当前 NiceGUI 面板里增加一条新链路：

1. 直接上传图片或 GIF
2. 后台自动做多模态识别
3. 在待导入列表里展示识别结果
4. 用户手动确认并批量导入到正式表情库

## Goals

- 上传后立即返回，不阻塞页面交互
- 支持批量上传、批量重试、批量导入、单条删除
- 成功导入后只保留正式表情库里的那一份文件
- 识别失败不能把整批流程拖死
- 和现有 `MemeIndex` / `importer.py` / Web 鉴权共存

## Non-Goals

- 不做 Hermes 核心安装、插件管理、消息发送逻辑改造
- 不做复杂权限系统，只复用现有 Web 登录门禁
- 不做上传后自动入库，最后一步必须人工点导入

## Architecture

新增两个边界清晰的模块：

- `meme_reaction/web/uploads.py`
  负责待导入工作区，维护暂存目录、待导入元数据、批量删除、批量导入。
- `meme_reaction/vision.py`
  负责把图片送去多模态识别，并把结果标准化成插件已有字段：
  `caption / tags / moods / safe_for / avoid_for / intensity`。

`meme_reaction/web/server.py` 只负责 UI 和动作编排：

- 接收上传
- 把文件写入暂存区
- 调度后台识别任务
- 展示待导入列表
- 调用导入服务把选中项落到正式表情库

## Data Model

每个待导入项至少保存这些字段：

- `id`
- `library`
- `original_name`
- `staged_path`
- `content_type`
- `size`
- `status`
  可选值：`queued` / `processing` / `ready` / `failed`
- `error`
- `caption`
- `tags`
- `moods`
- `safe_for`
- `avoid_for`
- `intensity`
- `created_at`
- `updated_at`

待导入索引保存在插件自有状态目录，不写 Hermes 主配置。

## Recognition Flow

上传完成后：

1. Web 保存文件到插件暂存目录
2. 创建待导入记录，状态为 `queued`
3. 后台任务把状态切成 `processing`
4. 调用多模态识别
5. 成功则写回识别结果并标记 `ready`
6. 失败则记录错误并标记 `failed`

如果上传的是动画 GIF 或动画 WebP，识别时只取第一帧静态图送入视觉模型。正式入库仍保留原始文件。

## Import Flow

手动点导入时：

1. 校验目标库存在且启用
2. 把暂存文件移动到目标库目录
3. 为该素材写同名 sidecar JSON，内容来自识别结果
4. 生成或更新 `MemeIndex`
5. 从待导入列表删除已成功导入项

文件名冲突时自动加后缀，避免覆盖已有素材。

## Error Handling

- 缺少 OpenAI 凭据：上传可成功，识别项标记 `failed`
- 目标库不存在：导入动作失败，但不删待导入项
- 单条导入失败：返回逐条结果，不拖累其他选中项
- 暂存索引损坏：回退为空列表，不让整个面板崩掉

## Configuration

不新增强依赖配置面板字段。

视觉识别默认读取：

- `meme_reaction.llm.model`
- 若为空则退回 `OPENAI_VISION_MODEL`
- 再为空则用代码默认模型

OpenAI 凭据默认读取标准环境变量。这样先把功能做通，不把设置页继续塞胖。

## Testing

需要覆盖：

- 待导入工作区的增删改查
- 动画文件识别前帧提取
- 识别结果标准化
- 批量导入移动文件、写 sidecar、更新索引
- 配置加载在没有 `hermes_cli` 时仍能直接读 `~/.hermes/config.yaml`
