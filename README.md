<div align="right">
  <a href="README_ZH.md">中文文档</a>
</div>

<p align="center">
  <h1 align="center">xhs-rl-paper-share</h1>
  <p align="center">
    <strong>Auto-publish arXiv RL papers to Xiaohongshu / 自动将 arXiv 强化学习论文发布到小红书</strong>
  </p>
  <p align="center">
    <a href="#-features">Features</a> •
    <a href="#-installation">Installation</a> •
    <a href="#-usage">Usage</a> •
    <a href="#%EF%B8%8F-commands">Commands</a> •
    <a href="#%EF%B8%8F-configuration">Configuration</a> •
    <a href="#-branches">Branches</a>
  </p>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.8+-yellow?style=flat-square" alt="Python">
  <img src="https://img.shields.io/badge/license-MIT-green?style=flat-square" alt="License">
  <a href="https://star-history.com/#GetIT-Sunday/xhs-rl-paper-share">
    <img src="https://img.shields.io/github/stars/GetIT-Sunday/xhs-rl-paper-share?style=social" alt="Stars">
  </a>
</p>

---

## ✨ Features

| Feature | Description |
|---|---|
| 📄 Paper Fetching | Fetch latest RL / embodied-AI / robot-learning papers from arXiv |
| ✍️ Content Generation | Generate Xiaohongshu-style copy from paper abstract — no LLM API Key required |
| 🖼️ Cover Extraction | Auto-extract arXiv paper first page as cover image via PyMuPDF |
| 📤 Publishing | Publish image+text notes via XHS Creator API, supports private preview and public publish |
| 🔄 Deduplication | Maintain published list to avoid re-publishing |

---

## 📦 Installation

```bash
git clone https://github.com/GetIT-Sunday/xhs-rl-paper-share.git
cd xhs-rl-paper-share
pip install xhs xhshow PyMuPDF requests arxiv
```

### Dependencies

| Package | Purpose |
|---|---|
| `xhs` | Xiaohongshu API client |
| `xhshow` | Real-time request signing (fixes outdated built-in signing) |
| `PyMuPDF` | PDF first page to image |
| `requests` | HTTP requests |
| `arxiv` | arXiv paper metadata |

---

## 🚀 Usage

### 1. Get Xiaohongshu Cookie

Log in to [XHS Creator Center](https://creator.xiaohongshu.com), open DevTools → Application → Cookies → `creator.xiaohongshu.com`, copy `a1`, `web_session`, `webId`.

> ⚠️ **Must use Creator Center cookies** — consumer-side (`www.xiaohongshu.com`) cookies cannot call publishing APIs.

### 2. Fetch Papers

```bash
python3 scripts/fetch_papers.py --count 5
# Output → references/fetched_papers.json
```

### 3. Generate Content

```bash
python3 scripts/generate_content.py --arxiv-id 2606.24014
# Output → references/content_2606_24014.json
```

### 4. Capture Cover

```bash
python3 scripts/capture_cover.py --arxiv-id 2606.24014
# Saves arXiv first-page screenshot → assets/covers/
```

### 5. Publish

```bash
# Private preview (recommended first)
python3 scripts/publish_to_xhs.py \
  --content-json references/content_2606_24014.json \
  --cookie 'a1=xxx;web_session=xxx;webId=xxx' \
  --private

# Public publish
python3 scripts/publish_to_xhs.py \
  --content-json references/content_2606_24014.json \
  --cookie 'a1=xxx;web_session=xxx;webId=xxx'
```

### 6. Scheduled Publishing (Optional)

```bash
# cron: daily at 10:00
0 10 * * * cd /path/to/repo && XHS_COOKIE='a1=xxx;...' python3 scripts/scheduled_publish.py
```

---

## 🛠️ Commands

| Script | Command | Description |
|---|---|---|
| `fetch_papers.py` | `python3 scripts/fetch_papers.py --count N` | Fetch N papers from arXiv |
| `generate_content.py` | `python3 scripts/generate_content.py --arxiv-id <ID>` | Generate XHS copy |
| `capture_cover.py` | `python3 scripts/capture_cover.py --arxiv-id <ID>` | Extract PDF first page as cover |
| `publish_to_xhs.py` | `python3 scripts/publish_to_xhs.py --content-json <f> --cookie <c>` | Publish note |
| `scheduled_publish.py` | `XHS_COOKIE='...' python3 scripts/scheduled_publish.py` | Full pipeline entry point |

---

## ⚙️ Configuration

Set cookie via environment variable to avoid shell history exposure:

```bash
export XHS_COOKIE='a1=xxx;web_session=xxx;webId=xxx'
python3 scripts/publish_to_xhs.py --content-json references/content_2606_24014.json
```

---

## 🌿 Branches

| Branch | Description |
|---|---|
| `main` | **General** — pure Python, standard PyPI deps, runs anywhere |
| `dodo` | **dodo Integration** — adds dodo AI Agent Skill protocol, GPT Image cover generation, arxiv-paper-reader reports |

---

## 📁 Project Structure

```
xhs-rl-paper-share/
├── scripts/
│   ├── fetch_papers.py        # Fetch papers from arXiv
│   ├── generate_content.py    # Generate XHS copy
│   ├── capture_cover.py       # Extract arXiv cover
│   ├── publish_to_xhs.py      # Publish via XHS API
│   ├── cookie_manager.py      # Cookie management
│   └── scheduled_publish.py   # Scheduled publish entry
├── references/
│   ├── fetched_papers.json    # Fetched paper list
│   ├── published_papers.json  # Published record (initially empty)
│   ├── publish_state.json     # Publish state
│   ├── paper_template.md      # Copy template docs
│   └── xhs_style_guide.md     # XHS style guide
├── assets/
│   └── covers/                # Cover images (runtime, .gitignored)
├── .gitignore
├── README.md                  # English (this file)
└── README_ZH.md               # 中文文档
```

---

## ⚠️ Notes

- **Cookie Security**: `web_session` is a login credential — never commit it to version control
- **Publish Frequency**: Recommend ≤ 3 posts/day to avoid XHS rate limiting
- **Cookie Expiry**: Creator Center cookies expire in ~30 days
- **Signing**: `xhs` built-in signing is flagged by XHS; this project monkey-patches to `xhshow` real-time signing

---

## 🤝 Contributing

Contributions welcome! Feel free to open issues or pull requests.

---

## 📄 License

MIT
