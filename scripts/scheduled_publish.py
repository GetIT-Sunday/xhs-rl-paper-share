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
import sys
import time
import subprocess
from datetime import datetime, date
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
STATE_PATH = BASE_DIR / "references" / "publish_state.json"
PUBLISHED_PATH = BASE_DIR / "references" / "published_papers.json"
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
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2))
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


def run_publish() -> bool:
    """执行完整发布流程，返回是否成功"""
    print("\n" + "=" * 60)
    print("🚀 开始执行发布流程")
    print("=" * 60)

    # 调用 xhs-rl-paper-share skill 的主流程
    # 使用 publish_to_xhs.py，不传 cookie（自动从 cookie_manager 读取）
    # 先找一篇未发布的论文
    published_ids = set()
    if PUBLISHED_PATH.exists():
        data = json.loads(PUBLISHED_PATH.read_text())
        published_ids = {p["arxiv_id"] for p in data.get("published", [])}

    # 检查是否有预先缓存的待发文案
    content_files = sorted(
        (BASE_DIR / "references").glob("content_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    target_content = None
    for cf in content_files:
        try:
            d = json.loads(cf.read_text())
            arxiv_id = d.get("arxiv_id", "")
            if arxiv_id and arxiv_id not in published_ids:
                target_content = cf
                print(f"📄 找到待发文案: {cf.name} (arXiv: {arxiv_id})")
                break
        except Exception:
            continue

    if target_content is None:
        print("❌ 没有找到待发文案，请先运行一次手动发布以生成文案缓存")
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
