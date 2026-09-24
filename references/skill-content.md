# 成稿契约与策略归因

`generate` 是确定性模板；当前 Agent 在阅读 Evidence Pack 后完成中文成稿。推荐标题不超过 20 字，正文清楚交代问题、方法、证据支持的结果和局限，话题与论文领域一致。类比标为解释性类比，勿混作论文实验；没有证据的增益百分比不写。

保持生成 JSON 的字段：

- `arxiv_id`、`original_title`、`abstract`、`categories`：来自真实论文，不改写来源。
- `xhs_title`、`xhs_content`：修改为最终中文稿，正文不用 Markdown 加粗。
- `evidence_pack`：真实证据文件绝对路径。新增全文依据时在该包中追加来源章节/页码和原文片段；不能扩大 `source.scope` 却不存依据。
- `selected_strategy`：实际采用的一种表达策略。`strategy_tags` 只放这一种；`candidate_strategy_tags` 是候选，不能全部领取反馈。
- `policy_version`、`strategy_weights_snapshot`：保留当时决策依据。Agent 改选策略时记录 `strategy_selection_reason` 为具体原因，不能冒充权重自动选择。
- `generator`：Agent 改写后改成 `paper2xhs_agent_v1`，避免调度器把成稿当模板重写。

从 `prepare` 得到的模板位于 `<data>`；Agent 成稿保存到 `<app>/references/content_<ID>.json`（ID 中点换下划线），让调度器能发现并保留它。`generate` 生成的模板本来就在该目录，可直接改写并更改 `generator`。生成后返回可点击文件路径和正文预览。

策略值：`abstract_explainer`、`counterintuitive`、`cross_domain_analogy`、`formula_breakdown`、`hot_topic`。没有可用历史反馈时默认中性解释；用户明确选择写作方式时遵从并记录原因。

确认文案每条核心断言有来源后执行 `run evidence -- --content <成稿> --evidence <证据包>`。该检查器发现不支持的数字时退出码为 2，但并不理解所有中文语义。编号、年份和链接也可能误报，逐项检查，不为让测试通过而删除证据。

封面默认取论文首页；`cover` 只需 PDF 渲染依赖。AI 重新设计封面是可选功能，需用户配置图像能力；不宣称 Skill 附带免费生图服务。
