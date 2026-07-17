import json
from pathlib import Path

path = Path(__file__).resolve().parent.parent / "outputs" / "2606.06473" / "analysis" / "report.json"
data = json.loads(path.read_text(encoding="utf-8"))
data.update({
    "one_sentence": "MLEvolve 让机器学习 Agent 在不断试错中记住经验、借鉴其他分支，并逐步把搜索从发散变成收敛。",
    "problem": "现有 Agent 容易重复失败：不同搜索分支互不相通，没有长期记忆，而且每次都重写整段代码。",
    "method": "Progressive MCGS 负责‘怎么搜’，Retrospective Memory 负责‘记住什么’，自适应编码负责‘改多少代码’。三者组合，让 Agent 先广泛探索，再集中改进最有希望的方案。",
    "conclusion": "这篇论文的关键不是多加几个 Agent，而是让每次尝试都能留下经验，并在后续搜索中真正用起来。",
})
path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
