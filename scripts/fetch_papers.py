#!/usr/bin/env python3
"""
从 arXiv 抓取最新 RL 论文

用法：
  python3 fetch_papers.py --count 5
  python3 fetch_papers.py --days 14 --count 10
"""

import argparse
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime, timedelta, timezone
import urllib.request
import urllib.parse
import urllib.error
import time
import sys

sys.path.insert(0, str(Path(__file__).parent))
from paper_pipeline import load_strategy_policy, rank_papers, strategy_weights_path
from publication_store import load_published, paper_id
from feedback import atomic_text

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

def load_published_ids():
    return {paper_id(item.get("arxiv_id")) for item in load_published()["published"]}


def build_search_query(query, days=7, now=None):
    """Use real UTC dates in arXiv's YYYYMMDDHHMM range."""
    if days <= 0:
        raise ValueError("days must be positive")
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    start = now - timedelta(days=days)
    start_date = start.strftime("%Y%m%d0000")
    end_date = now.strftime("%Y%m%d%H%M")
    return f'all:"{query}" AND submittedDate:[{start_date} TO {end_date}]'


def fetch_arxiv_papers(query, max_results=10, days=7, retries=2):
    """从 arXiv API 抓取论文"""
    # 构建 arXiv API URL
    base_url = "https://export.arxiv.org/api/query?"
    params = {
        "search_query": build_search_query(query, days=days),
        "start": 0,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    url = base_url + urllib.parse.urlencode(params)
    
    print(f"🔍 搜索 arXiv: {query}")
    print(f"   URL: {url[:100]}...")
    
    last_error = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "Paper2XHS/0.1 (arXiv reader)"}
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                xml_data = resp.read().decode("utf-8")
            break
        except (OSError, UnicodeError) as exc:
            last_error = exc
            if isinstance(exc, urllib.error.HTTPError) and exc.code not in (429, 500, 502, 503, 504):
                raise RuntimeError(f"arXiv HTTP {exc.code}") from exc
            if attempt < retries:
                wait = 3 * (2 ** attempt)
                print(f"⚠️ 请求失败，{wait} 秒后重试 ({attempt + 1}/{retries})")
                time.sleep(wait)
    else:
        raise RuntimeError(f"arXiv 请求失败（已重试 {retries} 次）: {last_error}") from last_error
    
    # 解析 XML
    try:
        root = ET.fromstring(xml_data)
    except ET.ParseError as exc:
        raise RuntimeError("arXiv 返回无效 XML") from exc
    if root.tag != "{http://www.w3.org/2005/Atom}feed":
        raise RuntimeError("arXiv 返回非 Atom 数据")
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    
    papers = []
    for entry in root.findall("atom:entry", ns):
        if entry.findtext("atom:id", default="", namespaces=ns).startswith("http://arxiv.org/api/errors"):
            raise RuntimeError("arXiv 返回查询错误")
        if not all(entry.findtext("atom:" + field, default="", namespaces=ns).strip()
                   for field in ("title", "summary", "id", "published")):
            raise RuntimeError("arXiv 返回不完整论文数据")
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
    if args.count <= 0 or args.days <= 0:
        parser.error("--count 和 --days 必须为正整数")
    
    published_ids = load_published_ids()
    print(f"📋 已发布论文: {len(published_ids)} 篇")
    
    all_papers = []
    seen_ids = set()
    successful_queries = 0
    failures = []
    
    for keyword in RL_KEYWORDS:
        try:
            papers = fetch_arxiv_papers(keyword, max_results=args.count, days=args.days)
            successful_queries += 1
        except RuntimeError as exc:
            failures.append(f"{keyword}: {exc}")
            print(f"❌ {exc}")
            papers = []
        for paper in papers:
            if paper_id(paper["arxiv_id"]) not in seen_ids and paper_id(paper["arxiv_id"]) not in published_ids:
                all_papers.append(paper)
                seen_ids.add(paper_id(paper["arxiv_id"]))
        time.sleep(3)  # 避免请求过快
    
    if failures:
        print(f"\n❌ {len(failures)} 项查询失败，{successful_queries} 项成功；结果不完整，已有候选文件保持不变。", file=sys.stderr)
        print("   可以稍后重试；已有候选仍可使用。", file=sys.stderr)
        return 2

    # 去重并按日期排序
    # Rank by relevance, freshness, evidence availability and novelty.  The
    # component scores are persisted with each candidate for auditability.
    weights_path = strategy_weights_path()
    policy = load_strategy_policy(weights_path)
    strategy_weights = policy["weights"]
    all_papers = rank_papers(all_papers, published_ids, strategy_weights)
    
    print(f"\n✅ 共找到 {len(all_papers)} 篇未发布的 RL 论文")
    
    # 输出结果
    output_path = args.output or str(Path(__file__).parent.parent / "references" / "fetched_papers.json")
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    payload = {"fetched_at": datetime.now(timezone.utc).isoformat(), "ranking": "paper_pipeline.score_paper", "policy_version": policy["version"], "papers": all_papers}
    atomic_text(output_path, json.dumps(payload, ensure_ascii=False, indent=2))
    
    print(f"💾 已保存到: {output_path}")
    
    # 打印前5篇
    for i, paper in enumerate(all_papers[:5]):
        print(f"\n--- 论文 {i+1} ---")
        print(f"  ID: {paper['arxiv_id']}")
        print(f"  标题: {paper['title'][:80]}")
        print(f"  日期: {paper['published']}")
        print(f"  选题分: {paper['selection_score']['total']:.3f}")
        print(f"  作者: {', '.join(paper['authors'][:3])}{'...' if len(paper['authors']) > 3 else ''}")


if __name__ == "__main__":
    raise SystemExit(main())
