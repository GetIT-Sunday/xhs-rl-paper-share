"""图文发布与草稿箱保存（移植自 autoclaw-cc/xiaohongshu-skills）。

核心函数：
  fill_publish_form(page, content)  — 填写发布表单（不点击发布）
  save_as_draft(page)               — 点击「暂存离开」保存草稿
  click_publish_button(page)        — 触发实际发布
"""
from __future__ import annotations

import json
import logging
import random
import re
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .bridge import BridgePage

from .errors import (
    AccountRiskControlError,
    ContentTooLongError,
    PublishError,
    TitleTooLongError,
    UploadTimeoutError,
)
from .selectors import (
    CONTENT_EDITOR,
    CONTENT_LENGTH_ERROR,
    CREATOR_TAB,
    DATETIME_INPUT,
    FILE_INPUT,
    IMAGE_PREVIEW,
    ORIGINAL_SWITCH,
    ORIGINAL_SWITCH_CARD,
    POPOVER,
    SCHEDULE_SWITCH,
    TAG_FIRST_ITEM,
    TAG_TOPIC_CONTAINER,
    TITLE_INPUT,
    TITLE_MAX_SUFFIX,
    UPLOAD_INPUT,
    VISIBILITY_DROPDOWN,
    VISIBILITY_OPTIONS,
)
from .types import PublishImageContent
from .urls import PUBLISH_URL

logger = logging.getLogger(__name__)


# ─── 公共入口 ────────────────────────────────────────────────────────────────

def fill_publish_form(page: "BridgePage", content: PublishImageContent) -> None:
    """填写图文发布表单，不点击发布。完成后可调用 save_as_draft 或 click_publish_button。"""
    if not content.image_paths:
        raise PublishError("图片不能为空")

    _navigate_to_publish_page(page)
    _click_publish_tab(page, "上传图文")
    time.sleep(1)

    _upload_images(page, content.image_paths)

    tags = content.tags[:10]
    if len(content.tags) > 10:
        logger.warning("标签数量超过10，截取前10个")

    _fill_publish_form(
        page,
        content.title,
        content.content,
        tags,
        content.schedule_time,
        content.is_original,
        content.visibility,
    )


def save_as_draft(page: "BridgePage") -> None:
    """点击「暂存离开」按钮保存草稿。

    要求：已通过 fill_publish_form 填写完表单，浏览器处于发布页。
    """
    clicked = page.evaluate(
        """
        (() => {
            const buttons = document.querySelectorAll('button.custom-button');
            for (const btn of buttons) {
                if (btn.textContent.trim() === '暂存离开') {
                    btn.click();
                    return true;
                }
            }
            return false;
        })()
        """
    )

    if clicked:
        time.sleep(2)
        logger.info("已点击「暂存离开」，内容已保存到草稿箱")
    else:
        logger.warning("未找到「暂存离开」按钮")
        raise PublishError("未找到「暂存离开」按钮")


def click_publish_button(page: "BridgePage") -> None:
    """触发发布（通过 dispatchEvent 向 <xhs-publish-btn> 发送自定义事件）。"""
    # 注入多层响应捕获
    page.evaluate(
        """
        (() => {
            window.__xhsPublishResult = null;
            function looksLikePublishResp(body) {
                if (!body) return false;
                return body.includes('HTTPBizError')
                    || /"code":\\s*-913\\d/.test(body)
                    || body.includes('禁止发笔记')
                    || /"note_id":\\s*"[^"]+"/.test(body);
            }
            function capture(source, info) {
                if (window.__xhsPublishResult) return;
                window.__xhsPublishResult = {source, ...info};
            }
            function captureFromBody(source, url, status, body) {
                if (window.__xhsPublishResult) return;
                if (!looksLikePublishResp(body)) return;
                try {
                    const j = JSON.parse(body);
                    capture(source, {url, status, ...j});
                } catch (e) {
                    const codeMatch = body.match(/"code":\\s*(-?\\d+)/);
                    const msgMatch = body.match(/"msg":\\s*"([^"]+)"/);
                    capture(source, {
                        url, status,
                        code: codeMatch ? parseInt(codeMatch[1], 10) : null,
                        msg: msgMatch ? msgMatch[1] : null,
                        raw: body.slice(0, 500),
                    });
                }
            }
            const origOpen = XMLHttpRequest.prototype.open;
            const origSend = XMLHttpRequest.prototype.send;
            XMLHttpRequest.prototype.open = function(method, url) {
                this.__xhsPubUrl = url;
                return origOpen.apply(this, arguments);
            };
            XMLHttpRequest.prototype.send = function() {
                this.addEventListener('loadend', () => {
                    captureFromBody('xhr', this.__xhsPubUrl, this.status, this.responseText || '');
                });
                return origSend.apply(this, arguments);
            };
            const origFetch = window.fetch;
            window.fetch = async function(...args) {
                const url = typeof args[0] === 'string' ? args[0] : args[0].url;
                const resp = await origFetch.apply(this, args);
                try {
                    const txt = await resp.clone().text();
                    captureFromBody('fetch', url, resp.status, txt);
                } catch (e) {}
                return resp;
            };
            ['error','log','warn'].forEach((method) => {
                const orig = console[method];
                console[method] = function(...args) {
                    const txt = args.map((a) => {
                        if (typeof a === 'string') return a;
                        if (a && typeof a === 'object') { try { return JSON.stringify(a); } catch(e) { return String(a); } }
                        return String(a);
                    }).join(' ');
                    if (txt.includes('HTTPBizError') || txt.includes('发布失败')) {
                        const codeMatch = txt.match(/"code":\\s*(-?\\d+)/);
                        const msgMatch = txt.match(/"msg":\\s*"([^"]+)"/);
                        if (codeMatch) {
                            capture('console', {
                                code: parseInt(codeMatch[1], 10),
                                msg: msgMatch ? msgMatch[1] : '发布失败',
                                raw_console: txt.slice(0, 800),
                            });
                        }
                    }
                    return orig.apply(this, args);
                };
            });
        })()
        """
    )

    fire_result = page.evaluate(
        """
        (() => {
            const host = document.querySelector('xhs-publish-btn[is-publish="true"]');
            if (!host) return 'not_found';
            if (host.getAttribute('submit-disabled') === 'true') return 'disabled';
            host.dispatchEvent(new CustomEvent('publish', {bubbles: true, cancelable: true}));
            return 'fired';
        })()
        """
    )

    if fire_result == "not_found":
        raise PublishError("未找到 <xhs-publish-btn> 发布按钮容器")
    if fire_result == "disabled":
        raise PublishError("发布按钮 submit-disabled=true，不可发布")

    deadline = time.monotonic() + 15
    result = None
    while time.monotonic() < deadline:
        result = page.evaluate("window.__xhsPublishResult")
        if result:
            break
        time.sleep(0.3)

    if not result:
        logger.warning("15s 内未捕获到发布反馈")
        time.sleep(2)
        return

    code = result.get("code")
    msg = result.get("msg", "")
    source = result.get("source", "unknown")
    logger.info("发布响应 (来源=%s code=%s msg=%r)", source, code, msg)

    if code == 0 or result.get("success") is True:
        logger.info("发布成功")
        time.sleep(2)
        return

    is_risk = (
        (code is not None and -9140 <= code <= -9130)
        or "违反" in (msg or "")
        or "禁止发笔记" in (msg or "")
        or "违规" in (msg or "")
    )
    if is_risk:
        raise AccountRiskControlError(code or -9136, msg or "账号被风控")
    raise PublishError(f"发布失败：code={code} msg={msg!r}")


# ─── 页面导航 ────────────────────────────────────────────────────────────────

def _navigate_to_publish_page(page: "BridgePage") -> None:
    page.navigate(PUBLISH_URL)
    page.wait_for_load(timeout=60.0)
    time.sleep(3)
    page.wait_dom_stable()
    time.sleep(2)


def _click_publish_tab(page: "BridgePage", tab_name: str) -> None:
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        found = page.evaluate(
            f"""
            (() => {{
                const name = {json.dumps(tab_name)};
                const tabs = document.querySelectorAll({json.dumps(CREATOR_TAB)});
                for (const t of tabs) {{
                    if (t.hasAttribute('data-hp-kind') || t.hasAttribute('button-hp-installed')) continue;
                    if (!t.hasAttribute('data-hp-bound')) continue;
                    const title = t.querySelector('span.title');
                    if (!title || title.textContent.trim() !== name) continue;
                    const r = t.getBoundingClientRect();
                    if (r.left < -1000 || r.top < -1000) continue;
                    t.click();
                    return 'clicked';
                }}
                for (const t of tabs) {{
                    if (t.hasAttribute('data-hp-kind') || t.hasAttribute('button-hp-installed')) continue;
                    const title = t.querySelector('span.title');
                    if (!title || title.textContent.trim() !== name) continue;
                    const r = t.getBoundingClientRect();
                    if (r.left < -1000 || r.top < -1000) continue;
                    t.click();
                    return 'clicked';
                }}
                return 'not_found';
            }})()
            """
        )
        if found == "clicked":
            return
        if found == "blocked":
            _remove_pop_cover(page)
            time.sleep(0.3)
        time.sleep(0.5)
    raise PublishError(f"没有找到发布 TAB: {tab_name}")


def _remove_pop_cover(page: "BridgePage") -> None:
    if page.has_element(POPOVER):
        page.remove_element(POPOVER)
    x = 380 + random.randint(0, 100)
    y = 20 + random.randint(0, 60)
    page.mouse_click(float(x), float(y))


# ─── 图片上传 ────────────────────────────────────────────────────────────────

def _upload_images(page: "BridgePage", image_paths: list[str]) -> None:
    import os
    valid_paths = [p for p in image_paths if os.path.exists(p)]
    if not valid_paths:
        raise PublishError("没有有效的图片文件")
    for i, path in enumerate(valid_paths):
        selector = UPLOAD_INPUT if i == 0 else FILE_INPUT
        logger.info("上传第 %d 张图片: %s", i + 1, path)
        page.set_file_input(selector, [path])
        _wait_for_upload_complete(page, i + 1)
        time.sleep(1)


def _wait_for_upload_complete(page: "BridgePage", expected_count: int) -> None:
    max_wait = 60.0
    start = time.monotonic()
    while time.monotonic() - start < max_wait:
        count = page.get_elements_count(IMAGE_PREVIEW)
        if count >= expected_count:
            return
        time.sleep(0.5)
    raise UploadTimeoutError(f"第 {expected_count} 张图片上传超时(60s)")


# ─── 表单填写 ────────────────────────────────────────────────────────────────

def _fill_publish_form(
    page: "BridgePage",
    title: str,
    content: str,
    tags: list[str],
    schedule_time: str | None,
    is_original: bool,
    visibility: str,
) -> None:
    content, tags = _extract_hashtags_from_content(content, tags)

    # 标题（粗略截断，不做严格汉字计数）
    if len(title) > 20:
        logger.warning("标题长度 %d 超限，截断到前20字符", len(title))
        title = title[:20]

    page.input_text(TITLE_INPUT, title)
    time.sleep(0.5)
    _check_title_max_length(page)
    time.sleep(1)

    content_selector = _find_content_element(page)
    page.input_content_editable(content_selector, content)
    time.sleep(1)
    page.click_element(TITLE_INPUT)

    if tags:
        _input_tags(page, content_selector, tags)
        time.sleep(1)

    _check_content_max_length(page)

    if schedule_time:
        _set_schedule_publish(page, schedule_time)

    _set_visibility(page, visibility)

    if is_original:
        try:
            _set_original(page)
        except Exception as e:
            logger.warning("设置原创声明失败: %s", e)

    logger.info("表单填写完成")


def _extract_hashtags_from_content(content: str, tags: list[str]) -> tuple[str, list[str]]:
    lines = content.rstrip().split("\n")
    if lines:
        last_line = lines[-1].strip()
        hashtag_pattern = re.compile(r"^(#\S+\s*)+$")
        if hashtag_pattern.match(last_line):
            extracted = re.findall(r"#(\S+)", last_line)
            existing = {t.lstrip("#") for t in tags}
            merged = list(tags)
            for t in extracted:
                if t not in existing:
                    merged.append(t)
                    existing.add(t)
            cleaned = "\n".join(lines[:-1]).rstrip()
            return cleaned, merged
    return content, list(tags)


def _find_content_element(page: "BridgePage") -> str:
    if page.has_element(CONTENT_EDITOR):
        return CONTENT_EDITOR
    found = page.evaluate(
        """
        (() => {
            const ps = document.querySelectorAll('p');
            for (const p of ps) {
                const placeholder = p.getAttribute('data-placeholder');
                if (placeholder && placeholder.includes('输入正文描述')) {
                    let current = p;
                    for (let i = 0; i < 5; i++) {
                        current = current.parentElement;
                        if (!current) break;
                        if (current.getAttribute('role') === 'textbox') return 'found';
                    }
                }
            }
            return '';
        })()
        """
    )
    if found == "found":
        return "[role='textbox']"
    raise PublishError("没有找到内容输入框")


def _check_title_max_length(page: "BridgePage") -> None:
    text = page.get_element_text(TITLE_MAX_SUFFIX)
    if text:
        parts = text.split("/")
        if len(parts) == 2:
            raise TitleTooLongError(parts[0], parts[1])
        raise TitleTooLongError(text, "?")


def _check_content_max_length(page: "BridgePage") -> None:
    text = page.get_element_text(CONTENT_LENGTH_ERROR)
    if text:
        parts = text.split("/")
        if len(parts) == 2:
            raise ContentTooLongError(parts[0], parts[1])
        raise ContentTooLongError(text, "?")


# ─── 标签输入 ────────────────────────────────────────────────────────────────

def _input_tags(page: "BridgePage", content_selector: str, tags: list[str]) -> None:
    time.sleep(1)
    para_count_before = int(
        page.evaluate(
            f'document.querySelector("{content_selector}").querySelectorAll("p").length'
        ) or 1
    )
    page.evaluate(
        f"""
        (() => {{
            const el = document.querySelector("{content_selector}");
            if (!el) return;
            el.focus();
            const range = document.createRange();
            range.selectNodeContents(el);
            range.collapse(false);
            const sel = window.getSelection();
            sel.removeAllRanges();
            sel.addRange(range);
            document.execCommand("insertParagraph", false, null);
        }})()
        """
    )
    time.sleep(0.5)
    for tag in tags:
        tag = tag.lstrip("#")
        _input_single_tag(page, content_selector, tag)

    page.evaluate(
        f"""
        (() => {{
            const el = document.querySelector("{content_selector}");
            if (!el) return;
            const paras = el.querySelectorAll("p");
            const lastContent = paras[{para_count_before} - 1];
            if (!lastContent) return;
            el.focus();
            const range = document.createRange();
            range.selectNodeContents(lastContent);
            range.collapse(false);
            const sel = window.getSelection();
            sel.removeAllRanges();
            sel.addRange(range);
            document.execCommand("insertParagraph", false, null);
        }})()
        """
    )
    time.sleep(0.3)


def _input_single_tag(page: "BridgePage", content_selector: str, tag: str) -> None:
    page.type_text("#", delay_ms=0)
    time.sleep(0.3)
    for char in tag:
        page.type_text(char, delay_ms=0)
        time.sleep(random.uniform(0.05, 0.12))

    deadline = time.monotonic() + 3.0
    clicked = False
    while time.monotonic() < deadline:
        time.sleep(0.5)
        if page.has_element(TAG_TOPIC_CONTAINER):
            item_selector = f"{TAG_TOPIC_CONTAINER} {TAG_FIRST_ITEM}"
            if page.has_element(item_selector):
                page.click_element(item_selector)
                clicked = True
                break

    if not clicked:
        page.type_text(" ", delay_ms=0)
    time.sleep(0.8)


# ─── 定时发布 ────────────────────────────────────────────────────────────────

def _set_schedule_publish(page: "BridgePage", schedule_time: str) -> None:
    from datetime import datetime
    try:
        dt = datetime.fromisoformat(schedule_time)
    except ValueError as e:
        raise PublishError(f"定时发布时间格式错误: {e}") from e
    page.click_element(SCHEDULE_SWITCH)
    time.sleep(0.8)
    datetime_str = dt.strftime("%Y-%m-%d %H:%M")
    page.select_all_text(DATETIME_INPUT)
    page.input_text(DATETIME_INPUT, datetime_str)
    time.sleep(0.5)


# ─── 可见范围 ────────────────────────────────────────────────────────────────

def _set_visibility(page: "BridgePage", visibility: str) -> None:
    if not visibility or visibility == "公开可见":
        return
    supported = {"仅自己可见", "仅互关好友可见"}
    if visibility not in supported:
        raise PublishError(f"不支持的可见范围: {visibility}")
    page.click_element(VISIBILITY_DROPDOWN)
    time.sleep(0.5)
    clicked = page.evaluate(
        f"""
        (() => {{
            const opts = document.querySelectorAll({json.dumps(VISIBILITY_OPTIONS)});
            for (const opt of opts) {{
                if (opt.textContent.includes({json.dumps(visibility)})) {{
                    opt.click();
                    return true;
                }}
            }}
            return false;
        }})()
        """
    )
    if not clicked:
        raise PublishError(f"未找到可见范围选项: {visibility}")
    time.sleep(0.2)


# ─── 原创声明 ────────────────────────────────────────────────────────────────

def _set_original(page: "BridgePage") -> None:
    result = page.evaluate(
        f"""
        (() => {{
            const cards = document.querySelectorAll({json.dumps(ORIGINAL_SWITCH_CARD)});
            for (const card of cards) {{
                if (!card.textContent.includes('原创声明')) continue;
                const sw = card.querySelector({json.dumps(ORIGINAL_SWITCH)});
                if (!sw) continue;
                const input = sw.querySelector('input[type="checkbox"]');
                if (input && input.checked) return 'already_on';
                sw.click();
                return 'clicked';
            }}
            return 'not_found';
        }})()
        """
    )
    if result == "already_on":
        return
    if result == "not_found":
        raise PublishError("未找到原创声明选项")
    time.sleep(0.5)
    _confirm_original_declaration(page)


def _confirm_original_declaration(page: "BridgePage") -> None:
    time.sleep(0.8)
    page.evaluate(
        """
        (() => {
            const footers = document.querySelectorAll('div.footer');
            for (const footer of footers) {
                if (!footer.textContent.includes('原创声明须知')) continue;
                const cb = footer.querySelector('div.d-checkbox input[type="checkbox"]');
                if (cb && !cb.checked) cb.click();
                return;
            }
        })()
        """
    )
    time.sleep(0.5)
    result = page.evaluate(
        """
        (() => {
            const footers = document.querySelectorAll('div.footer');
            for (const footer of footers) {
                if (!footer.textContent.includes('声明原创')) continue;
                const btn = footer.querySelector('button.custom-button');
                if (btn) {
                    if (btn.classList.contains('disabled') || btn.disabled) {
                        const cb = footer.querySelector('div.d-checkbox input[type="checkbox"]');
                        if (cb && !cb.checked) cb.click();
                        return 'button_disabled';
                    }
                    btn.click();
                    return 'clicked';
                }
            }
            return 'button_not_found';
        })()
        """
    )
    if result in ("button_not_found", "button_disabled"):
        raise PublishError(f"原创声明按钮状态: {result}")
