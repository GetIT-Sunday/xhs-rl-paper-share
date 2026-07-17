"""
xhs_mcp_client.py — xiaohongshu-mcp HTTP 客户端

通过 JSON-RPC 2.0 调用本地运行的 xiaohongshu-mcp 服务
（https://github.com/xpzouying/xiaohongshu-mcp）。

使用前提：
  1. 下载并启动 xiaohongshu-mcp：
       ./xiaohongshu-mcp-linux-amd64          # 或 docker compose up -d
  2. 首次使用需要先登录：
       ./xiaohongshu-login-linux-amd64
  3. 服务默认监听 http://localhost:18060/mcp

设计说明：
  - xiaohongshu-mcp 使用无头 Playwright/CloakBrowser 控制真实浏览器，
    绕过反爬，稳定性远高于 Python xhs 库的 API 调用方式。
  - 本模块只做 HTTP 薄包装，不关心对端是 Go 还是其他语言。
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_MCP_URL = "http://localhost:18060/mcp"


class XhsMcpError(Exception):
    """xiaohongshu-mcp 服务错误。"""


class XhsMcpClient:
    """xiaohongshu-mcp JSON-RPC 2.0 客户端。"""

    def __init__(self, url: str = DEFAULT_MCP_URL, timeout: int = 120) -> None:
        self.url = url
        self.timeout = timeout
        self._req_id = 0

    # ─── 底层 RPC ────────────────────────────────────────────────────────────

    def _call(self, method: str, params: dict | None = None) -> Any:
        """发送 JSON-RPC 请求，返回 result 字段。"""
        self._req_id += 1
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "id": self._req_id,
        }
        if params is not None:
            payload["params"] = params

        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            self.url,
            data=data,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as e:
            raise XhsMcpError(
                f"无法连接到 xiaohongshu-mcp（{self.url}）: {e}\n"
                "请确认服务已启动，参考：https://github.com/xpzouying/xiaohongshu-mcp"
            ) from e

        if "error" in body:
            raise XhsMcpError(f"RPC 错误: {body['error']}")
        return body.get("result")

    def _call_tool(self, tool_name: str, arguments: dict) -> dict:
        """调用 MCP tool，返回工具结果。"""
        result = self._call(
            "tools/call",
            {"name": tool_name, "arguments": arguments},
        )
        if result is None:
            raise XhsMcpError(f"工具 {tool_name} 返回空结果")

        # MCP 响应结构：{"content": [{"type": "text", "text": "..."}], "isError": false}
        is_error = result.get("isError", False)
        content = result.get("content", [])
        text = "\n".join(
            c.get("text", "") for c in content if c.get("type") == "text"
        )

        if is_error:
            raise XhsMcpError(f"工具 {tool_name} 返回错误: {text}")

        return {"success": True, "text": text, "raw": result}

    # ─── 连通性检查 ──────────────────────────────────────────────────────────

    def is_running(self) -> bool:
        """检查 xiaohongshu-mcp 服务是否在运行。"""
        try:
            self._call("initialize", {})
            return True
        except XhsMcpError:
            return True  # 只要能连上就算在运行
        except Exception:
            return False

    def check_login_status(self) -> dict:
        """检查小红书登录状态。"""
        return self._call_tool("check_login_status", {})

    # ─── 发布功能 ────────────────────────────────────────────────────────────

    def publish_content(
        self,
        title: str,
        content: str,
        images: list[str],
        tags: list[str] | None = None,
        schedule_at: str | None = None,
        is_original: bool = False,
        visibility: str = "公开可见",
    ) -> dict:
        """发布图文内容到小红书。

        Args:
            title:       标题（最多20个汉字）
            content:     正文（不含 # 标签，标签用 tags 参数）
            images:      图片路径列表（绝对路径 或 HTTP URL）
            tags:        话题标签列表，如 ["机器学习", "强化学习"]
            schedule_at: 定时发布时间（ISO8601，如 2024-01-20T10:30:00+08:00）
            is_original: 是否声明原创
            visibility:  可见范围（公开可见 / 仅自己可见 / 仅互关好友可见）

        Returns:
            {"success": True, "text": "...", "raw": ...}
        """
        # 标题截断（避免超限）
        if len(title) > 20:
            logger.warning("标题超过20字，截断: %s", title)
            title = title[:20]

        args: dict[str, Any] = {
            "title": title,
            "content": content,
            "images": images,
        }
        if tags:
            # xiaohongshu-mcp 的 tags 不带 #，只要词本身
            args["tags"] = [t.lstrip("#") for t in tags]
        if schedule_at:
            args["schedule_at"] = schedule_at
        if is_original:
            args["is_original"] = True
        if visibility and visibility != "公开可见":
            args["visibility"] = visibility

        logger.info(
            "调用 xiaohongshu-mcp publish_content: title=%r images=%d tags=%s",
            title,
            len(images),
            args.get("tags"),
        )
        return self._call_tool("publish_content", args)


# ─── 便捷函数（供 publish_to_xhs.py 调用）──────────────────────────────────

def publish_via_mcp(
    content_data: dict,
    cover_path: str,
    mcp_url: str = DEFAULT_MCP_URL,
) -> dict:
    """通过 xiaohongshu-mcp 发布论文笔记。

    Args:
        content_data: generate_content.py 输出的 JSON 数据
        cover_path:   封面图片绝对路径
        mcp_url:      MCP 服务 URL（默认 http://localhost:18060/mcp）

    Returns:
        {"success": bool, "error": str | None, "text": str}
    """
    import re

    client = XhsMcpClient(url=mcp_url)

    # 1. 连通性检查
    if not client.is_running():
        return {
            "success": False,
            "error": (
                f"xiaohongshu-mcp 服务未运行（{mcp_url}）\n"
                "请先启动服务：https://github.com/xpzouying/xiaohongshu-mcp\n"
                "  下载二进制: xiaohongshu-mcp-linux-amd64\n"
                "  或 Docker: docker compose up -d"
            ),
        }

    # 2. 检查登录状态
    try:
        login_status = client.check_login_status()
        logger.info("登录状态: %s", login_status.get("text", "")[:100])
        if "未登录" in login_status.get("text", "") or "not logged in" in login_status.get("text", "").lower():
            return {
                "success": False,
                "error": (
                    "小红书账号未登录，请先运行登录工具：\n"
                    "  ./xiaohongshu-login-linux-amd64\n"
                    "  或 docker exec -it xiaohongshu-mcp sh -c './xiaohongshu-login'"
                ),
            }
    except XhsMcpError as e:
        logger.warning("登录状态检查失败（继续尝试发布）: %s", e)

    # 3. 提取标签（从正文中的 #tag）
    xhs_content = content_data.get("xhs_content", "")
    raw_tags = re.findall(r'#([\w\u4e00-\u9fff·]+)', xhs_content)

    # 清理正文中的 # 标签行（xiaohongshu-mcp 要求 tags 和 content 分开）
    clean_content = re.sub(r'\s*#[\w\u4e00-\u9fff·]+', '', xhs_content).strip()

    # 4. 发布
    try:
        result = client.publish_content(
            title=content_data.get("xhs_title", ""),
            content=clean_content,
            images=[cover_path],
            tags=raw_tags if raw_tags else None,
        )
        return {
            "success": True,
            "error": None,
            "text": result.get("text", ""),
        }
    except XhsMcpError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": f"发布异常: {e}"}
