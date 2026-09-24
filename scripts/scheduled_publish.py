#!/usr/bin/env python3
"""
定时发布调度脚本 —— 时间轮换策略

每天 9:00 由定时任务触发，脚本自己判断今天应该在哪个时间槽发布。
时间槽序列：9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22
循环重复（14天一轮）。

状态存储于 references/publish_state.json：
  slot_index         : 上次使用的时间槽下标（0-13）
  last_published_date: 上次发布日期 YYYY-MM-DD

运行逻辑：
  1. 读取状态，计算今天应使用的时间槽（上次+1，取模14）
  2. 获取目标小时（slot_hours[slot_index]）
  3. 当前时间 < 目标小时 → sleep 到目标时间再执行
  4. 当前时间 >= 目标小时+1 → 已错过，立即执行（补发）
  5. 执行完整发布流程
  6. 更新状态文件
"""

import json
import os
import sys
import time
import subprocess
from datetime import datetime, date
from pathlib import Path

from feedback import DATA_DIR, atomic_text, utcnow
from paper_pipeline import rank_papers, load_strategy_policy, strategy_weights_path, build_evidence_pack
from publication_store import load_published, paper_id
from generate_content import generate_content

BASE_DIR = Path(__file__).parent.parent
STATE_PATH = DATA_DIR / "publish_state.json"
SKILL_DIR = BASE_DIR

# 时间槽序列：9点到22点，共14个槽
SLOT_HOURS = [9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22]


def load_state() -> dict:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text())
        except Exception:
            pass
    return {"slot_index": 0, "last_published_date": ""}


def save_state(slot_index: int, published_date: str):
    state = {"slot_index": slot_index, "last_published_date": published_date}
    atomic_text(STATE_PATH, json.dumps(state, ensure_ascii=False, indent=2))
    print(f"✅ 状态已保存: slot={slot_index}({SLOT_HOURS[slot_index]}点), date={published_date}")


def get_today_slot(state: dict) -> int:
    """
    计算今天应使用的时间槽下标。
    若今天已发布过，返回 -1（跳过）。
    """
    today = date.today().isoformat()
    if state.get("last_published_date") == today:
        print(f"⏭️  今天（{today}）已发布过，跳过")
        return -1

    last_index = state.get("slot_index", -1)
    next_index = (last_index + 1) % len(SLOT_HOURS)
    return next_index


def wait_until_hour(target_hour: int):
    """等待直到目标小时整点（最多等到 target_hour:05）"""
    now = datetime.now()
    if now.hour > target_hour:
        print(f"⚡ 当前 {now.hour}:{now.minute:02d}，已过目标时间 {target_hour}:00，立即执行")
        return
    if now.hour == target_hour:
        print(f"✅ 当前已在目标小时 {target_hour}:00，立即执行")
        return

    # 计算需要等待的秒数
    target_dt = now.replace(hour=target_hour, minute=0, second=0, microsecond=0)
    wait_sec = (target_dt - now).total_seconds()
    print(f"⏰ 当前 {now.strftime('%H:%M')}，等待到 {target_hour}:00（{wait_sec/60:.1f} 分钟后）")
    time.sleep(wait_sec)
    print(f"⏰ 已到达目标时间 {target_hour}:00，开始发布")


def prepare_next_content(base_dir=BASE_DIR, data_dir=DATA_DIR):
    """Rerank cached AND newly fetched papers; preserve externally authored text."""
    reference = base_dir / "references"
    published = {paper_id(p.get("arxiv_id")) for p in load_published()["published"]}
    policy = load_strategy_policy(data_dir / "strategy_weights.json")
    papers, drafts = {}, {}
    fetched = reference / "fetched_papers.json"
    if fetched.exists():
        for p in json.loads(fetched.read_text()).get("papers", []):
            papers[paper_id(p.get("arxiv_id"))] = p
    for cf in sorted(reference.glob("content_*.json")):
        try:
            d = json.loads(cf.read_text())
            key = paper_id(d.get("arxiv_id"))
            if not key:
                continue
            drafts[key] = (cf, d)
            papers.setdefault(key, {"arxiv_id": d["arxiv_id"], "title": d.get("original_title", ""),
                                    "summary": d.get("abstract", ""), "categories": d.get("categories", [])})
        except (OSError, ValueError, KeyError):
            continue
    candidates = [p for key, p in papers.items() if key and key not in published]
    ranked = rank_papers(candidates, published, policy["weights"])
    if not ranked:
        return None
    selected = ranked[0]
    key = paper_id(selected["arxiv_id"])
    cached_path, cached = drafts.get(key, (None, {}))
    # Existing manually edited/older drafts are immutable. Their selection still
    # uses current ranking, but their style attribution must stay historical.
    if cached_path and cached.get("generator") != "paper2xhs_template_v2":
        target = cached_path
        strategy = cached.get("selected_strategy")
        content_policy = cached.get("policy_version")
    else:
        evidence = data_dir / ("evidence_" + key.replace(".", "_").replace("/", "_") + ".json")
        build_evidence_pack(selected, evidence)
        content = generate_content(selected, evidence, policy["weights"])
        content.update(policy_version=policy["version"], policy_updated_at=policy["updated_at"],
                       selection_score=selected["selection_score"])
        target = data_dir / ("content_" + key.replace(".", "_").replace("/", "_") + ".json")
        atomic_text(target, json.dumps(content, ensure_ascii=False, indent=2))
        strategy = content["selected_strategy"]
        content_policy = policy["version"]
    audit = {"at": utcnow(), "policy_version": policy["version"], "content_policy_version": content_policy,
             "selected_arxiv_id": selected["arxiv_id"], "selected_strategy": strategy,
             "candidate_scores": [{"arxiv_id": p["arxiv_id"], **p["selection_score"]} for p in ranked]}
    atomic_text(data_dir / "last_decision.json", json.dumps(audit, ensure_ascii=False, indent=2))
    return target


def run_publish() -> bool:
    """执行完整发布流程，返回是否成功"""
    print("\n" + "=" * 60)
    print("🚀 开始执行发布流程")
    print("=" * 60)

    try:
        subprocess.run([sys.executable, str(BASE_DIR / "scripts" / "fetch_papers.py"), "--count", "3"],
                       timeout=600, check=False)
    except (subprocess.TimeoutExpired, OSError):
        print("⚠️ 抓取失败，使用已有候选")
    target_content = prepare_next_content()
    if target_content is None:
        print("❌ 没有候选论文")
        return False

    cmd = [
        sys.executable,
        str(BASE_DIR / "scripts" / "publish_to_xhs.py"),
        "--content-json", str(target_content),
        "--force",
        "--mark-published",
    ]

    print(f"执行: {' '.join(cmd)}")
    result = subprocess.run(cmd, timeout=120)
    return result.returncode == 0


def refresh_feedback() -> bool:
    """Refresh private snapshots; a failed refresh keeps the previous policy."""
    endpoint = os.environ.get("XHS_METRICS_ENDPOINT")
    creator = os.environ.get("XHS_METRICS_MODE") == "creator"
    if not endpoint and not creator:
        return True
    collector = BASE_DIR / "scripts" / "collect_metrics.py"
    print("📊 刷新创作者中心指标快照")
    cmd = [sys.executable, str(collector)]
    if creator:
        cmd.append("--creator")
    try:
        result = subprocess.run(cmd, timeout=90, check=False)
    except subprocess.TimeoutExpired:
        print("⚠️ 指标采集超时，继续使用上一版策略")
        return False
    if result.returncode != 0:
        print("⚠️ 指标采集失败，继续使用上一版策略")
        return False
    return True


def main():
    print(f"\n🕐 scheduled_publish.py 启动 at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    state = load_state()
    slot_index = get_today_slot(state)

    if slot_index == -1:
        print("今日已发布，退出")
        return 0

    target_hour = SLOT_HOURS[slot_index]
    print(f"📅 今日发布时间槽: {target_hour}:00 (slot #{slot_index})")

    wait_until_hour(target_hour)

    refresh_feedback()
    success = run_publish()

    if success:
        save_state(slot_index, date.today().isoformat())
        print(f"\n✅ 今日发布完成！下次发布时间: {SLOT_HOURS[(slot_index + 1) % len(SLOT_HOURS)]}:00")
    else:
        print("\n❌ 发布失败，状态未更新（明天将重试同一时间槽）")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
