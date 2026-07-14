"""数据类型定义。"""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class PublishImageContent:
    """图文发布内容。"""
    title: str
    content: str
    image_paths: list[str]
    tags: list[str] = field(default_factory=list)
    schedule_time: str | None = None
    is_original: bool = False
    visibility: str = "公开可见"
