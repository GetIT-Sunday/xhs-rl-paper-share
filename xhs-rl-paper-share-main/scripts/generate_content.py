#!/usr/bin/env python3
"""
基于论文生成小红书爆款文案

用法：
  python3 generate_content.py --arxiv-id 2301.12345
  python3 generate_content.py --paper-json /path/to/paper.json
"""

import argparse
import json
import re
import sys
from pathlib import Path
from datetime import datetime

# 小红书爆款文案模板
TEMPLATE = """{title_intro}

{intro_sentence}

📕《{paper_title}》
{content_paragraph}

{tags}"""

# 标题党关键词
TITLE_HOOKS = [
    "这篇论文太重要了！",
    "RL领域重磅综述！",
    "强化学习新突破！",
    "具身智能+RL，这个方向要火了！",
    "这篇综述把RL讲透了！",
    "RL入门必看！",
    "深度解读：这篇论文改变了我对RL的认知",
    "2024年RL论文精选：{title}",
    "分享一篇RL论文，{short_title}",
]

# 引入句
INTRO_SENTENCES = [
    "从最新 arXiv 论文中挖到一篇好文，来分享一下！",
    "最近在读强化学习相关论文，这篇很有价值：",
    "整理 RL 论文时发现的宝藏文章，推荐给大家：",
    "这篇论文解答了我很多关于强化学习的疑问：",
    "具身智能和强化学习的结合，这篇论文讲得很清楚：",
]


def generate_title(paper_title, paper_summary):
    """生成标题党标题"""
    # 提取核心关键词
    keywords = extract_keywords(paper_summary)
    
    # 判断论文类型
    if "survey" in paper_title.lower() or "review" in paper_title.lower():
        prefix = "分享一篇RL综述，"
        suffix = "推荐！" if len(paper_title) < 50 else ""
        return f"{prefix}{paper_title[:40]}{'...' if len(paper_title) > 40 else ''}{suffix}"
    
    # 通用标题
    short_title = paper_title[:30]
    hook = TITLE_HOOKS[0] if len(paper_title) < 40 else f"分享一篇RL论文：{short_title}"
    return hook


def extract_keywords(text):
    """从摘要中提取关键词"""
    keywords = []
    rl_keywords = [
        "强化学习", "reinforcement learning", "policy gradient",
        "Q-learning", "PPO", "SAC", "offline RL", "多智能体",
        "具身智能", "embodied AI", "robot learning", "world model"
    ]
    
    text_lower = text.lower()
    for kw in rl_keywords:
        if kw.lower() in text_lower:
            keywords.append(kw)
    
    return keywords[:5]


def generate_content_paragraph(paper_title, paper_summary, max_length=500):
    """生成正文段落"""
    # 清理摘要
    summary = paper_summary.replace("\n", " ").strip()
    
    # 截断过长内容
    if len(summary) > max_length:
        # 尝试在句号处截断
        sentences = re.split(r'[.!?。！？]', summary)
        content = ""
        for sent in sentences:
            if len(content + sent) < max_length - 50:
                content += sent + "。"
            else:
                break
        summary = content.strip()
    
    # 添加过渡
    intro = "这篇文章" if "survey" not in paper_title.lower() else "这篇综述文章"
    
    return f"{intro}主要探讨了{summary}"


def generate_tags(paper_summary):
    """生成话题标签"""
    base_tags = ["#机器学习", "#强化学习"]
    
    # 根据内容添加细分标签
    if "embodied" in paper_summary.lower() or "robot" in paper_summary.lower():
        base_tags.append("#具身智能")
    if "multi-agent" in paper_summary.lower():
        base_tags.append("#多智能体")
    if "offline" in paper_summary.lower():
        base_tags.append("#离线强化学习")
    
    base_tags.extend(["#文献阅读", "#论文分享"])
    
    return " ".join(base_tags)


def generate_content(paper_data):
    """生成完整的小红书文案"""
    title = paper_data["title"]
    summary = paper_data["summary"]
    arxiv_id = paper_data["arxiv_id"]
    
    # 生成各部分
    xhs_title = generate_title(title, summary)
    intro_sentence = INTRO_SENTENCES[0]  # 可随机选择
    content_para = generate_content_paragraph(title, summary)
    tags = generate_tags(summary)
    
    # 组合
    content = TEMPLATE.format(
        title_intro=xhs_title,
        intro_sentence=intro_sentence,
        paper_title=title[:80],  # 限制标题长度
        content_paragraph=content_para,
        tags=tags
    )
    
    return {
        "xhs_title": xhs_title,
        "xhs_content": content,
        "arxiv_id": arxiv_id,
        "original_title": title,
        "abstract": paper_data.get("summary", ""),
        "categories": paper_data.get("categories", ["cs.LG"]),
        "generated_at": datetime.now().isoformat()
    }


def main():
    parser = argparse.ArgumentParser(description="生成小红书文案")
    parser.add_argument("--arxiv-id", help="arXiv 论文 ID")
    parser.add_argument("--paper-json", help="论文 JSON 文件路径")
    parser.add_argument("--output", default=None, help="输出文件路径")
    args = parser.parse_args()
    
    # 读取论文数据
    if args.paper_json:
        with open(args.paper_json, "r") as f:
            paper_data = json.load(f)
            if "papers" in paper_data:
                paper_data = paper_data["papers"][0]  # 取第一篇
    elif args.arxiv_id:
        # 从抓取的论文列表中查找
        fetched_path = Path(__file__).parent.parent / "references" / "fetched_papers.json"
        if fetched_path.exists():
            with open(fetched_path, "r") as f:
                data = json.load(f)
                for p in data.get("papers", []):
                    if p["arxiv_id"] == args.arxiv_id:
                        paper_data = p
                        break
                else:
                    print(f"❌ 未找到论文: {args.arxiv_id}")
                    sys.exit(1)
        else:
            print(f"❌ 请先运行 fetch_papers.py 抓取论文")
            sys.exit(1)
    else:
        print("❌ 请提供 --arxiv-id 或 --paper-json")
        sys.exit(1)
    
    # 生成文案
    result = generate_content(paper_data)
    
    # 输出
    print("=" * 60)
    print("📝 小红书文案")
    print("=" * 60)
    print(f"\n【标题】\n{result['xhs_title']}")
    print(f"\n【正文】\n{result['xhs_content']}")
    print(f"\n【元信息】")
    print(f"  arXiv ID: {result['arxiv_id']}")
    print(f"  原标题: {result['original_title'][:60]}...")
    print(f"  生成时间: {result['generated_at']}")
    
    # 保存
    output_path = args.output or str(
        Path(__file__).parent.parent / "references" / 
        f"content_{result['arxiv_id'].replace('.', '_')}.json"
    )
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 已保存到: {output_path}")


if __name__ == "__main__":
    main()
