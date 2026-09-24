<div align="center">

<img src="assets/banner.png" alt="Paper2XHS 项目横幅：从 arXiv 论文到小红书内容（概念示意）" width="100%">

# Paper2XHS

**把科研论文写成小红书内容，用运营反馈帮助下一次选题。**

面向强化学习、具身智能和机器人学习领域研究者与科普创作者的 Agent Skill。

[English](README.md) · [简体中文](README_ZH.md)

![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square)
![Agent Skill](https://img.shields.io/badge/Agent-Skill-0066cc?style=flat-square)
[![GitHub stars](https://img.shields.io/github/stars/GetIT-Sunday/xhs-rl-paper-share?style=flat-square)](https://github.com/GetIT-Sunday/xhs-rl-paper-share)

[快速开始](#快速开始) · [可以做什么](#可以做什么) · [反馈决策](#让反馈参与决策) · [文档](#文档)

</div>

## 快速开始

把下面这句话发给具备 GitHub Skill 安装能力的 Agent：

```text
Help me install Paper2XHS from https://github.com/GetIT-Sunday/xhs-rl-paper-share with Skills. Install the repository root as the paper2xhs skill.
```

安装后新建会话或刷新 Skills，然后说：

```text
使用 $paper2xhs，选一篇近期机器人学习论文，生成有证据支撑的中文小红书草稿和论文首页封面。先展示结果，暂不发布。
```

Skill 会引导准备环境、选择论文、整理 Evidence Pack，再由当前 Agent 写中文成稿。**生成草稿不需要小红书登录，也不必单独配置 LLM API Key。** 发布和在线指标采集需要你自己的账号和配置。

**环境要求：**Python 3.10+、macOS/Linux 或 Windows WSL，以及支持 Skills 的 Agent。安装依赖和获取论文需要网络；GitHub 安装指令要求远端仓库已包含 Skill 文件。

<details>
<summary><strong>手动安装到 Codex</strong></summary>

```bash
git clone https://github.com/GetIT-Sunday/xhs-rl-paper-share.git \
  "${CODEX_HOME:-$HOME/.codex}/skills/paper2xhs"
```

目录已存在时，请先更新或备份。也可将维护者提供的 `paper2xhs.zip` 解压到 Skills 目录，保留完整的 `paper2xhs/` 文件夹及其中的脚本和参考文档。

</details>

## 可以做什么

| 能力 | 实际功能 |
|---|---|
| **选择论文** | 从 arXiv 召回候选，按发布历史去重，结合主题相关性、时效性、证据量和适用策略权重排序。 |
| **依据证据写作** | 将来源链接、摘要片段、数字和术语写入 Evidence Pack，由当前 Agent 整理成中文草稿。 |
| **准备与发布** | 截取 PDF 首页封面、匹配话题标签，并在用户要求时通过配置好的适配器发布。 |
| **使用运营反馈** | 导入报表或使用可配置的创作者中心适配器，保存带时间戳的快照并更新表达策略权重。 |
| **保留决策记录** | 记录实际使用的策略和权重版本；凭证、草稿、发布历史与运营数据保存在用户本机。 |

你可以这样说：

- “用 $paper2xhs 面向机器人学习读者解读这篇 arXiv 论文，说明方法、证据和局限。”
- “用 $paper2xhs 导入这份创作者报表，解释反馈对选题排序有什么影响。”
- “用 $paper2xhs 发布我已确认的成稿，并记录它使用的表达策略。”

**Skill 写作和脚本生成有所不同：**完整中文成稿由当前 Agent 完成；独立生成脚本和无人值守脚本调度目前输出摘要模板。

## 示例输出

<img src="assets/screenshot_demo.png" alt="项目示例：左侧是 arXiv 论文，右侧是已发布的中文小红书笔记" width="820">

*从论文到已发布笔记：这是项目已有示例，不是实时指标看板。*

## 可追溯的内容依据

**Evidence Pack（证据包）**是论文材料所支持内容的本地记录，包括来源链接、摘要片段、数字和术语。Agent 据此核对草稿中的方法与结果。

内置检查器可以标记部分无依据数字和英文术语，不是完整语义事实核验；当前发布脚本也仅将检查结果作为警告。超出摘要范围的结论，需要阅读全文并补录证据。

成稿 JSON、策略标签和来源要求见[内容与归因指南](references/skill-content.md)。

## 让反馈参与决策

反馈路径为：**运营指标 → 时间快照 → 平滑策略权重 → 候选排序与文案策略**。

- **区分指标。**缺失计数保持未知；阅读量不等于曝光量，账号净涨粉也不自动归因到单篇笔记。
- **对齐观察时长。**通常取每篇笔记发布后 24–30 小时的一次有效观测，要求曝光已知且策略可归因；重复采集不会增加学习样本。
- **平滑小样本反馈。**使用 capped Gamma–Poisson 事件率估计，每篇笔记的曝光贡献上限为 10,000，只更新实际使用策略的权重。
- **记录如何决策。**候选排序和模板生成读取策略；发布调度器会重新排列缓存和新候选，并保存选择记录。

这些权重反映观察相关性，不能证明策略带来因果提升。没有可用策略时，文案默认采用中性解释方式。

**本地 CSV/JSON 导入可用；在线采集需登录并验证字段映射。**配置示例是合成结构，计数口径默认 `unknown`，确认后台提供逐笔累计值后才可设为 `lifetime`。启用在线采集或周期发布前，请阅读[运维指南](references/skill-operations.md)。

## 在终端运行

开发者或习惯脚本的用户可以直接运行：

```bash
git clone https://github.com/GetIT-Sunday/xhs-rl-paper-share.git
cd xhs-rl-paper-share
python3 scripts/paper2xhs.py doctor
python3 scripts/paper2xhs.py setup
python3 scripts/paper2xhs.py run fetch -- --count 5 --days 7
python3 scripts/paper2xhs.py prepare
```

`prepare` 从已有候选中选题并输出草稿路径，不会发布。`--count` 是每个搜索关键词的召回数量，不是最终论文总数。如果 `python3` 低于 3.10，请改用已安装的新版解释器，例如 `python3.12`。

私有工作目录默认为 `~/.local/share/paper2xhs/`：

| 位置 | 内容 |
|---|---|
| `app/references/` | 候选论文和草稿 |
| `app/assets/covers/` | 论文首页封面 |
| `data/` | 指标快照、策略权重、报告、决策及发布记录 |
| `cookie.json` | 配置登录后保存的本地凭证缓存 |

通过 `PAPER2XHS_HOME` 修改工作目录，不同账号使用不同目录。`doctor` 展示实际路径而不显示凭证。更新 Skill 会刷新程序文件，保留已有私有数据。

<details>
<summary><strong>离线准备与反馈报告</strong></summary>

`setup --skip-deps` 可准备仅使用标准库的工作流，不安装第三方依赖，也不会启用在线发布或 PDF 渲染。

```bash
python3 scripts/paper2xhs.py setup --skip-deps
python3 scripts/paper2xhs.py run feedback -- report
```

导入自己的报表时，向 Agent 提供绝对文件路径。先做 dry-run，核对时间、计数口径、账号和字段映射后再写入账本。

</details>

## 当前边界

| 功能 | 状态 |
|---|---|
| 平台在线访问 | 使用非官方适配器，需在用户账号上验证登录、签名兼容性和当前指标字段。 |
| 发布 | 安装与本地预览不会发布；`--private` 会在平台创建真实的私密笔记。 |
| 调度 | `run schedule` 可能等待发布时间槽，再发布一篇内容；它不会自动注册周期任务。 |
| 可选集成 | MCP 需要另行运行服务；旧 `--draft` 模式使用的浏览器 Bridge 未随包提供。 |
| 高级封面 | 自带论文首页封面；模型生图需要单独配置相应能力。 |

## 文档

| 文档 | 用途 |
|---|---|
| [Skill 指令](SKILL.md) | Agent 入口、支持任务和执行边界 |
| [内容指南](references/skill-content.md) | 论文证据、中文写作和策略归因 |
| [运维指南](references/skill-operations.md) | 登录、指标映射、私有存储和调度 |
| [指标配置示例](examples/creator_metrics.config.example.json) | 核对真实 schema 后建立采集配置 |
| [测试](tests/) | 快照、策略、发布元数据及隔离安装包验证 |

统一入口为 [scripts/paper2xhs.py](scripts/paper2xhs.py)，各功能模块位于 [scripts/](scripts/)。

## 参与贡献

欢迎通过 [Issues](https://github.com/GetIT-Sunday/xhs-rl-paper-share/issues) 提交可复现的问题，或发起 Pull Request。修改平台适配器时，请用脱敏样例说明已验证的字段口径，不附带 Cookie 和真实账号导出数据。

```bash
python3 -m unittest discover -s tests -v
python3 scripts/package_skill.py
```

打包程序使用明确的文件清单生成 `dist/paper2xhs.zip`，排除历史笔记、凭证和运营数据；发布 Release 是维护者单独执行的操作。

## 许可证

旧文档标注 MIT，但当前仓库没有 `LICENSE` 文件。维护者需要确认许可证并补充正文，才能明确项目的授权状态。

## Star history

[![Star History](https://api.star-history.com/svg?repos=GetIT-Sunday/xhs-rl-paper-share&type=Date)](https://star-history.com/#GetIT-Sunday/xhs-rl-paper-share&Date)
