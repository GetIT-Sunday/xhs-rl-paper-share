"""小红书页面 CSS 选择器常量（移植自 autoclaw-cc/xiaohongshu-skills）。"""

# ========== 发布页 ==========
UPLOAD_CONTENT = "div.upload-content"
CREATOR_TAB = "div.creator-tab"
UPLOAD_INPUT = ".upload-input"
FILE_INPUT = 'input[type="file"]'
TITLE_INPUT = "div.d-input input"
CONTENT_EDITOR = "div.ql-editor"
IMAGE_PREVIEW = ".img-preview-area .pr"
PUBLISH_BUTTON = ".publish-page-publish-btn button.bg-red"

# 标题/正文长度校验
TITLE_MAX_SUFFIX = "div.title-container div.max_suffix"
CONTENT_LENGTH_ERROR = "div.edit-container div.length-error"

# 可见范围
VISIBILITY_DROPDOWN = "div.permission-card-wrapper div.d-select-content"
VISIBILITY_OPTIONS = "div.d-options-wrapper div.d-grid-item div.custom-option"

# 定时发布
SCHEDULE_SWITCH = ".post-time-wrapper .d-switch"
DATETIME_INPUT = ".date-picker-container input"

# 原创声明
ORIGINAL_SWITCH_CARD = "div.custom-switch-card"
ORIGINAL_SWITCH = "div.d-switch"

# 标签联想
TAG_TOPIC_CONTAINER = "#creator-editor-topic-container"
TAG_FIRST_ITEM = ".item"

# 弹窗
POPOVER = "div.d-popover"
