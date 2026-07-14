<a name="xhs-rl-paper-share"></a>
<div align="right">
  <a href="README_ZH.md">中文文档</a>
</div>

<p align="center">
  <img src="assets/banner.png" alt="xhs-rl-paper-share banner" width="100%">
</p>

<p align="center">
  <a href="#-features">Features</a> •
  <a href="#-installation">Installation</a> •
  <a href="#-usage">Usage</a> •
  <a href="#%EF%B8%8F-commands">Commands</a> •
  <a href="#%EF%B8%8F-configuration">Configuration</a> •
  <a href="#-branches">Branches</a>
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

> **Demo** — arXiv paper (left) → XHS published note (right)
>
> <img src="assets/demo_screenshot.png" alt="Demo: arXiv paper to Xiaohongshu post" width="100%">

| Feature | Description |
|---|---|
| 📄 Paper Fetching | Fetch latest RL / embodied-AI / robot-learning papers from arXiv |
| ✍️ Content Generation | Generate Xiaohongshu-style copy from paper abstract — no LLM API Key required |
| 🖼️ Cover Extraction | Auto-extract arXiv paper first page as cover image via PyMuPDF |
| 📤 Publishing | Publish image+text notes via XHS Creator API, supports private preview and public publish |
| 🔄 Deduplication | Maintain published list to avoid re-publishing |

---

## 📦 Installation

> **Prerequisites**: Python 3.8+ · a Xiaohongshu Creator account

```bash
git clone https://github.com/GetIT-Sunday/xhs-rl-paper-share.git
cd xhs-rl-paper-share
pip install xhs xhshow PyMuPDF requests arxiv
```

<details>
<summary><strong>📋 Dependency details</strong></summary>
<br>

| Package | Purpose |
|---|---|
| `xhs` | Xiaohongshu API client |
| `xhshow` | Real-time request signing (fixes outdated built-in signing) |
| `PyMuPDF` | PDF first page to image |
| `requests` | HTTP requests |
| `arxiv` | arXiv paper metadata |

</details>

<div align="right"><a href="#xhs-rl-paper-share">↑ back to top</a></div>

---

## 🚀 Usage

The full pipeline is 4 required steps + 2 optional steps:

**① Get Xiaohongshu Cookie**

Log in to [XHS Creator Center](https://creator.xiaohongshu.com), open DevTools → Application → Cookies → `creator.xiaohongshu.com`, copy `a1`, `web_session`, `webId`.

> ⚠️ **Must use Creator Center cookies** — consumer-side (`www.xiaohongshu.com`) cookies cannot call publishing APIs.

**② Fetch Papers**

```bash
python3 scripts/fetch_papers.py --count 5
# Output → references/fetched_papers.json
```

**③ Generate Content**

```bash
python3 scripts/generate_content.py --arxiv-id 2606.24014
# Output → references/content_2606_24014.json
```

**④ Capture Cover**

```bash
python3 scripts/capture_cover.py --arxiv-id 2606.24014
# Saves arXiv first-page screenshot → assets/covers/
```

**⑤ Publish**

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

<details>
<summary><strong>⑥ Scheduled Publishing (optional) — click to expand</strong></summary>
<br>

```bash
# cron: daily at 10:00
0 10 * * * cd /path/to/repo && XHS_COOKIE='a1=xxx;...' python3 scripts/scheduled_publish.py
```

</details>

<div align="right"><a href="#xhs-rl-paper-share">↑ back to top</a></div>

---

## 🛠️ Commands

<table>
<tr><th>Script</th><th>Command</th><th>Description</th></tr>
<tr><td><code>fetch_papers.py</code></td><td><code>python3 scripts/fetch_papers.py --count N</code></td><td>Fetch N papers from arXiv</td></tr>
<tr><td><code>generate_content.py</code></td><td><code>python3 scripts/generate_content.py --arxiv-id &lt;ID&gt;</code></td><td>Generate XHS copy</td></tr>
<tr><td><code>capture_cover.py</code></td><td><code>python3 scripts/capture_cover.py --arxiv-id &lt;ID&gt;</code></td><td>Extract PDF first page as cover</td></tr>
<tr><td><code>publish_to_xhs.py</code></td><td><code>python3 scripts/publish_to_xhs.py --content-json &lt;f&gt; --cookie &lt;c&gt;</code></td><td>Publish note</td></tr>
<tr><td><code>scheduled_publish.py</code></td><td><code>XHS_COOKIE='...' python3 scripts/scheduled_publish.py</code></td><td>Full pipeline entry point</td></tr>
</table>

<div align="right"><a href="#xhs-rl-paper-share">↑ back to top</a></div>

---

## ⚙️ Configuration

> 🔒 Set cookie via environment variable to avoid shell history exposure

```bash
export XHS_COOKIE='a1=xxx;web_session=xxx;webId=xxx'
python3 scripts/publish_to_xhs.py --content-json references/content_2606_24014.json
```

<div align="right"><a href="#xhs-rl-paper-share">↑ back to top</a></div>

---

## 🌿 Branches

<table>
<tr>
<th width="50%">🌍 <code>main</code> — General</th>
<th width="50%">🤖 <code>dodo</code> — dodo Integration</th>
</tr>
<tr>
<td valign="top">

Pure Python, standard PyPI dependencies only. Runs anywhere.

- ✅ Zero platform lock-in
- ✅ Works in any Python 3.8+ environment
- ✅ Minimal dependency surface

</td>
<td valign="top">

Everything in `main`, plus dodo AI Agent platform integration.

- ✅ dodo Skill protocol (`SKILL.md`)
- ✅ GPT Image cover generation
- ✅ `arxiv-paper-reader` deep-read reports

</td>
</tr>
</table>

<div align="right"><a href="#xhs-rl-paper-share">↑ back to top</a></div>

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

<div align="right"><a href="#xhs-rl-paper-share">↑ back to top</a></div>

---

## ⚠️ Notes

<details open>
<summary><strong>🔒 Cookie Security</strong></summary>
<br>

`web_session` is a login credential — never commit it to version control.

</details>

<details>
<summary><strong>📊 Publish Frequency</strong></summary>
<br>

Recommend ≤ 3 posts/day to avoid XHS rate limiting.

</details>

<details>
<summary><strong>⏰ Cookie Expiry</strong></summary>
<br>

Creator Center cookies expire in ~30 days.

</details>

<details>
<summary><strong>✍️ Signing</strong></summary>
<br>

`xhs`'s built-in signing algorithm is flagged by XHS risk control; this project monkey-patches it to `xhshow` real-time signing.

</details>

<div align="right"><a href="#xhs-rl-paper-share">↑ back to top</a></div>

---

## 🤝 Contributing

Contributions are what make the open-source community such an amazing place to learn and create. Any contribution you make is greatly appreciated!

1. Fork the project
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

Don't forget to give the project a ⭐ if you find it useful!

<div align="right"><a href="#xhs-rl-paper-share">↑ back to top</a></div>

---

## 📄 License

Distributed under the **MIT License**. See [LICENSE](LICENSE) for details.

<div align="right"><a href="#xhs-rl-paper-share">↑ back to top</a></div>

---

<p align="center">
  <sub>If this project saved you time, consider giving it a ⭐ — it helps others discover it too.</sub>
</p>

<p align="center">
  <a href="https://star-history.com/#GetIT-Sunday/xhs-rl-paper-share&Date">
    <img src="https://api.star-history.com/svg?repos=GetIT-Sunday/xhs-rl-paper-share&type=Date" alt="Star History Chart" width="600">
  </a>
</p>
