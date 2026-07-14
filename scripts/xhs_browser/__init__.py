"""
xhs_browser — Chrome CDP/Bridge 驱动的小红书浏览器自动化模块。
移植自 autoclaw-cc/xiaohongshu-skills，用于草稿箱保存。

依赖：
  pip install websockets requests

使用前提：
  - 本地运行 Chrome，并通过 XHS Bridge 扩展 + bridge_server.py 暴露 ws://localhost:9333
  - 或者：Chrome 以 --remote-debugging-port=9222 启动（CDP 直连模式）
"""

from .bridge import BridgePage
from .errors import (
    CDPError,
    ElementNotFoundError,
    PublishError,
    UploadTimeoutError,
    TitleTooLongError,
    ContentTooLongError,
    AccountRiskControlError,
)
from .publish import fill_publish_form, save_as_draft

__all__ = [
    "BridgePage",
    "CDPError",
    "ElementNotFoundError",
    "PublishError",
    "UploadTimeoutError",
    "TitleTooLongError",
    "ContentTooLongError",
    "AccountRiskControlError",
    "fill_publish_form",
    "save_as_draft",
]
