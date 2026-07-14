#!/usr/bin/env python3
"""
从 arXiv 抓取最新 RL 论文

用法：
  python3 fetch_papers.py --count 5
  python3 fetch_papers.py --category cs.LG --count 10
"""

import argparse
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime, timedelta
import urllib.request
import urllib.parse
import time

# RL 相关搜索关键词
RL_KEYWORDS = [
    "reinforcement learning",
    "deep reinforcement learning",
    "policy gradient",
    "Q-learning",
    "actor-critic",
    "PPO",
    "SAC",
    "offline RL",
    "multi-agent reinforcement learning",
    "embodied AI",
    "robot learning",
    "world model",
    "model-based RL",
]

# 已发布论文列表路径
PUBLISHED_PATH = Path(__file__).parent.parent / "references" / "published_papers.json"


def load_published_ids():
    """加载已发布论文 ID 列表"""
    if not PUBLISHED_PATH.exists():
        return set()
    with open(PUBLISHED_PATH, "r") as f:
        data = json.load(f)
    return {item["arxiv_id"] for item in data.get("published", [])}


def fetch_arxiv_papers(query, max_results=10, days=7):
    """从 arXiv API 抓取论文"""
    # 计算7天前的日期
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    
    # 构建 arXiv API URL
    base_url = "http://export.arxiv.org/api/query?"
    params = {
        "search_query": f'all:"{query}" AND submittedDate:[{start_date}000000 TO 999999999999]',
        "start": 0,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    url = base_url + urllib.parse.urlencode(params)
    
    print(f"🔍 搜索 arXiv: {query}")
    print(f"   URL: {url[:100]}...")
    
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            xml_data = resp.read().decode("utf-8")
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return []
    
    # 解析 XML
    root = ET.fromstring(xml_data)
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    
    papers = []
    for entry in root.findall("atom:entry", ns):
        title = entry.find("atom:title", ns).text.strip().replace("\n", " ")
        summary = entry.find("atom:summary", ns).text.strip().replace("\n", " ")
        arxiv_id = entry.find("atom:id", ns).text.split("/")[-1]
        published = entry.find("atom:published", ns).text[:10]
        
        # 提取作者
        authors = [a.find("atom:name", ns).text for a in entry.findall("atom:author", ns)]
        
        # 提取分类
        categories = [c.get("term") for c in entry.findall("atom:category", ns)]
        
        papers.append({
            "arxiv_id": arxiv_id,
            "title": title,
            "summary": summary,
            "authors": authors[:5],  # 最多5个作者
            "published": published,
            "categories": categories,
            "arxiv_url": f"https://arxiv.org/abs/{arxiv_id}",
            "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}",
        })
    
    print(f"   找到 {len(papers)} 篇论文")
    return papers


def main():
    parser = argparse.ArgumentParser(description="抓取最新 RL 论文")
    parser.add_argument("--count", type=int, default=5, help="每个关键词抓取数量")
    parser.add_argument("--days", type=int, default=7, help="搜索最近N天的论文")
    parser.add_argument("--output", default=None, help="输出文件路径")
    args = parser.parse_args()
    
    published_ids = load_published_ids()
    print(f"📋 已发布论文: {len(published_ids)} 篇")
    
    all_papers = []
    seen_ids = set()
    
    for keyword in RL_KEYWORDS:
        papers = fetch_arxiv_papers(keyword, max_results=args.count, days=args.days)
        for paper in papers:
            if paper["arxiv_id"] not in seen_ids and paper["arxiv_id"] not in published_ids:
                all_papers.append(paper)
                seen_ids.add(paper["arxiv_id"])
        time.sleep(3)  # 避免请求过快
    
    # 去重并按日期排序
    all_papers.sort(key=lambda x: x["published"], reverse=True)
    
    print(f"\n✅ 共找到 {len(all_papers)} 篇未发布的 RL 论文")
    
    # 输出结果
    output_path = args.output or str(Path(__file__).parent.parent / "references" / "fetched_papers.json")
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump({"fetched_at": datetime.now().isoformat(), "papers": all_papers}, f, ensure_ascii=False, indent=2)
    
    print(f"💾 已保存到: {output_path}")
    
    # 打印前5篇
    for i, paper in enumerate(all_papers[:5]):
        print(f"\n--- 论文 {i+1} ---")
        print(f"  ID: {paper['arxiv_id']}")
        print(f"  标题: {paper['title'][:80]}")
        print(f"  日期: {paper['published']}")
        print(f"  作者: {', '.join(paper['authors'][:3])}{'...' if len(paper['authors']) > 3 else ''}")


if __name__ == "__main__":
    main()
