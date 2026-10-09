# Paper2XHS 上手教程

这份教程带你完成一次完整流程：安装 Skill、召回近期强化学习论文、生成中文稿、配置小红书账号、预览并发布。

Paper2XHS 适合强化学习、具身智能和机器人学习方向的科研内容创作。论文检索和证据整理由 Skill 脚本完成，最终中文文案由 Agent 根据 Evidence Pack 撰写。

## 1. 安装 Skill

在支持 Skills 的 Agent 对话中直接发送：

```text
Help me install Paper2XHS from https://github.com/GetIT-Sunday/xhs-rl-paper-share with Skills. Install the repository root as the paper2xhs skill.
```

安装完成后，新开一个对话，或刷新当前对话的 Skills。

也可以手动安装到 Codex Skills 目录：

```bash
git clone https://github.com/GetIT-Sunday/xhs-rl-paper-share.git \
  "${CODEX_HOME:-$HOME/.codex}/skills/paper2xhs"
```

不要只复制一个脚本。Skill 需要保留整个 `paper2xhs/` 目录中的 `SKILL.md`、`scripts/`、`references/` 和 `assets/`。

## 2. 先生成一篇草稿

不登录也可以找论文和生成草稿。对 Agent 说：

```text
Use $paper2xhs to find a recent reinforcement learning paper, write an evidence-grounded Chinese Xiaohongshu post, create a paper-page cover, and show me the result without publishing.
```

Agent 会完成以下工作：

1. 从 arXiv 召回近期候选论文。
2. 按方向相关性、时效性、可解释性和证据完整度筛选。
3. 读取摘要，必要时阅读 PDF 全文。
4. 生成 Evidence Pack，记录来源、数字和关键原文。
5. 写出标题、正文、话题和论文首页封面。

生成结果会先展示给你。此时不会登录，也不会发布。

## 3. 配置小红书账号

需要发布时，对 Agent 说：

```text
Use $paper2xhs to open the local account setup wizard.
```

配置页面会在本机打开：

1. 点击“生成登录二维码”。
2. 使用小红书 App 扫码，并在手机上确认登录。
3. 检查页面显示的昵称和账号 ID 是否正确。
4. 点击“确认账号并返回对话”。

登录凭证保存在本机私有目录，不会写入仓库、发送到对话或交给 Agent 外部服务。保存配置本身不会发布内容，也不会开启定时任务。

如果二维码过期，直接在配置页重新生成。配置页默认 15 分钟后关闭。

## 4. 审核成稿

让 Agent 展示最终版本：

```text
Use $paper2xhs to show the verified account, title, body, topics, evidence scope, and cover before publishing.
```

重点检查：

- 标题是否准确、是否适合 20 字以内的展示空间。
- 每个数字、对比和结论是否有论文依据。
- 是否明确区分论文结果、个人解读和局限。
- 账号昵称和账号 ID 是否是你要发布的账号。
- 封面是否为目标论文，而不是其他缓存论文。

如果需要修改，直接告诉 Agent 具体要求，例如：

```text
把正文压缩到 500 字以内，保留方法、最重要的两个实验数字和局限，不改变论文结论。
```

## 5. 发布

确认稿件后，对 Agent 说：

```text
发布刚才确认的版本。
```

Agent 会在发布前再次核对登录账号，然后上传封面、正文和话题。发布结果会写入本机发布记录。

发布接口偶尔可能只返回平台内部笔记 ID，不返回分享链接。遇到这种情况不要重复发布，先在小红书账号中检查是否已经出现笔记。

## 6. 终端方式

如果你希望自己检查环境，可以在项目目录运行：

```bash
python3 scripts/paper2xhs.py doctor
python3 scripts/paper2xhs.py setup
python3 scripts/paper2xhs.py run fetch -- --count 5 --days 7
python3 scripts/paper2xhs.py prepare
```

需要登录时：

```bash
python3 scripts/paper2xhs.py configure
```

打开命令输出的本机 URL，完成扫码和账号确认。`prepare` 只生成候选草稿，不会发布。

## 7. 运行目录和文件

默认运行目录是 `~/.local/share/paper2xhs/`：

| 路径 | 内容 |
|---|---|
| `app/references/` | 候选论文、Evidence Pack 和草稿 |
| `app/assets/covers/` | 论文首页封面 |
| `data/` | 发布记录、反馈快照、策略权重和决策记录 |
| `cookie.json` | 本机登录缓存 |
| `config.json` | 已确认账号和凭证指纹 |

不同小红书账号建议使用不同运行目录：

```bash
PAPER2XHS_HOME="$HOME/.local/share/paper2xhs-account-b" \
  python3 scripts/paper2xhs.py doctor
```

## 8. 常见问题

### arXiv 返回 500 或暂时没有候选

这是远程接口的瞬时失败，不需要修改代码。稍后重试即可；Skill 会保留已有缓存。也可以把具体 arXiv 链接交给 Agent，让它直接处理指定论文。

### 为什么脚本生成的是模板，不是完整中文稿？

脚本负责稳定地召回论文、保存证据和生成结构化骨架。完整中文稿需要 Agent 阅读 Evidence Pack 后完成，这样才能根据上下文处理方法、数字、结论和局限。

### Evidence Pack 是什么？

Evidence Pack 是每篇论文的本地证据记录，包含 arXiv 链接、摘要片段、数字、术语，以及全文阅读后补充的页码和原文片段。它用于约束文案，减少偏题和事实夸大。

### 反馈闭环现在是否自动可用？

本地 CSV/JSON 导入可以使用。创作者中心在线采集还需要先核对真实字段映射；在字段语义确认前，不要把曝光、阅读、累计点赞或涨粉混用，也不要把账号净增粉归因到单篇笔记。

### 安装后需要改代码吗？

普通用户不需要改代码。安装 Skill、配置账号，然后通过 Agent 对话提出“找论文”“生成草稿”或“发布”等请求即可。

## 9. 进一步阅读

- [主 README](README.md)：项目能力、边界和架构概览
- [Skill instructions](SKILL.md)：Agent 调用规则
- [内容与证据指南](references/skill-content.md)：成稿字段和证据要求
- [运维指南](references/skill-operations.md)：登录、反馈采集和调度

