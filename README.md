<p align="center">
  <h1 align="center">xhs-rl-paper-share</h1>
  <p align="center">
    <strong>Auto-publish arXiv RL papers to Xiaohongshu / 自动将 arXiv 强化学习论文发布到小红书</strong>
  </p>
  <p align="center">
    <a href="#-features--功能特性">Features</a> •
    <a href="#-installation--安装">Installation</a> •
    <a href="#-usage--使用">Usage</a> •
    <a href="#-commands--命令">Commands</a> •
    <a href="#%EF%B8%8F-configuration--配置">Configuration</a> •
    <a href="#-branches--分支说明">Branches</a>
  </p>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.8+-yellow?style=flat-square" alt="Python">
  <img src="https://img.shields.io/badge/license-MIT-green?style=flat-square" alt="License">
  <img src="https://img.shields.io/github/stars/GetIT-Sunday/xhs-rl-paper-share?style=social" alt="Stars">
</p>

---

## ✨ Features / 功能特性

| Feature / 功能 | Description / 说明 |
|---|---|
| 📄 Paper Fetching / 论文抓取 | Fetch latest RL / embodied-AI / robot-learning papers from arXiv / 从 arXiv 抓取最新 RL、具身智能、机器人学习论文 |
| ✍️ Content Generation / 文案生成 | Generate Xiaohongshu-style copy from paper abstract / 基于摘要生成小红书风格文案，无需 LLM API Key |
| 🖼️ Cover Extraction / 封面截取 | Auto-extract arXiv paper first page as cover image (PyMuPDF) / 自动截取 arXiv 论文首页作为封面图 |
| 📤 Publishing / 发布 | Publish image+text notes via XHS Creator API / 调用小红书创作者 API 发布图文笔记，支持私密预览和公开发布 |
| 🔄 Deduplication / 去重 | Maintain published list to avoid re-publishing / 维护已发布记录，避免重复发布 |

---

## 📦 Installation / 安装

```bash
git clone https://github.com/GetIT-Sunday/xhs-rl-paper-share.git
cd xhs-rl-paper-share
pip install xhs xhshow PyMuPDF requests arxiv
```

### Dependencies / 依赖说明

| Package | Purpose / 用途 |
|---|---|
| `xhs` | Xiaohongshu API client / 小红书 API 客户端 |
| `xhshow` | Real-time request signing (fixes outdated built-in signing) / 实时请求签名（修复 xhs 内置过时签名） |
| `PyMuPDF` | PDF first page to image / PDF 首页转图片 |
| `requests` | HTTP requests / HTTP 请求 |
| `arxiv` | arXiv paper metadata / arXiv 论文元数据 |

---

## 🚀 Usage / 使用

### 1. Get Xiaohongshu Cookie / 获取小红书 Cookie

Log in to [XHS Creator Center](https://creator.xiaohongshu.com), open DevTools → Application → Cookies → `creator.xiaohongshu.com`, copy `a1`, `web_session`, `webId`.

登录[小红书创作者中心](https://creator.xiaohongshu.com)，打开浏览器开发者工具 → Application → Cookies → `creator.xiaohongshu.com`，复制 `a1`、`web_session`、`webId` 三个字段。

> ⚠️ **Must use Creator Center cookies** — consumer-side (`www.xiaohongshu.com`) cookies cannot call publishing APIs.
> 必须使用**创作者中心**的 Cookie，普通用户端的 Cookie 无法调用发布接口。

### 2. Fetch Papers / 抓取论文

```bash
python3 scripts/fetch_papers.py --count 5
# Output → references/fetched_papers.json
```

### 3. Generate Content / 生成文案

```bash
python3 scripts/generate_content.py --arxiv-id 2606.24014
# Output → references/content_2606_24014.json
```

### 4. Capture Cover / 截取封面

```bash
python3 scripts/capture_cover.py --arxiv-id 2606.24014
# Saves arXiv first-page screenshot → assets/covers/
```

### 5. Publish / 发布

```bash
# Private preview (recommended first) / 私密预览（推荐先确认内容）
python3 scripts/publish_to_xhs.py \
  --content-json references/content_2606_24014.json \
  --cookie 'a1=xxx;web_session=xxx;webId=xxx' \
  --private

# Public publish / 公开发布
python3 scripts/publish_to_xhs.py \
  --content-json references/content_2606_24014.json \
  --cookie 'a1=xxx;web_session=xxx;webId=xxx'
```

### 6. Scheduled Publishing / 定时任务（可选）

```bash
# cron: daily at 10:00 / 每天 10:00 自动发布
0 10 * * * cd /path/to/repo && XHS_COOKIE='a1=xxx;...' python3 scripts/scheduled_publish.py
```

---

## 🛠️ Commands / 命令

| Script / 脚本 | Command / 命令 | Description / 说明 |
|---|---|---|
| `fetch_papers.py` | `python3 scripts/fetch_papers.py --count N` | Fetch N papers from arXiv / 从 arXiv 抓取 N 篇论文 |
| `generate_content.py` | `python3 scripts/generate_content.py --arxiv-id <ID>` | Generate XHS copy / 生成小红书文案 |
| `capture_cover.py` | `python3 scripts/capture_cover.py --arxiv-id <ID>` | Extract PDF first page as cover / 截取封面图 |
| `publish_to_xhs.py` | `python3 scripts/publish_to_xhs.py --content-json <f> --cookie <c>` | Publish note / 发布笔记 |
| `scheduled_publish.py` | `XHS_COOKIE='...' python3 scripts/scheduled_publish.py` | Full pipeline entry point / 全流程入口 |

---

## ⚙️ Configuration / 配置

Set cookie via environment variable to avoid shell history exposure:

通过环境变量设置 Cookie，避免 Cookie 暴露在 shell 历史中：

```bash
export XHS_COOKIE='a1=xxx;web_session=xxx;webId=xxx'
python3 scripts/publish_to_xhs.py --content-json references/content_2606_24014.json
```

---

## 🌿 Branches / 分支说明

| Branch / 分支 | Description / 说明 |
|---|---|
| `main` | **General** — pure Python, standard PyPI deps, runs anywhere / **通用版**：纯 Python，只依赖公开 PyPI 包，可在任意环境独立运行 |
| `dodo` | **dodo Integration** — adds dodo AI Agent Skill protocol, GPT Image cover generation, arxiv-paper-reader reports / **dodo 集成版**：集成 dodo AI Agent 平台 Skill 协议、GPT Image 封面生成、论文精读报告 |

---

## 📁 Project Structure / 目录结构

```
xhs-rl-paper-share/
├── scripts/
│   ├── fetch_papers.py        # Fetch papers from arXiv / 从 arXiv 抓取论文
│   ├── generate_content.py    # Generate XHS copy / 生成小红书文案
│   ├── capture_cover.py       # Extract arXiv cover / 截取封面
│   ├── publish_to_xhs.py      # Publish via XHS API / 发布到小红书
│   ├── cookie_manager.py      # Cookie management / Cookie 管理
│   └── scheduled_publish.py   # Scheduled publish entry / 定时发布入口
├── references/
│   ├── fetched_papers.json    # Fetched paper list / 抓取到的论文列表
│   ├── published_papers.json  # Published record (initially empty) / 已发布记录（初始为空）
│   ├── publish_state.json     # Publish state / 发布状态
│   ├── paper_template.md      # Copy template docs / 文案模板说明
│   └── xhs_style_guide.md     # XHS style guide / 小红书风格指南
├── assets/
│   └── covers/                # Cover images (runtime, .gitignored) / 封面图（运行时生成）
├── .gitignore
└── README.md
```

---

## ⚠️ Notes / 注意事项

- **Cookie Security / Cookie 安全**：`web_session` is a login credential — never commit it to version control / 是登录凭证，不要提交到版本控制
- **Publish Frequency / 发布频率**：Recommend ≤ 3 posts/day to avoid XHS rate limiting / 建议每天不超过 3 篇，避免触发小红书风控
- **Cookie Expiry / Cookie 时效**：Creator Center cookies expire in ~30 days / 创作者中心 Cookie 约 30 天有效，过期需重新获取
- **Signing / 签名说明**：`xhs` built-in signing is flagged by XHS; this project monkey-patches to `xhshow` real-time signing / `xhs` 内置旧版签名已被风控识别，本项目已 monkey-patch 为 `xhshow` 实时签名

---

## 🤝 Contributing / 贡献

Contributions welcome! Feel free to open issues or pull requests.

欢迎提交 Issue 和 Pull Request！

---

## 📄 License / 许可证

MIT

---

<p align="center">
  <a href="https://star-history.com/#GetIT-Sunday/xhs-rl-paper-share&Date">
    <img src="https://api.star-history.com/svg?repos=GetIT-Sunday/xhs-rl-paper-share&type=Date" alt="Star History Chart" width="600">
  </a>
</p>
