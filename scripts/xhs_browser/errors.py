"""错误类型定义。"""


class CDPError(Exception):
    """CDP 通信或 JS 执行错误。"""


class ElementNotFoundError(CDPError):
    """元素未找到。"""

    def __init__(self, selector: str) -> None:
        super().__init__(f"元素未找到: {selector}")
        self.selector = selector


class PublishError(Exception):
    """发布失败。"""


class UploadTimeoutError(PublishError):
    """图片上传超时。"""


class TitleTooLongError(PublishError):
    """标题超长。"""

    def __init__(self, current: str, max_len: str) -> None:
        super().__init__(f"标题超长: {current}/{max_len}")
        self.current = current
        self.max_len = max_len


class ContentTooLongError(PublishError):
    """正文超长。"""

    def __init__(self, current: str, max_len: str) -> None:
        super().__init__(f"正文超长: {current}/{max_len}")
        self.current = current
        self.max_len = max_len


class AccountRiskControlError(PublishError):
    """账号被风控。"""

    def __init__(self, code: int, msg: str) -> None:
        super().__init__(f"账号被风控: code={code} msg={msg}")
        self.code = code
        self.msg = msg
