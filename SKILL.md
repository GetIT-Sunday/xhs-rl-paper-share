---
name: paper2xhs
description: 将 arXiv 强化学习、具身智能和机器人学习论文制作成小红书内容，支持候选选题、证据约束写作、论文封面、发布和运营反馈采集。用户提到 Paper2XHS、论文转小红书、科研账号运营或笔记反馈优化时使用。
---

# Paper2XHS

将本目录视为只读程序包。`<skill>` 指本 SKILL.md 所在的绝对目录，命令中的占位符必须替换成真实路径。不要依赖当前工作目录、作者电脑路径或另外克隆的仓库。

## 首次使用

先执行 `python3 "<skill>/scripts/paper2xhs.py" doctor`。读取返回的 `home`、`app`、`data` 和 `python` 路径；后续所有输入输出用绝对路径。若 `python_supported=false`，寻找已安装的 Python 3.10+（如 `python3.12`）运行入口；没有可用版本时先说明需安装 Python。

- 需要 Python 3.10+、macOS/Linux（Windows 使用 WSL）。脚本自带选题、反馈和生成骨架逻辑，无需另配 LLM API；中文成稿由当前 Agent 根据证据写作。
- 执行 `python3 "<skill>/scripts/paper2xhs.py" setup` 在独立目录准备虚拟环境和依赖。仅离线导入/反馈或生成骨架时可用 `setup --skip-deps`，它不联网安装第三方包。
- 默认运行目录为 `~/.local/share/paper2xhs`，可用 `PAPER2XHS_HOME` 指定。不同账号使用不同目录。数据、凭证和草稿不写入 Skill。
- 只有发布和在线指标采集需要小红书登录；先生成内容不必登录。读 [references/skill-operations.md](references/skill-operations.md) 处理登录、采集和调度。

## 根据用户意图执行

所有功能通过 `python3 "<skill>/scripts/paper2xhs.py" run <功能> -- <参数>` 调用。命令在 `doctor` 返回的 `app` 内运行；外部 CSV/JSON 文件传绝对路径。

| 意图 | 功能 / 参数 | 产物 |
|---|---|---|
| 召回近期候选 | `fetch --count 5 --days 7` | `<app>/references/fetched_papers.json` |
| 按当前权重选题、准备草稿 | 单独子命令 `prepare`（不是 `run prepare`） | 返回草稿路径；`<data>/last_decision.json` |
| 指定论文生成骨架 | `generate --arxiv-id <ID>` 或 `--paper-json <绝对路径>` | `<app>/references/content_<ID>.json` 和证据包 |
| 论文首页封面 | `cover --arxiv-id <ID>` | `<app>/assets/covers/` |
| 检查文案证据 | `evidence --content <JSON> --evidence <JSON>` | 数字和术语检查结果 |
| 导入反馈并更新权重 | `collect --source <CSV/JSON> --account-id <账号> --scope lifetime` | `<data>/metrics_snapshots.jsonl`、策略权重 |
| 反馈报告 | `feedback report` | `<data>/feedback_report.md` |
| 发布指定成稿 | `publish --content-json <JSON> --mark-published` | 本地发布记录；需要登录和发布授权 |

### 选题和写作

1. 用户指定论文时优先处理该论文。需要选题时抓取候选，结合用户领域筛选，再用 `prepare` 选题；排序中的新颖性/视觉分是启发式代理，不能宣称完成科学创新性评估。
2. `generate` 和无人值守调度器目前输出**摘要模板骨架**，不是完整 LLM 论文解读。读取其 Evidence Pack 和摘要，由当前 Agent 写可发布的中文内容。方法、结果、数值和适用条件必须能对应证据；只拿到摘要时明确阅读范围，全文主张先获取原文。
3. 读取 [references/skill-content.md](references/skill-content.md) 保持 JSON 契约及策略归因。保存中文成稿并展示标题、正文和封面。不要把示例数字或营销模板当成论文事实。
4. 用 `evidence` 做辅助检查，人工复核数字、比较基线和结论范围。检查器只检查部分数字/英文术语；发布脚本仅警告，不能将它称为完整语义事实校验。

### 发布和反馈

安装 Skill、要求生成或“预览”均不等于授权公开发布。用户明确要求发布时，在其已授权范围内执行，不重复索取确认；脚本的 `--force` 只用于已有明确授权的非交互执行。`--private` 也会在平台创建笔记，不是本地预览。

发布前核对成稿和发布账号。超时或结果不明时停止重试，先到账号确认是否已经创建，避免重复发布。MCP 若未返回笔记 ID，不猜测 ID、不按标题自动归因。`--draft` 依赖未随包提供的浏览器 Bridge，不作为默认功能；MCP 服务需用户另行安装。

在线反馈接口及字段映射尚需实号验证；不能声称安装后已自动接通。只有确认是逐笔累计口径才用 `lifetime`；曝光不等于阅读量，账号净涨粉不等于单篇涨粉。每篇笔记只取发布后 24–30 小时的一次有效观测，缺失曝光/策略标签时不学习。权重是观察相关性，不证明因果提升。

只在用户要求周期运行时设置调度。`run schedule` 会等到轮换时段并**实际发布一篇**，不是注册定时任务，也不是持续采集服务。设置方式及 24–30 小时窗口的采集频率见运维参考。
