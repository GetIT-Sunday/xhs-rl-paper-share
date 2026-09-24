# 登录、反馈和发布运维

所有命令使用 SKILL.md 的 `paper2xhs.py` 入口。`doctor` 提供绝对路径，不打印凭证，不访问平台。`setup` 安装依赖需要网络；`setup --skip-deps` 可离线准备标准库工作流。Python 3.10+，macOS/Linux，Windows 使用 WSL。

## 运行目录

默认 `~/.local/share/paper2xhs/`：

- `.venv/`：运行依赖；不是当前 Agent 的模型环境。
- `app/scripts/`：随 Skill 更新的程序副本。
- `app/references/`：候选和可发布成稿；不会从发行包导入作者历史笔记。
- `app/assets/covers/`：封面。
- `data/`：快照、权重、报告、决策记录、发布账本和调度状态。
- `cookie.json`：本地登录缓存。

通过 `PAPER2XHS_HOME` 切换账号工作目录；`PAPER2XHS_DATA_DIR` 可单独指定数据目录。不要让多个账号共用这些目录。更新安装包只同步程序和配置示例，不清空运营数据。导入旧工程时由用户明确指定需要迁移的文件，不自动扫描其他账号。

## 登录

`run login` 尝试现有 SDK 扫码登录并缓存 Cookie。接口可能变动；拿到二维码后让用户在小红书 App 完成操作，不假装登录成功。扫码不可用时在创作者中心完成登录并在本机配置 `XHS_COOKIE`；不要让用户把凭证发到聊天或提交 Git。`doctor` 的 cookie_configured 只表示存在配置，不能证明有效。

`run publish` 和 `run collect` 通过入口复用缓存。`XHS_ACCOUNT_ID` 必须由用户确认；存在登录凭证不自动证明该 ID 对应当前登录账号。缺少权限、验证挑战或签名错误时停止，保留已生成的成稿。

## 反馈采集

离线文件首先推荐 `run collect -- --source <绝对路径> --account-id <账号> --dry-run`。需要实际写入时移除 dry-run；只有确认为逐笔累计计数才加 `--scope lifetime`。CSV/JSON 需要 `note_id` 和至少一个指标，时间须含时区；缺少 observed_at 时用文件修改时间，重新导入相同导出不制造新时间点。

在线流程：

1. 将 `<skill>/examples/creator_metrics.config.example.json` 复制到 `<home>/creator_metrics.config.json`。
2. 对照登录后实际返回结构修改 `rows_path`、`fields`、`has_more_path`、时间单位和统计口径。**示例是合成 schema，counter_scope 默认 unknown，不是已经核对的线上配置。**
3. 配置 `XHS_METRICS_CONFIG` 指向上述绝对路径，`XHS_ACCOUNT_ID` 为当前账号。先 `run collect -- --creator --dry-run`，验证后移除 dry-run。
4. 设置 `XHS_METRICS_MODE=creator` 后，发布调度器才会调用在线采集。

SDK 是非官方适配器，下载安装不保证线上接口可用。当前没有绕过登录或平台验证的功能。来源失败、空数据、分页重复时不猜字段。未获取到曝光时可保存互动快照，但不做曝光归一化学习。

反馈是 capped Gamma–Poisson 平滑的观察性事件率：每篇笔记在发布后 24–30 小时只取一次有效观测，曝光贡献上限 10,000；候选策略不冒领奖励。净涨粉仅在平台明确逐笔归因时使用。只有旧笔记的今天累计数，不能补造它的 24 小时历史值。

策略通过账号 + 笔记 ID 回连发布记录；旧稿若只有多个候选标签，不能推断真实使用策略。MCP 发布可能不返回 ID，需要用户核对后补记；不能按标题模糊匹配。操作报告和策略 JSON 属于本地文件，不需要上传公共仓库。

## 发布和周期运行

`run publish -- --content-json <成稿绝对路径> --mark-published` 会向平台写入；用户明确授权时可附加 `--force` 非交互执行。`--private` 是平台私密发布，不是预览。MCP 模式要求用户已有服务，`--draft` 所需 Bridge 不随包提供。

`run schedule` 是现有单次发布调度器：可能等待当天轮换时段，随后抓取、排序并发布一篇。不要为验证安装调用它。它没有常驻调度服务，也不自动调用当前 Agent 写中文；无人值守纯脚本产物仍是模板，成稿质量需另行接入模型或预先准备 Agent 成稿。

用户要求周期运营时，使用宿主已有的定时任务能力。分别安排指标采集与发布；发布时段每天轮换，仅发布前采集一次可能错过 24–30 小时学习窗口。可建议每 1–2 小时采集一次（以平台限制和用户需求为准），并独立安排每日发布。不要在安装或初次试用时自动启用周期发布。
