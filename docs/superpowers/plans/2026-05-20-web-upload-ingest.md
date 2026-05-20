# Web Upload Ingest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有 NiceGUI 面板里加入上传图片/GIF、后台自动识别、手动批量导入正式表情库的完整链路。

**Architecture:** 把待导入工作区和视觉识别拆到独立模块，`server.py` 只做界面和编排；正式入库继续复用现有 `MemeIndex`、`stat_item`、sidecar 元数据格式。

**Tech Stack:** Python 3.14, NiceGUI, Pillow, OpenAI Python SDK 2.x, YAML/JSON persistence, unittest/pytest.

---

## File Structure

- Modify `meme_reaction/config.py`
- Create `meme_reaction/vision.py`
- Create `meme_reaction/web/uploads.py`
- Modify `meme_reaction/web/server.py`
- Modify `meme_reaction/web/presentation.py`
- Create `tests/test_web_uploads.py`
- Create `tests/test_vision.py`
- Modify `tests/test_meme_reaction_config.py`

### Task 1: Fix Config Reload Fallback

**Files:**
- Modify: `meme_reaction/config.py`
- Modify: `tests/test_meme_reaction_config.py`

- [ ] 写失败测试，覆盖 `hermes_cli` 不可导入时直接读取 `~/.hermes/config.yaml`
- [ ] 跑单测确认先失败
- [ ] 实现 YAML fallback
- [ ] 跑单测确认通过

### Task 2: Build Pending Upload Workspace

**Files:**
- Create: `meme_reaction/web/uploads.py`
- Create: `tests/test_web_uploads.py`

- [ ] 写失败测试，覆盖新增待导入项、标记识别成功/失败、删除条目
- [ ] 跑单测确认先失败
- [ ] 实现暂存目录和 `pending.json` 持久化
- [ ] 跑单测确认通过

### Task 3: Build Vision Tagger

**Files:**
- Create: `meme_reaction/vision.py`
- Create: `tests/test_vision.py`

- [ ] 写失败测试，覆盖结果标准化和动画首帧处理
- [ ] 跑单测确认先失败
- [ ] 实现 OpenAI 视觉识别封装
- [ ] 跑单测确认通过

### Task 4: Implement Import Into Library

**Files:**
- Modify: `meme_reaction/web/uploads.py`
- Modify: `tests/test_web_uploads.py`

- [ ] 写失败测试，覆盖移动文件、写 sidecar、更新 index、清理待导入项
- [ ] 跑单测确认先失败
- [ ] 实现正式导入逻辑
- [ ] 跑单测确认通过

### Task 5: Wire Web UI

**Files:**
- Modify: `meme_reaction/web/server.py`
- Modify: `meme_reaction/web/presentation.py`

- [ ] 加上传卡片、待导入列表、批量选择、重试、删除、导入按钮
- [ ] 接入后台识别任务和上传预览接口
- [ ] 保持现有鉴权与主题逻辑可用

### Task 6: Verify End To End

**Files:**
- Modify: `README.md` if behavior needs documentation

- [ ] 跑新增单测和现有 Web 相关测试
- [ ] 跑 `py_compile`
- [ ] 重启本地 dashboard
- [ ] 用 HTTP 探活确认页面仍能打开
