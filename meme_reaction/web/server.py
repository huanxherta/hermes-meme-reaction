"""NiceGUI dashboard for the Hermes Meme Reaction plugin."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from fastapi import HTTPException, Query, Request
from fastapi.responses import FileResponse
from nicegui import app as nicegui_app
from nicegui import background_tasks
from nicegui import ui
from nicegui.events import MultiUploadEventArguments

sys.path.insert(0, str(Path(__file__).parent.parent.parent.resolve()))

from meme_reaction.config import MemeLibraryConfig, get_hermes_config_path, load_meme_reaction_config, load_root_config_file, save_root_config_file
from meme_reaction.importer import import_libraries
from meme_reaction.index import MemeIndex, MemeItem, delete_meme_item
from meme_reaction.vision import tag_meme_image
from meme_reaction.web.presentation import (
    build_libraries_payload,
    build_runtime_payload,
    build_selection_payload,
    build_threshold_payload,
    build_vision_payload,
    build_web_payload,
    find_disallowed_library,
    filter_memes,
    join_csv,
    merge_config_payload,
    split_csv,
)
from meme_reaction.web.security import AUTH_STORAGE_KEY, THEME_STORAGE_KEY, USERNAME_STORAGE_KEY, build_storage_secret, is_request_authenticated, is_web_auth_configured, normalize_theme_mode, verify_web_login
from meme_reaction.web.uploads import workspace_for_config


THEME_CSS = """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
    :root {
        --bg: linear-gradient(145deg, #fbf8fb 0%, #f6f2f5 42%, #edf4fb 100%);
        --panel: rgba(255, 255, 255, 0.88);
        --panel-strong: rgba(255, 255, 255, 0.96);
        --border: rgba(184, 169, 182, 0.20);
        --text: #4e4854;
        --muted: #8e8793;
        --accent: #f2a7b5;
        --accent-2: #d9b4f0;
        --accent-3: #bfdcf4;
        --chip: rgba(242, 167, 181, 0.16);
        --field-bg: rgba(255, 255, 255, 0.94);
        --meta-bg: rgba(244, 236, 241, 0.84);
        --soft-bg: rgba(236, 242, 249, 0.72);
        --menu-bg: rgba(255, 255, 255, 0.98);
        --thumb-bg: rgba(191, 220, 244, 0.20);
        --shadow: 0 18px 40px rgba(188, 174, 192, 0.16);
        --accent-strong: #eb8fa4;
        --gold: #f3c96b;
    }

    body.body--dark {
        --bg: linear-gradient(135deg, #111925 0%, #182332 100%);
        --panel: rgba(20, 30, 42, 0.88);
        --panel-strong: rgba(18, 27, 38, 0.96);
        --border: rgba(162, 184, 204, 0.14);
        --text: #edf2f7;
        --muted: #aeb9c5;
        --accent: #f08a74;
        --accent-2: #d78ab4;
        --accent-3: #7fa2f2;
        --chip: rgba(240, 138, 116, 0.18);
        --field-bg: rgba(13, 22, 31, 0.86);
        --meta-bg: rgba(255, 255, 255, 0.05);
        --soft-bg: rgba(255, 255, 255, 0.04);
        --menu-bg: rgba(16, 24, 35, 0.98);
        --thumb-bg: rgba(255, 255, 255, 0.04);
        --shadow: 0 20px 48px rgba(0, 0, 0, 0.24);
    }

    body {
        background: var(--bg) !important;
        color: var(--text) !important;
        font-family: 'Outfit', -apple-system, BlinkMacSystemFont, sans-serif !important;
    }

    .nicegui-content {
        width: min(1320px, calc(100vw - 32px));
        margin: 0 auto;
        padding: 28px 0 72px;
    }

    .q-card {
        background: var(--panel) !important;
        backdrop-filter: blur(16px) !important;
        border: 1px solid var(--border) !important;
        border-radius: 18px !important;
        box-shadow: var(--shadow) !important;
    }

    .hero-panel {
        background:
            radial-gradient(circle at top right, rgba(242, 167, 181, 0.20), transparent 28%),
            radial-gradient(circle at bottom left, rgba(191, 220, 244, 0.22), transparent 34%),
            linear-gradient(180deg, var(--panel-strong), var(--panel)) !important;
        border: 1px solid var(--border) !important;
    }

    .surface-card {
        background: linear-gradient(180deg, var(--panel-strong), var(--panel)) !important;
    }

    .q-tab {
        font-weight: 700 !important;
        border-radius: 12px !important;
        color: var(--muted) !important;
    }

    .q-tab__label,
    .q-tab .q-icon,
    .q-btn__content,
    .q-btn .q-icon,
    .q-item__label,
    .q-item__section,
    .q-field__native,
    .q-field__input,
    .q-field__label,
    .q-field__marginal,
    .q-select__dropdown-icon,
    .q-toggle__label,
    .q-checkbox__label,
    .q-radio__label,
    .q-slider__pin-text,
    .q-menu,
    .q-dialog,
    .q-card__section,
    .q-notification__message,
    .q-field__messages,
    .q-field__bottom,
    .q-field__prefix,
    .q-field__suffix {
        color: var(--text) !important;
    }

    input::placeholder,
    textarea::placeholder {
        color: var(--muted) !important;
        opacity: 1 !important;
    }

    .q-menu .q-item,
    .q-virtual-scroll__content .q-item {
        color: var(--text) !important;
        background: var(--menu-bg) !important;
    }

    .q-menu .q-item.q-manual-focusable--focused,
    .q-menu .q-item--active {
        background: rgba(242, 167, 181, 0.12) !important;
        color: var(--accent) !important;
    }

    .q-tab--active {
        background: linear-gradient(135deg, rgba(242, 167, 181, 0.16), rgba(191, 220, 244, 0.20)) !important;
        color: var(--text) !important;
    }

    .q-btn {
        text-transform: none !important;
        border-radius: 12px !important;
        font-weight: 700 !important;
    }

    .q-btn.bg-accent,
    .q-btn.bg-primary,
    .q-btn[color="accent"],
    .q-btn[color="primary"] {
        box-shadow: 0 10px 22px rgba(242, 167, 181, 0.28) !important;
    }

    .hero-title {
        font-size: clamp(1.8rem, 2.4vw, 2.8rem);
        line-height: 1.05;
        font-weight: 800;
        letter-spacing: -0.03em;
    }

    .hero-subtitle {
        color: var(--muted) !important;
        max-width: 62ch;
    }

    .hero-kicker {
        color: var(--accent-strong);
        font-size: 0.8rem;
        letter-spacing: 0.16em;
        text-transform: uppercase;
        font-weight: 800;
    }

    .stat-card {
        background: linear-gradient(180deg, var(--panel-strong), var(--panel)) !important;
        border: 1px solid var(--border) !important;
    }

    .stat-icon {
        width: 40px;
        height: 40px;
        border-radius: 12px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        color: white;
        background: linear-gradient(135deg, var(--accent), var(--accent-2));
        box-shadow: 0 10px 24px rgba(242, 167, 181, 0.26);
    }

    .stat-value {
        font-size: 1.9rem;
        font-weight: 800;
        letter-spacing: -0.04em;
    }

    .stat-label {
        color: var(--muted);
        font-size: 0.78rem;
        text-transform: uppercase;
        letter-spacing: 0.12em;
    }

    .section-title {
        font-size: 1.1rem;
        font-weight: 800;
        letter-spacing: -0.02em;
    }

    .section-hint {
        color: var(--muted) !important;
        font-size: 0.9rem;
    }

    .toolbar-card .q-field,
    .surface-card .q-field,
    .dialog-card .q-field {
        background: var(--field-bg);
        border-radius: 14px;
    }

    .toolbar-card .q-field__control,
    .surface-card .q-field__control,
    .dialog-card .q-field__control {
        min-height: 52px !important;
    }

    .toolbar-card .q-field__control,
    .surface-card .q-field__control,
    .dialog-card .q-field__control,
    .toolbar-card .q-field__control:before,
    .surface-card .q-field__control:before,
    .dialog-card .q-field__control:before,
    .toolbar-card .q-field__control:after,
    .surface-card .q-field__control:after,
    .dialog-card .q-field__control:after {
        color: var(--text) !important;
        border-color: rgba(184, 169, 182, 0.24) !important;
    }

    .toolbar-grid {
        display: grid;
        grid-template-columns: minmax(260px, 2fr) repeat(3, minmax(140px, 1fr));
        gap: 12px;
        align-items: center;
    }

    .overview-strip {
        display: grid;
        grid-template-columns: 1.35fr 1fr;
        gap: 16px;
    }

    .meter-track {
        width: 100%;
        height: 14px;
        border-radius: 999px;
        overflow: hidden;
        background: rgba(191, 220, 244, 0.26);
    }

    .meter-fill {
        height: 100%;
        border-radius: 999px;
    }

    .meme-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(272px, 1fr));
        gap: 1.1rem;
    }

    .meme-card {
        overflow: hidden;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }

    .meme-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 22px 40px rgba(199, 184, 201, 0.22);
    }

    .meme-thumb {
        width: 100%;
        aspect-ratio: 1 / 1;
        object-fit: cover;
        background: var(--thumb-bg);
    }

    .meme-meta {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 8px;
    }

    .meta-tile {
        border-radius: 14px;
        background: var(--meta-bg);
        padding: 10px 12px;
    }

    .meta-label {
        color: var(--muted) !important;
        font-size: 0.72rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
    }

    .meta-value {
        font-weight: 700;
        margin-top: 3px;
    }

    .chip-button {
        background: linear-gradient(135deg, rgba(242, 167, 181, 0.16), rgba(255, 255, 255, 0.94)) !important;
        color: var(--text) !important;
        border-radius: 999px !important;
        padding: 2px 8px !important;
        min-height: auto !important;
        border: 1px solid rgba(242, 167, 181, 0.24) !important;
    }

    .chip {
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
        padding: 0.24rem 0.55rem;
        border-radius: 999px;
        background: linear-gradient(135deg, rgba(242, 167, 181, 0.18), rgba(255, 255, 255, 0.94));
        color: var(--text);
        font-size: 0.72rem;
        font-weight: 700;
        border: 1px solid rgba(242, 167, 181, 0.18);
    }

    .chip-muted {
        background: linear-gradient(135deg, rgba(191, 220, 244, 0.26), rgba(255, 255, 255, 0.96));
        color: #647588;
        border-color: rgba(191, 220, 244, 0.26);
    }

    .chip-soft {
        background: linear-gradient(135deg, rgba(217, 180, 240, 0.22), rgba(255, 255, 255, 0.96));
        color: #75657f;
        border-color: rgba(217, 180, 240, 0.22);
    }

    .history-card {
        border-left: 4px solid rgba(242, 167, 181, 0.46);
    }

    .history-stack {
        display: grid;
        gap: 14px;
    }

    .status-dot {
        width: 12px;
        height: 12px;
        border-radius: 999px;
        display: inline-block;
        background: #d9dbe3;
        box-shadow: 0 0 0 4px rgba(242, 167, 181, 0.10);
    }

    .status-dot.on {
        background: var(--accent);
    }

    .path-text {
        font-family: 'JetBrains Mono', ui-monospace, monospace;
        word-break: break-all;
    }

    .input-field textarea,
    .input-field input {
        font-family: 'JetBrains Mono', ui-monospace, monospace;
    }

    .dialog-card {
        background: linear-gradient(180deg, var(--panel-strong), var(--panel)) !important;
    }

    .login-shell {
        min-height: calc(100vh - 64px);
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 12px 0;
    }

    .login-card {
        width: min(430px, calc(100vw - 24px));
    }

    @media (max-width: 1100px) {
        .toolbar-grid,
        .overview-strip {
            grid-template-columns: 1fr;
        }
    }
</style>
"""


def _safe_json_lines(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    items: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                text = line.strip()
                if not text:
                    continue
                try:
                    item = json.loads(text)
                except json.JSONDecodeError:
                    continue
                if isinstance(item, dict):
                    items.append(item)
    except OSError:
        return []
    items.reverse()
    return items


def _format_timestamp(raw: Any) -> str:
    try:
        ts = float(raw)
    except (TypeError, ValueError):
        return "未知时间"
    return datetime.fromtimestamp(ts, tz=timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")


def _human_size(size: int) -> str:
    value = float(size or 0)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024.0:
            return f"{value:.1f} {unit}"
        value /= 1024.0
    return f"{value:.1f} TB"


def _join_nonempty(values: list[str]) -> str:
    return ", ".join([v for v in values if str(v).strip()])


class DashboardState:
    def __init__(self) -> None:
        self.cfg = load_meme_reaction_config()
        self.index = MemeIndex.load(self.cfg.index_path)
        self.history = _safe_json_lines(self.cfg.history_path)
        self.pending_uploads = workspace_for_config(self.cfg).list_items()
        self.search_query = ""
        self.search_tag = ""
        self.search_library = ""
        self.search_enabled = ""
        self.library_page = 1
        self.library_limit = 12
        self.allowed_platforms = join_csv(self.cfg.allowed_platforms)
        self.denied_platforms = join_csv(self.cfg.denied_platforms)
        self.allowed_targets = join_csv(self.cfg.targets.allowed)
        self.denied_targets = join_csv(self.cfg.targets.denied)

    def refresh(self) -> None:
        self.cfg = load_meme_reaction_config()
        self.index = MemeIndex.load(self.cfg.index_path)
        self.history = _safe_json_lines(self.cfg.history_path)
        self.pending_uploads = workspace_for_config(self.cfg).list_items()
        self.allowed_platforms = join_csv(self.cfg.allowed_platforms)
        self.denied_platforms = join_csv(self.cfg.denied_platforms)
        self.allowed_targets = join_csv(self.cfg.targets.allowed)
        self.denied_targets = join_csv(self.cfg.targets.denied)


state = DashboardState()


@nicegui_app.get("/api/memes/raw")
def get_raw_meme(request: Request, path: str = Query(...)) -> FileResponse:
    resolved_path = Path(path).expanduser().resolve()
    cfg = load_meme_reaction_config()
    if not is_request_authenticated(request, cfg):
        raise HTTPException(status_code=401, detail="Authentication required")
    index = MemeIndex.load(cfg.index_path)

    allowed = any(Path(item.path).expanduser().resolve() == resolved_path for item in index.items)
    if not allowed:
        raise HTTPException(status_code=403, detail="Forbidden path")
    if not resolved_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(resolved_path)


@nicegui_app.get("/api/uploads/raw")
def get_raw_upload(request: Request, item_id: str = Query(...)) -> FileResponse:
    cfg = load_meme_reaction_config()
    if not is_request_authenticated(request, cfg):
        raise HTTPException(status_code=401, detail="Authentication required")
    workspace = workspace_for_config(cfg)
    item = workspace.get_item(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Upload item not found")
    staged_path = Path(item.staged_path).expanduser().resolve()
    if not staged_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(staged_path)


ui.add_head_html(THEME_CSS, shared=True)


@ui.page("/")
def index_page() -> None:
    state.refresh()
    initial_theme_mode = normalize_theme_mode(
        nicegui_app.storage.user.get(THEME_STORAGE_KEY),
        state.cfg.web.theme.default_mode,
    )
    dark_mode = ui.dark_mode(value=initial_theme_mode == "dark")

    page_refs: dict[str, Any] = {}
    edit_dialog_state: dict[str, Any] = {"item": None}
    detail_dialog_state: dict[str, Any] = {"log": None}
    theme_button_ref: dict[str, Any] = {}
    library_row_refs: list[dict[str, Any]] = []
    upload_ref: dict[str, Any] = {}
    selected_upload_ids: set[str] = set()

    def notify_saved(title: str, message: str) -> None:
        ui.notify(f"{title}: {message}", type="positive")

    def sync_theme_button() -> None:
        button = theme_button_ref.get("button")
        if button is None:
            return
        button.props(f'icon={"light_mode" if dark_mode.value else "dark_mode"}')

    def set_theme_mode(mode: str, *, persist: bool = True) -> None:
        normalized = normalize_theme_mode(mode, state.cfg.web.theme.default_mode)
        dark_mode.value = normalized == "dark"
        if persist:
            nicegui_app.storage.user[THEME_STORAGE_KEY] = normalized
        sync_theme_button()

    def toggle_theme() -> None:
        next_mode = "light" if dark_mode.value else "dark"
        set_theme_mode(next_mode)

    def current_theme_mode() -> str:
        return "dark" if dark_mode.value else "light"

    def current_user_authenticated() -> bool:
        if not state.cfg.web.auth.enabled:
            return True
        return bool(nicegui_app.storage.user.get(AUTH_STORAGE_KEY))

    def logout() -> None:
        nicegui_app.storage.user[AUTH_STORAGE_KEY] = False
        nicegui_app.storage.user[USERNAME_STORAGE_KEY] = ""
        ui.navigate.to("/")

    def save_index() -> None:
        state.index.save(state.cfg.index_path)
        state.refresh()

    def save_config_update(update: dict[str, object], success_message: str) -> None:
        config_path = get_hermes_config_path()
        existing = load_root_config_file(config_path)
        payload = merge_config_payload(existing, update)
        save_root_config_file(payload, config_path)
        state.refresh()
        notify_saved("已保存", f"{success_message} ({config_path})")

    def render_auth_config_error() -> None:
        with ui.element("div").classes("login-shell w-full"):
            with ui.card().classes("hero-panel login-card p-6"):
                with ui.row().classes("w-full items-center justify-between"):
                    ui.label("Web 鉴权配置不完整").classes("section-title")
                    theme_button_ref["button"] = ui.button(icon="dark_mode", on_click=toggle_theme).props("flat round")
                sync_theme_button()
                ui.label("你已经开启了面板登录保护，但没有同时配置用户名和密码。").classes("section-hint mt-3")
                ui.label(f"请先修改 {get_hermes_config_path()} 里的 meme_reaction.web.auth.username / password。").classes("section-hint")

    def render_login_gate() -> None:
        with ui.element("div").classes("login-shell w-full"):
            with ui.card().classes("hero-panel login-card p-6"):
                with ui.row().classes("w-full items-center justify-between"):
                    with ui.column().classes("gap-1"):
                        ui.label("Hermes Meme 控制中心").classes("section-title")
                        ui.label("这个页面已启用登录保护。").classes("section-hint")
                    theme_button_ref["button"] = ui.button(icon="dark_mode", on_click=toggle_theme).props("flat round")
                sync_theme_button()
                login_username = ui.input("用户名").classes("w-full mt-4")
                login_password = ui.input("密码", password=True, password_toggle_button=True).classes("w-full")
                login_hint = ui.label("").classes("section-hint min-h-[20px]")

                def submit_login() -> None:
                    if verify_web_login(state.cfg, str(login_username.value or ""), str(login_password.value or "")):
                        nicegui_app.storage.user[AUTH_STORAGE_KEY] = True
                        nicegui_app.storage.user[USERNAME_STORAGE_KEY] = state.cfg.web.auth.username
                        nicegui_app.storage.user[THEME_STORAGE_KEY] = current_theme_mode()
                        ui.navigate.to("/")
                        return
                    login_hint.text = "用户名或密码错误。"
                    ui.notify("登录失败", type="negative")

                with ui.row().classes("w-full justify-end mt-4"):
                    ui.button("登录", icon="login", on_click=submit_login).props("unelevated color=accent")

    if state.cfg.web.auth.enabled and not is_web_auth_configured(state.cfg):
        render_auth_config_error()
        return

    if state.cfg.web.auth.enabled and not current_user_authenticated():
        render_login_gate()
        return

    def run_importer() -> None:
        ui.notify("开始扫描表情库...", type="info")
        import_libraries(state.cfg)
        state.refresh()
        render_all()
        ui.notify("扫描完成", type="positive")

    def open_meme_editor(item: MemeItem) -> None:
        edit_dialog_state["item"] = item
        edit_dialog.open()
        edit_caption.value = item.caption
        edit_tags.value = join_csv(item.tags)
        edit_moods.value = join_csv(item.moods)
        edit_safe_for.value = join_csv(item.safe_for)
        edit_avoid_for.value = join_csv(item.avoid_for)
        edit_enabled.value = item.enabled
        edit_intensity.value = item.intensity
        edit_intensity_label.text = f"{item.intensity:.2f}"
        edit_path.text = item.path
        edit_library.text = item.library
        edit_size.text = _human_size(item.size)
        edit_thumb.set_source(f"/api/memes/raw?path={item.path}")

    def save_meme_editor() -> None:
        item = edit_dialog_state.get("item")
        if not isinstance(item, MemeItem):
            return
        item.caption = (edit_caption.value or "").strip()
        item.tags = split_csv(edit_tags.value)
        item.moods = split_csv(edit_moods.value)
        item.safe_for = split_csv(edit_safe_for.value)
        item.avoid_for = split_csv(edit_avoid_for.value)
        item.enabled = bool(edit_enabled.value)
        try:
            item.intensity = float(edit_intensity.value or 0.5)
        except (TypeError, ValueError):
            item.intensity = 0.5
        state.index.save(state.cfg.index_path)
        state.refresh()
        render_library()
        render_history()
        edit_dialog.close()
        notify_saved("已保存", "表情包元数据已经更新")

    def open_history_detail(log: dict[str, Any]) -> None:
        detail_dialog_state["log"] = log
        detail_reason.text = str((log.get("decision") or {}).get("reason") or "未提供理由")
        detail_target.text = str(log.get("target") or "未知目标")
        detail_time.text = _format_timestamp(log.get("ts"))
        detail_score.text = f"{float((log.get('decision') or {}).get('final_score') or 0):.2f}"
        detail_meme_name.text = Path(str(log.get("path") or "")).name or "表情包"
        detail_meme_path.text = str(log.get("path") or "-")
        detail_thumb.set_source(f"/api/memes/raw?path={log.get('path')}")
        detail_chat.clear()
        user_message = str(log.get("user_message") or "").strip()
        assistant_message = str(log.get("assistant_response") or "").strip()
        if user_message:
            with detail_chat:
                ui.label("用户").classes("chip")
                ui.markdown(user_message).classes("q-mt-xs")
        if assistant_message:
            with detail_chat:
                ui.label("助手").classes("chip chip-muted q-mt-md")
                ui.markdown(assistant_message).classes("q-mt-xs")
        detail_tags.clear()
        for tag in list((log.get("tags") or [])) + list((log.get("moods") or [])):
            with detail_tags:
                ui.label(str(tag)).classes("chip")
        detail_dialog.open()

    def render_stats() -> None:
        if not page_refs:
            return
        page_refs["stat_memes"].text = str(len(state.index.items))
        page_refs["stat_active"].text = str(sum(1 for item in state.index.items if item.enabled))
        page_refs["stat_history"].text = str(len(state.history))
        page_refs["stat_libraries"].text = str(len({item.library for item in state.index.items}))
        page_refs["path_index"].text = str(state.cfg.index_path)
        page_refs["path_routes"].text = str(state.cfg.routes_path)
        page_refs["path_history"].text = str(state.cfg.history_path)
        page_refs["status_text"].text = "已开启" if state.cfg.enabled else "已关闭"
        page_refs["status_indicator"].style(
            f"background: {'var(--accent)' if state.cfg.enabled else '#cfd6dd'};"
        )
        page_refs["switch_enabled"].value = state.cfg.enabled
        page_refs["switch_dry_run"].value = state.cfg.dry_run
        page_refs["cooldown"].value = state.cfg.cooldown_seconds
        page_refs["trigger_weight"].value = state.cfg.trigger_weight
        page_refs["threshold"].value = state.cfg.threshold
        page_refs["trigger_text"].text = f"{state.cfg.trigger_weight:.2f}"
        page_refs["threshold_text"].text = f"{state.cfg.threshold:.2f}"
        page_refs["trigger_bar"].style(f"width: {state.cfg.trigger_weight * 100:.0f}%")
        page_refs["threshold_bar"].style(f"width: {state.cfg.threshold * 100:.0f}%")

    def refresh_decision_preview() -> None:
        if not page_refs:
            return
        page_refs["trigger_text"].text = f"{state.cfg.trigger_weight:.2f}"
        page_refs["threshold_text"].text = f"{state.cfg.threshold:.2f}"
        page_refs["trigger_bar"].style(f"width: {state.cfg.trigger_weight * 100:.0f}%")
        page_refs["threshold_bar"].style(f"width: {state.cfg.threshold * 100:.0f}%")

    def render_library() -> None:
        if not page_refs:
            return
        container = page_refs["library_container"]
        container.clear()
        items = filter_memes(
            state.index.items,
            query=state.search_query,
            tag=state.search_tag,
            library=state.search_library,
            enabled=state.search_enabled,
        )
        total = len(items)
        pages = max(1, (total + state.library_limit - 1) // state.library_limit)
        state.library_page = min(max(1, state.library_page), pages)
        page_start = (state.library_page - 1) * state.library_limit
        page_items = items[page_start : page_start + state.library_limit]

        page_refs["library_count"].text = f"{total} 张"
        page_refs["library_page_label"].text = f"{state.library_page} / {pages}"
        page_refs["library_prev"].props(f"disable={'true' if state.library_page <= 1 else 'false'}")
        page_refs["library_next"].props(f"disable={'true' if state.library_page >= pages else 'false'}")

        if not page_items:
            with container:
                with ui.card().classes("surface-card w-full p-8 text-center"):
                    ui.icon("photo_library", size="3rem").classes("opacity-40")
                    ui.label("没有找到符合条件的表情包").classes("mt-3 text-lg font-bold")
                    ui.label("调整关键字、内容标签、情绪标签或库筛选后再试。").classes("section-hint")
            return

        with container:
            for item in page_items:
                with ui.card().classes("surface-card meme-card"):
                    ui.image(f"/api/memes/raw?path={item.path}").classes("meme-thumb")
                    with ui.column().classes("p-4 gap-3"):
                        with ui.row().classes("w-full items-start justify-between gap-2"):
                            with ui.column().classes("gap-1"):
                                ui.label(item.caption or Path(item.path).name).classes("font-bold text-base")
                                ui.label(item.library).classes("section-hint")
                            ui.label("已启用" if item.enabled else "已禁用").classes("chip" if item.enabled else "chip chip-muted")
                        with ui.row().classes("gap-1 flex-wrap"):
                            for tag in item.tags[:4]:
                                ui.button(
                                    tag,
                                    on_click=lambda _=None, current=tag: apply_tag_filter(current),
                                ).props("flat dense no-caps").classes("chip-button")
                            if len(item.tags) > 4:
                                ui.label(f"+{len(item.tags) - 4}").classes("chip chip-muted")
                        with ui.row().classes("gap-1 flex-wrap"):
                            for mood in item.moods[:3]:
                                ui.label(mood).classes("chip chip-soft")
                        with ui.element("div").classes("meme-meta"):
                            with ui.element("div").classes("meta-tile"):
                                ui.label("激烈度").classes("meta-label")
                                ui.label(f"{item.intensity:.2f}").classes("meta-value")
                            with ui.element("div").classes("meta-tile"):
                                ui.label("大小").classes("meta-label")
                                ui.label(_human_size(item.size)).classes("meta-value path-text")
                        with ui.row().classes("w-full justify-between items-center pt-2"):
                            ui.label(item.relpath or Path(item.path).name).classes("path-text section-hint")
                            with ui.row().classes("gap-1"):
                                ui.button(icon="edit", on_click=lambda current=item: open_meme_editor(current)).props("flat round dense")
                                ui.button(icon="delete", on_click=lambda current=item: confirm_delete_library_item(current)).props("flat round dense color=negative")
                                ui.switch(value=item.enabled, on_change=lambda e, current=item: toggle_meme_enabled(current, bool(e.value))).props("dense")

    def render_history() -> None:
        if not page_refs:
            return
        container = page_refs["history_container"]
        container.clear()
        history_query = state.search_query.strip().lower()
        entries = state.history
        if history_query:
            entries = [
                entry for entry in entries
                if history_query in " ".join(
                    [str(entry.get("path") or ""), str(entry.get("target") or ""), str(entry.get("user_message") or ""), str(entry.get("assistant_response") or "")]
                ).lower()
            ]
        page_refs["history_count"].text = f"{len(entries)} 条"
        if not entries:
            with container:
                with ui.card().classes("surface-card w-full p-8 text-center"):
                    ui.icon("history", size="3rem").classes("opacity-40")
                    ui.label("暂无发送历史").classes("mt-3 text-lg font-bold")
                    ui.label("当插件触发表情包发送后，这里会记录决策、目标和素材路径。").classes("section-hint")
            return
        with container:
            for log in entries[:40]:
                decision = log.get("decision") or {}
                score = float(decision.get("final_score") or 0.0)
                with ui.card().classes("surface-card history-card p-4"):
                    with ui.row().classes("w-full items-center justify-between gap-3"):
                        with ui.row().classes("items-center gap-3"):
                            ui.image(f"/api/memes/raw?path={log['path']}").classes("w-16 h-16 rounded-xl object-cover")
                            with ui.column().classes("gap-1"):
                                ui.label(Path(str(log.get("path") or "")).name or "表情包").classes("font-bold")
                                ui.label(str(log.get("target") or "-")).classes("path-text section-hint")
                                ui.label(_format_timestamp(log.get("ts"))).classes("section-hint")
                        with ui.column().classes("items-end gap-1"):
                            ui.label(f"{score:.2f}").classes("stat-value")
                            ui.label(str(decision.get("reason") or "未提供理由")).classes("section-hint text-right")
                        ui.button("详情", icon="visibility", on_click=lambda current=log: open_history_detail(current)).props("outline")

    def render_libraries() -> None:
        if not page_refs:
            return
        container = page_refs["library_rows"]
        container.clear()
        library_row_refs.clear()
        with container:
            for idx, lib in enumerate(state.cfg.libraries):
                with ui.card().classes("surface-card w-full p-4"):
                    with ui.row().classes("w-full items-start gap-3"):
                        name_input = ui.input("目录名称", value=lib.name).classes("w-48")
                        path_input = ui.input("路径", value=str(lib.path)).classes("flex-grow")
                        recursive_switch = ui.switch("递归", value=lib.recursive)
                        enabled_switch = ui.switch("启用", value=lib.enabled)
                        library_row_refs.append(
                            {
                                "name": name_input,
                                "path": path_input,
                                "recursive": recursive_switch,
                                "enabled": enabled_switch,
                            }
                        )

                        def _update_name(e: Any, current: int = idx) -> None:
                            state.cfg.libraries[current].name = str(e.value or "").strip() or f"library-{current + 1}"

                        def _update_path(e: Any, current: int = idx) -> None:
                            state.cfg.libraries[current].path = Path(str(e.value or "").strip())

                        def _update_recursive(e: Any, current: int = idx) -> None:
                            state.cfg.libraries[current].recursive = bool(e.value)

                        def _update_enabled(e: Any, current: int = idx) -> None:
                            state.cfg.libraries[current].enabled = bool(e.value)

                        name_input.on("change", _update_name)
                        path_input.on("change", _update_path)
                        recursive_switch.on_value_change(_update_recursive)
                        enabled_switch.on_value_change(_update_enabled)

                        ui.button(
                            icon="delete",
                            on_click=lambda current=idx: remove_library_row(current),
                        ).props("flat round dense color=negative")

    def refresh_pending_uploads() -> None:
        state.pending_uploads = workspace_for_config(state.cfg).list_items()

    def pending_status_meta(status: str) -> tuple[str, str]:
        mapping = {
            "queued": ("等待识别", "chip chip-muted"),
            "processing": ("识别中", "chip chip-soft"),
            "ready": ("可导入", "chip"),
            "failed": ("识别失败", "chip chip-muted"),
        }
        return mapping.get(str(status or "").lower(), ("未知状态", "chip chip-muted"))

    def toggle_pending_selection(item_id: str, selected: bool) -> None:
        if selected:
            selected_upload_ids.add(item_id)
        else:
            selected_upload_ids.discard(item_id)

    async def process_uploaded_item(item_id: str) -> None:
        cfg = load_meme_reaction_config()
        workspace = workspace_for_config(cfg)
        item = workspace.get_item(item_id)
        if item is None:
            return
        try:
            workspace.mark_processing(item_id)
            result = await tag_meme_image(item.staged_path, cfg=cfg)
        except Exception as exc:
            try:
                workspace.mark_failed(item_id, str(exc))
            except KeyError:
                return
        else:
            try:
                workspace.mark_ready(item_id, result)
            except KeyError:
                return

    def queue_recognition(item_ids: Sequence[str]) -> None:
        for item_id in item_ids:
            background_tasks.create(process_uploaded_item(item_id), name=f"meme-upload-{item_id}")

    def render_pending_uploads() -> None:
        if not page_refs or "pending_container" not in page_refs:
            return
        refresh_pending_uploads()
        container = page_refs["pending_container"]
        container.clear()
        known_ids = {item.id for item in state.pending_uploads}
        selected_upload_ids.intersection_update(known_ids)
        page_refs["pending_count"].text = f"{len(state.pending_uploads)} 条"
        ready_count = sum(1 for item in state.pending_uploads if item.status == "ready")
        failed_count = sum(1 for item in state.pending_uploads if item.status == "failed")
        page_refs["pending_ready_count"].text = f"{ready_count} 条可导入"
        page_refs["pending_failed_count"].text = f"{failed_count} 条失败"

        if not state.pending_uploads:
            with container:
                with ui.card().classes("surface-card w-full p-8 text-center"):
                    ui.icon("upload_file", size="3rem").classes("opacity-40")
                    ui.label("还没有待导入素材").classes("mt-3 text-lg font-bold")
                    ui.label("上传图片或 GIF 后，这里会自动跑识别并等待你手动入库。").classes("section-hint")
            return

        with container:
            for item in state.pending_uploads:
                status_text, status_classes = pending_status_meta(item.status)
                with ui.card().classes("surface-card w-full p-4"):
                    with ui.row().classes("w-full items-start gap-4 wrap"):
                        ui.checkbox(
                            value=item.id in selected_upload_ids,
                            on_change=lambda e, current=item.id: toggle_pending_selection(current, bool(e.value)),
                        ).props("dense")
                        ui.image(f"/api/uploads/raw?item_id={item.id}").classes("w-36 h-36 rounded-xl object-cover")
                        with ui.column().classes("flex-grow gap-2 min-w-[280px]"):
                            with ui.row().classes("w-full items-start justify-between gap-3"):
                                with ui.column().classes("gap-1"):
                                    ui.label(item.caption or item.original_name).classes("font-bold text-base")
                                    ui.label(item.original_name).classes("path-text section-hint")
                                ui.label(status_text).classes(status_classes)
                            with ui.row().classes("gap-2 flex-wrap"):
                                ui.label(item.library).classes("chip chip-muted")
                                ui.label(_human_size(item.size)).classes("chip chip-soft")
                            if item.tags:
                                with ui.row().classes("gap-1 flex-wrap"):
                                    for tag in item.tags[:6]:
                                        ui.label(tag).classes("chip")
                            if item.moods:
                                with ui.row().classes("gap-1 flex-wrap"):
                                    for mood in item.moods[:4]:
                                        ui.label(mood).classes("chip chip-soft")
                            if item.safe_for:
                                ui.label(f"适合：{_join_nonempty(item.safe_for[:4])}").classes("section-hint")
                            if item.avoid_for:
                                ui.label(f"避免：{_join_nonempty(item.avoid_for[:4])}").classes("section-hint")
                            if item.error:
                                ui.label(item.error).classes("section-hint text-negative")
                            with ui.row().classes("w-full items-center justify-between gap-3 pt-2 wrap"):
                                ui.label(f"激烈度 {item.intensity:.2f}").classes("section-hint")
                                with ui.row().classes("gap-2"):
                                    if item.status == "failed":
                                        ui.button(
                                            "重新识别",
                                            icon="refresh",
                                            on_click=lambda current=item.id: queue_recognition([current]),
                                        ).props("outline")
                                    if item.status == "ready":
                                        ui.button(
                                            "导入",
                                            icon="inventory_2",
                                            on_click=lambda current=item.id: import_uploads([current]),
                                        ).props("outline")
                                    ui.button(
                                        icon="delete",
                                        on_click=lambda current=item.id: delete_uploads([current]),
                                    ).props("flat round dense color=negative")

    def render_all() -> None:
        render_stats()
        render_library()
        render_pending_uploads()
        render_history()
        render_libraries()

    def toggle_meme_enabled(item: MemeItem, enabled: bool) -> None:
        item.enabled = enabled
        state.index.save(state.cfg.index_path)
        render_library()
        ui.notify("已更新表情包启用状态", type="positive")

    def delete_library_item(item: MemeItem) -> None:
        result = delete_meme_item(state.cfg, item.id)
        if not result.success:
            ui.notify(f"删除失败: {result.error}", type="negative")
            return
        state.refresh()
        render_all()
        ui.notify("已删除正式表情素材", type="positive")

    def confirm_delete_library_item(item: MemeItem) -> None:
        with ui.dialog() as dialog, ui.card().classes("surface-card p-5 min-w-[360px]"):
            ui.label("删除正式表情").classes("section-title")
            ui.label(item.caption or Path(item.path).name).classes("font-bold")
            ui.label("会删除原图、同名 sidecar .json，并从索引移除。此操作不可撤销。").classes("section-hint")
            ui.label(item.path).classes("path-text section-hint")
            with ui.row().classes("w-full justify-end gap-2 pt-2"):
                ui.button("取消", on_click=dialog.close).props("flat")

                def confirm_and_delete(current: MemeItem = item) -> None:
                    dialog.close()
                    delete_library_item(current)

                ui.button("确认删除", icon="delete", on_click=confirm_and_delete).props("unelevated color=negative")
        dialog.open()

    def add_library_row() -> None:
        libs = list(state.cfg.libraries)
        libs.append(MemeLibraryConfig(name="新表情库", path=Path("~/memes"), recursive=True, enabled=True))
        state.cfg.libraries = tuple(libs)
        render_libraries()

    def remove_library_row(index: int) -> None:
        libs = list(state.cfg.libraries)
        if 0 <= index < len(libs):
            libs.pop(index)
            state.cfg.libraries = tuple(libs)
            render_libraries()

    async def handle_upload_batch(event: MultiUploadEventArguments) -> None:
        if not state.cfg.libraries:
            ui.notify("请先配置至少一个表情库目录", type="negative")
            return
        library_name = str(upload_library_select.value or state.cfg.libraries[0].name)
        library = next((lib for lib in state.cfg.libraries if lib.name == library_name), None)
        if library is None:
            ui.notify("选中的表情库不存在", type="negative")
            return
        if not state.cfg.import_path_allowed(library.path):
            ui.notify(f"表情库目录超出 import.allowed_roots: {library.path}", type="negative")
            return
        workspace = workspace_for_config(state.cfg)
        created_ids: list[str] = []
        for uploaded in event.files:
            staged_path = workspace.allocate_staged_path(uploaded.name)
            await uploaded.save(staged_path)
            item = workspace.add_staged_file(
                original_name=uploaded.name,
                staged_path=staged_path,
                library=library_name,
                content_type=uploaded.content_type,
                size=uploaded.size(),
            )
            created_ids.append(item.id)
        render_pending_uploads()
        if upload_ref.get("widget") is not None:
            upload_ref["widget"].reset()
        if created_ids:
            queue_recognition(created_ids)
        ui.notify(f"已上传 {len(created_ids)} 个文件，正在后台识别", type="positive")

    def retry_selected_uploads() -> None:
        item_ids = sorted(selected_upload_ids)
        if not item_ids:
            ui.notify("先勾选要重新识别的条目", type="warning")
            return
        queue_recognition(item_ids)
        ui.notify(f"已重新排队 {len(item_ids)} 条识别任务", type="info")

    def delete_uploads(item_ids: Sequence[str]) -> None:
        if not item_ids:
            return
        workspace_for_config(state.cfg).remove_items(item_ids)
        for item_id in item_ids:
            selected_upload_ids.discard(item_id)
        render_pending_uploads()
        ui.notify(f"已删除 {len(item_ids)} 条待导入素材", type="positive")

    def delete_selected_uploads() -> None:
        item_ids = sorted(selected_upload_ids)
        if not item_ids:
            ui.notify("先勾选要删除的条目", type="warning")
            return
        delete_uploads(item_ids)

    def import_uploads(item_ids: Sequence[str]) -> None:
        if not item_ids:
            ui.notify("先勾选要导入的条目", type="warning")
            return
        result = workspace_for_config(state.cfg).import_items(state.cfg, item_ids)
        for item_id in result.imported_ids:
            selected_upload_ids.discard(item_id)
        state.refresh()
        render_all()
        if result.failed:
            ui.notify(
                f"已导入 {len(result.imported_ids)} 条，失败 {len(result.failed)} 条",
                type="warning",
            )
            return
        ui.notify(f"已导入 {len(result.imported_ids)} 条素材", type="positive")

    def import_selected_uploads() -> None:
        import_uploads(sorted(selected_upload_ids))

    def save_runtime_settings() -> None:
        update = build_runtime_payload(
            enabled=bool(page_refs["switch_enabled"].value),
            dry_run=bool(page_refs["switch_dry_run"].value),
            cooldown_seconds=int(page_refs["cooldown"].value or 0),
        )
        save_config_update(update, "运行设置已经写入")
        render_stats()

    def save_threshold_settings() -> None:
        update = build_threshold_payload(
            trigger_weight=float(page_refs["trigger_weight"].value or 0.0),
            threshold=float(page_refs["threshold"].value or 0.0),
        )
        save_config_update(update, "决策门槛已经写入")
        render_stats()

    def save_selection_llm_settings() -> None:
        update = build_selection_payload(
            top_k=int(selection_top_k.value or 1),
            repeat_penalty=float(selection_penalty.value or 0.8),
            max_same_tag_recent=int(selection_max_same.value or 3),
            allow_gif=bool(selection_allow_gif.value),
            allow_webp=bool(selection_allow_webp.value),
            allow_static_image=bool(selection_allow_static.value),
            llm_enabled=bool(llm_enabled.value),
            llm_timeout_seconds=float(llm_timeout.value or 4.0),
        )
        save_config_update(update, "选图与判定设置已经写入")

    def save_vision_settings() -> None:
        update = build_vision_payload(
            provider=str(vision_provider.value or ""),
            model=str(vision_model.value or ""),
            base_url=str(vision_base_url.value or ""),
            api_key=str(vision_api_key.value or ""),
        )
        save_config_update(update, "视觉识别设置已经写入")

    def save_web_settings() -> None:
        auth_enabled = bool(web_auth_enabled.value)
        web_username_value = str(web_username.value or "").strip()
        web_password_value = str(web_password.value or "")
        if auth_enabled and (not web_username_value or not web_password_value):
            ui.notify("启用登录保护时必须填写用户名和密码", type="negative")
            return
        update = build_web_payload(
            auth_enabled=auth_enabled,
            username=web_username_value,
            password=web_password_value,
            default_theme_mode=str(web_theme_default.value or "light"),
        )
        save_config_update(update, "Web 面板设置已经写入")

    def save_library_settings() -> None:
        libraries: list[MemeLibraryConfig] = []
        for idx, row in enumerate(library_row_refs):
            libraries.append(
                MemeLibraryConfig(
                    name=str(row["name"].value or "").strip() or f"library-{idx + 1}",
                    path=Path(str(row["path"].value or "").strip() or "~/memes"),
                    recursive=bool(row["recursive"].value),
                    enabled=bool(row["enabled"].value),
                )
            )
        blocked = find_disallowed_library(state.cfg, libraries)
        if blocked is not None:
            ui.notify(f"表情库目录超出 import.allowed_roots: {blocked.path}", type="negative")
            return
        state.cfg.libraries = tuple(libraries)
        update = build_libraries_payload(state.cfg.libraries)
        save_config_update(update, "表情库目录已经写入")
        render_libraries()

    metric_icons = {
        "stat_memes": "photo_library",
        "stat_active": "bolt",
        "stat_history": "history",
        "stat_libraries": "folder_open",
    }

    with ui.card().classes("hero-panel p-6 mb-6"):
        with ui.row().classes("w-full items-start justify-between gap-6 wrap"):
            with ui.column().classes("gap-2"):
                ui.label("Meme Workspace").classes("hero-kicker")
                ui.label("Hermes Meme 控制中心").classes("hero-title")
                ui.label("把表情素材、匹配规则和触发历史收拢到一个真正可维护的工作台里。").classes("hero-subtitle")
            with ui.row().classes("items-center gap-3 wrap"):
                theme_button_ref["button"] = ui.button(icon="dark_mode", on_click=toggle_theme).props("flat round")
                sync_theme_button()
                if state.cfg.web.auth.enabled:
                    ui.label(str(nicegui_app.storage.user.get(USERNAME_STORAGE_KEY) or state.cfg.web.auth.username)).classes("chip chip-muted")
                    ui.button("退出", icon="logout", on_click=logout).props("outline")
                ui.button("扫描索引", icon="refresh", on_click=run_importer).props("unelevated color=accent")

    with ui.row().classes("w-full gap-3 mb-6 wrap"):
        for label, ref in [("表情包", "stat_memes"), ("启用中", "stat_active"), ("历史记录", "stat_history"), ("库目录", "stat_libraries")]:
            with ui.card().classes("stat-card p-4 flex-[1_1_220px]"):
                with ui.row().classes("w-full items-start justify-between"):
                    with ui.column().classes("gap-1"):
                        ui.label(label).classes("stat-label")
                        page_refs[ref] = ui.label("-").classes("stat-value")
                    with ui.element("div").classes("stat-icon"):
                        ui.icon(metric_icons[ref])

    with ui.element("div").classes("overview-strip w-full mb-6"):
        with ui.card().classes("surface-card p-5"):
            with ui.row().classes("w-full items-center justify-between gap-4"):
                with ui.column().classes("gap-1"):
                    ui.label("运行状态").classes("section-title")
                    ui.label("插件开关、索引路径和运行模式总览。").classes("section-hint")
                with ui.row().classes("items-center gap-2"):
                    page_refs["status_indicator"] = ui.element("span").classes("status-dot on")
                    page_refs["status_text"] = ui.label("-").classes("section-hint")
                    ui.button("保存运行设置", icon="save", on_click=save_runtime_settings).props("outline")
            ui.separator().classes("my-4")
            with ui.row().classes("w-full gap-4 wrap"):
                with ui.column().classes("gap-3 flex-[1_1_240px]"):
                    page_refs["switch_enabled"] = ui.switch("启用插件", value=state.cfg.enabled)
                    page_refs["switch_dry_run"] = ui.switch("Dry-run 调试", value=state.cfg.dry_run)
                    page_refs["cooldown"] = ui.number("冷却时间（秒）", value=state.cfg.cooldown_seconds).classes("w-full")
                with ui.column().classes("gap-2 flex-[1_1_320px]"):
                    ui.label("索引路径").classes("meta-label")
                    page_refs["path_index"] = ui.label("-").classes("path-text section-hint")
                    ui.label("路由缓存").classes("meta-label mt-2")
                    page_refs["path_routes"] = ui.label("-").classes("path-text section-hint")
                    ui.label("发送历史").classes("meta-label mt-2")
                    page_refs["path_history"] = ui.label("-").classes("path-text section-hint")
        with ui.card().classes("surface-card p-5"):
            with ui.row().classes("w-full items-center justify-between gap-3"):
                with ui.column().classes("gap-1"):
                    ui.label("决策门槛").classes("section-title")
                    ui.label("触发概率和匹配阈值都应该可读，不该藏在一堆默认控件里。").classes("section-hint")
                ui.button("保存门槛", icon="save", on_click=save_threshold_settings).props("outline")
            ui.separator().classes("my-4")
            with ui.column().classes("gap-4"):
                with ui.column().classes("gap-1"):
                    with ui.row().classes("w-full items-center justify-between"):
                        ui.label("触发概率").classes("meta-label")
                        page_refs["trigger_text"] = ui.label(f"{state.cfg.trigger_weight:.2f}").classes("meta-value")
                    with ui.element("div").classes("meter-track"):
                        page_refs["trigger_bar"] = ui.element("div").classes("meter-fill").style(
                            "background: linear-gradient(90deg, rgba(217,108,89,0.92), rgba(217,108,89,0.45));"
                        )
                    page_refs["trigger_weight"] = ui.slider(min=0, max=1, step=0.05, value=state.cfg.trigger_weight).classes("w-full")
                with ui.column().classes("gap-1"):
                    with ui.row().classes("w-full items-center justify-between"):
                        ui.label("匹配阈值").classes("meta-label")
                        page_refs["threshold_text"] = ui.label(f"{state.cfg.threshold:.2f}").classes("meta-value")
                    with ui.element("div").classes("meter-track"):
                        page_refs["threshold_bar"] = ui.element("div").classes("meter-fill").style(
                            "background: linear-gradient(90deg, rgba(81,114,184,0.92), rgba(81,114,184,0.45));"
                        )
                    page_refs["threshold"] = ui.slider(min=0, max=1, step=0.05, value=state.cfg.threshold).classes("w-full")

    with ui.tabs().classes("w-full mb-4") as tabs:
        tab_dash = ui.tab("控制台", icon="dashboard")
        tab_lib = ui.tab("表情库", icon="photo_library")
        tab_ingest = ui.tab("上传入库", icon="upload_file")
        tab_hist = ui.tab("历史", icon="history")
        tab_set = ui.tab("设置", icon="settings")

    with ui.tab_panels(tabs, value=tab_dash).classes("w-full bg-transparent"):
        with ui.tab_panel(tab_dash).classes("p-0"):
            with ui.card().classes("surface-card p-5"):
                ui.label("控制台说明").classes("section-title")
                ui.label("这页只保留即时状态和关键旋钮。更重的素材管理、历史和目录维护都放到各自页面，避免一屏堆满。").classes("section-hint")

        with ui.tab_panel(tab_lib).classes("p-0"):
            with ui.card().classes("toolbar-card p-4 mb-4"):
                with ui.element("div").classes("toolbar-grid w-full"):
                    search_input = ui.input("搜索", placeholder="名称 / 内容标签 / 情绪标签").classes("flex-grow")
                    tag_input = ui.input("标签过滤", placeholder="直接输入标签").classes("w-48")
                    library_select = ui.select(["", *[lib.name for lib in state.cfg.libraries]], value="", label="表情库").classes("w-48")
                    enabled_select = ui.select(["", "true", "false"], value="", label="状态").classes("w-40")
                    ui.button("清空", icon="filter_alt_off", on_click=lambda: clear_library_filters()).props("outline")
                    page_refs["library_count"] = ui.label("-").classes("chip chip-muted")

                def apply_library_filters() -> None:
                    state.search_query = search_input.value or ""
                    state.search_tag = tag_input.value or ""
                    state.search_library = library_select.value or ""
                    state.search_enabled = enabled_select.value or ""
                    state.library_page = 1
                    render_library()

                search_input.on_value_change(lambda _: apply_library_filters())
                tag_input.on_value_change(lambda _: apply_library_filters())
                library_select.on_value_change(lambda _: apply_library_filters())
                enabled_select.on_value_change(lambda _: apply_library_filters())

            page_refs["library_container"] = ui.element("div").classes("meme-grid w-full")
            with ui.row().classes("w-full justify-between items-center mt-4"):
                ui.label("内容标签是用于搜索和匹配的主键，情绪标签用于语气补充。").classes("section-hint")
                with ui.row().classes("items-center gap-2"):
                    page_refs["library_prev"] = ui.button("上一页", icon="chevron_left", on_click=lambda: shift_library_page(-1)).props("outline")
                    page_refs["library_page_label"] = ui.label("1 / 1").classes("chip")
                    page_refs["library_next"] = ui.button("下一页", icon="chevron_right", on_click=lambda: shift_library_page(1)).props("outline")

        with ui.tab_panel(tab_ingest).classes("p-0"):
            with ui.card().classes("surface-card p-5 mb-4"):
                with ui.row().classes("w-full items-center justify-between gap-3 wrap"):
                    with ui.column().classes("gap-1"):
                        ui.label("上传后自动识别，最后手动入库").classes("section-title")
                        ui.label("上传会先进入插件自己的待导入工作区；识别跑完后，你再决定哪些正式进库。").classes("section-hint")
                    with ui.row().classes("items-center gap-2 wrap"):
                        page_refs["pending_count"] = ui.label("-").classes("chip chip-muted")
                        page_refs["pending_ready_count"] = ui.label("-").classes("chip")
                        page_refs["pending_failed_count"] = ui.label("-").classes("chip chip-soft")
                ui.separator().classes("my-4")
                with ui.row().classes("w-full items-start gap-4 wrap"):
                    upload_library_select = ui.select(
                        {lib.name: lib.name for lib in state.cfg.libraries} or {"default": "default"},
                        value=state.cfg.libraries[0].name if state.cfg.libraries else "default",
                        label="导入到表情库",
                    ).classes("w-56")
                    upload_ref["widget"] = ui.upload(
                        multiple=True,
                        auto_upload=True,
                        on_multi_upload=handle_upload_batch,
                        label="拖进来或点这里上传图片 / GIF",
                    ).props("accept=.png,.jpg,.jpeg,.webp,.gif color=accent flat bordered")
                with ui.row().classes("w-full items-center justify-between gap-3 mt-4 wrap"):
                    ui.label("识别会自动开始。失败项可以重试；只有识别完成的项才会进入正式表情库。").classes("section-hint")
                    with ui.row().classes("items-center gap-2 wrap"):
                        ui.button("重试选中", icon="refresh", on_click=retry_selected_uploads).props("outline")
                        ui.button("删除选中", icon="delete", on_click=delete_selected_uploads).props("outline color=negative")
                        ui.button("导入选中", icon="inventory_2", on_click=import_selected_uploads).props("unelevated color=accent")
            page_refs["pending_container"] = ui.column().classes("w-full gap-3")

        with ui.tab_panel(tab_hist).classes("p-0"):
            with ui.card().classes("surface-card p-4 mb-4"):
                with ui.row().classes("w-full items-center justify-between"):
                    ui.label("触发历史").classes("section-title")
                    page_refs["history_count"] = ui.label("-").classes("chip chip-muted")
            page_refs["history_container"] = ui.column().classes("history-stack w-full")

        with ui.tab_panel(tab_set).classes("p-0"):
            with ui.row().classes("w-full gap-4 wrap"):
                with ui.card().classes("surface-card p-5 flex-[1_1_360px]"):
                    with ui.row().classes("w-full items-center justify-between gap-3"):
                        ui.label("选图与判定").classes("section-title")
                        ui.button("保存这块", icon="save", on_click=save_selection_llm_settings).props("outline")
                    selection_top_k = ui.number("候选 Top-K", value=state.cfg.selection.top_k).classes("w-full")
                    selection_penalty = ui.number("重复惩罚", value=state.cfg.selection.repeat_penalty, step=0.05).classes("w-full")
                    selection_max_same = ui.number("同标签连发上限", value=state.cfg.selection.max_same_tag_recent).classes("w-full")
                    selection_allow_gif = ui.switch("允许 GIF", value=state.cfg.selection.allow_gif)
                    selection_allow_webp = ui.switch("允许 WebP", value=state.cfg.selection.allow_webp)
                    selection_allow_static = ui.switch("允许静态图", value=state.cfg.selection.allow_static_image)
                    llm_enabled = ui.switch("启用 LLM 判定", value=state.cfg.llm.enabled)
                    ui.label(
                        "关闭：完全不做 LLM 判定。开启：复用 Hermes 宿主自己的 ctx.llm 来判断要不要发表情包。"
                    ).classes("section-hint")
                    llm_timeout = ui.number("LLM 超时（秒）", value=state.cfg.llm.timeout_seconds, step=0.5).classes("w-full")
                    ui.label("这个开关只影响“要不要发表情包”的判定，不影响上传图片的视觉识别。").classes("section-hint")
                with ui.card().classes("surface-card p-5 flex-[1_1_360px]"):
                    with ui.row().classes("w-full items-center justify-between gap-3"):
                        ui.label("视觉识别（上传入库）").classes("section-title")
                        ui.button("保存这块", icon="save", on_click=save_vision_settings).props("outline")
                    vision_provider = ui.input("视觉 Provider（留空继承 Hermes）", value=state.cfg.vision.provider).classes("w-full")
                    ui.label(
                        "留空：先读 Hermes 的 auxiliary.vision.provider；再回退 model.provider。填写：只覆盖这个插件的视觉识别。"
                    ).classes("section-hint")
                    vision_model = ui.input("视觉 Model（留空继承 Hermes）", value=state.cfg.vision.model).classes("w-full")
                    ui.label(
                        "留空：只读 Hermes 的 auxiliary.vision.model；如果这里也没配，识别任务会直接失败并显示“未配置视觉模型”。"
                    ).classes("section-hint")
                    vision_base_url = ui.input("视觉 Base URL（留空继承 Hermes）", value=state.cfg.vision.base_url).classes("w-full")
                    ui.label(
                        "留空：先读 auxiliary.vision.base_url；再回退 model.base_url。填写：只覆盖这个插件的视觉识别接口地址。"
                    ).classes("section-hint")
                    vision_api_key = ui.input(
                        "视觉 API Key（留空继承 Hermes）",
                        value=state.cfg.vision.api_key,
                        password=True,
                        password_toggle_button=True,
                    ).classes("w-full")
                    ui.label(
                        "留空：先读 auxiliary.vision.api_key；再回退 model.api_key。填写：只覆盖这个插件的视觉识别密钥。"
                    ).classes("section-hint")
                with ui.card().classes("surface-card p-5 flex-[1_1_360px]"):
                    with ui.row().classes("w-full items-center justify-between gap-3"):
                        ui.label("Web 面板").classes("section-title")
                        ui.button("保存这块", icon="save", on_click=save_web_settings).props("outline")
                    web_auth_enabled = ui.switch("启用登录保护", value=state.cfg.web.auth.enabled)
                    web_username = ui.input("用户名", value=state.cfg.web.auth.username).classes("w-full")
                    web_password = ui.input(
                        "密码",
                        value=state.cfg.web.auth.password,
                        password=True,
                        password_toggle_button=True,
                    ).classes("w-full")
                    web_theme_default = ui.select(
                        {"light": "浅色", "dark": "深色"},
                        value=state.cfg.web.theme.default_mode,
                        label="默认主题",
                    ).classes("w-full")
                    ui.label("主题切换会按浏览器记住；默认主题只影响首次访问。").classes("section-hint")

            with ui.card().classes("surface-card p-5 mt-4"):
                with ui.row().classes("w-full items-center justify-between"):
                    ui.label("表情库目录").classes("section-title")
                    with ui.row().classes("items-center gap-2"):
                        ui.button("添加目录", icon="add", on_click=add_library_row).props("unelevated color=accent")
                        ui.button("保存目录", icon="save", on_click=save_library_settings).props("outline")
                page_refs["library_rows"] = ui.column().classes("w-full gap-3 mt-3")

    edit_dialog = ui.dialog()
    with edit_dialog, ui.card().classes("dialog-card w-[min(900px,95vw)] p-5"):
        with ui.row().classes("w-full items-start justify-between"):
            with ui.column().classes("gap-1"):
                ui.label("编辑表情包").classes("section-title")
                edit_path = ui.label("-").classes("path-text section-hint")
            edit_library = ui.label("-").classes("chip chip-muted")
        with ui.row().classes("w-full gap-4 mt-4"):
            edit_thumb = ui.image("").classes("w-56 h-42 rounded-xl object-cover")
            with ui.column().classes("flex-grow gap-3"):
                edit_caption = ui.input("画面描述", placeholder="写一句能帮助识别这张图的描述").classes("w-full")
                edit_tags = ui.input("内容标签", placeholder="用逗号分隔").classes("w-full")
                edit_moods = ui.input("情绪标签", placeholder="用逗号分隔").classes("w-full")
                edit_safe_for = ui.input("适用场景", placeholder="用逗号分隔").classes("w-full")
                edit_avoid_for = ui.input("规避场景", placeholder="用逗号分隔").classes("w-full")
                with ui.row().classes("items-center gap-4"):
                    edit_enabled = ui.switch("启用", value=True)
                    edit_intensity = ui.slider(min=0, max=1, step=0.05, value=0.5).classes("w-72")
                    edit_intensity_label = ui.label("0.50").classes("stat-value")
        with ui.row().classes("w-full justify-end gap-3 mt-5"):
            ui.button("取消", on_click=edit_dialog.close).props("outline")
            ui.button("保存", icon="save", on_click=save_meme_editor).props("unelevated color=accent")

    detail_dialog = ui.dialog()
    with detail_dialog, ui.card().classes("dialog-card w-[min(900px,95vw)] p-5"):
        with ui.row().classes("w-full items-start justify-between"):
            with ui.column().classes("gap-1"):
                ui.label("历史详情").classes("section-title")
                detail_time = ui.label("-").classes("section-hint")
            detail_target = ui.label("-").classes("chip chip-muted")
        with ui.row().classes("w-full gap-4 mt-4"):
            detail_thumb = ui.image("").classes("w-56 h-42 rounded-xl object-cover")
            with ui.column().classes("flex-grow gap-3"):
                detail_meme_name = ui.label("-").classes("stat-value")
                detail_meme_path = ui.label("-").classes("path-text section-hint")
                detail_score = ui.label("-").classes("stat-value")
                detail_reason = ui.label("-").classes("section-hint")
                detail_tags = ui.column().classes("gap-2")
                detail_chat = ui.column().classes("gap-2")
        with ui.row().classes("w-full justify-end mt-5"):
            ui.button("关闭", on_click=detail_dialog.close).props("unelevated color=accent")

    def shift_library_page(delta: int) -> None:
        state.library_page = max(1, state.library_page + delta)
        render_library()

    def apply_tag_filter(tag: str) -> None:
        state.search_tag = str(tag or "").strip()
        state.library_page = 1
        try:
            tag_input.value = state.search_tag
        except Exception:
            pass
        render_library()

    def clear_library_filters() -> None:
        state.search_query = ""
        state.search_tag = ""
        state.search_library = ""
        state.search_enabled = ""
        state.library_page = 1
        try:
            search_input.value = ""
            tag_input.value = ""
            library_select.value = ""
            enabled_select.value = ""
        except Exception:
            pass
        render_library()

    def sync_interactions() -> None:
        page_refs["switch_enabled"].on_value_change(lambda e: setattr(state.cfg, "enabled", bool(e.value)))
        page_refs["switch_dry_run"].on_value_change(lambda e: setattr(state.cfg, "dry_run", bool(e.value)))
        page_refs["cooldown"].on("change", lambda e: setattr(state.cfg, "cooldown_seconds", int(e.value or 0)))
        page_refs["trigger_weight"].on_value_change(
            lambda e: (
                setattr(state.cfg, "trigger_weight", float(e.value or 0.0)),
                refresh_decision_preview(),
            )
        )
        page_refs["threshold"].on_value_change(
            lambda e: (
                setattr(state.cfg, "threshold", float(e.value or 0.0)),
                refresh_decision_preview(),
            )
        )

    sync_interactions()
    ui.timer(2.0, render_pending_uploads)
    render_all()


def start_server(port: int = 8000, host: str = "127.0.0.1") -> None:
    cfg = load_meme_reaction_config()
    ui.run(
        host=host,
        port=port,
        show=False,
        title="Hermes Meme Dashboard",
        storage_secret=build_storage_secret(cfg),
    )


if __name__ in {"__main__", "__mp_main__"}:
    import argparse

    parser = argparse.ArgumentParser(description="Start the Hermes Meme Reaction NiceGUI Dashboard.")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", type=str, default="127.0.0.1")
    args = parser.parse_args()
    start_server(port=args.port, host=args.host)
