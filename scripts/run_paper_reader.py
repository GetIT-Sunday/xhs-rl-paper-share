#!/usr/bin/env python3
"""
后台驱动脚本：调用 arxiv-paper-reader skill 生成论文精读报告。
由 publish_to_xhs.py 以子进程方式非阻塞启动。

用法：
  python3 run_paper_reader.py --arxiv-id 2606.24014 --output /path/to/report.md
"""

import argparse
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--arxiv-id", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    # arxiv-paper-reader skill 的主脚本
    skill_dir = Path(__file__).parent.parent.parent / "arxiv-paper-reader"
    reader_scripts = list(skill_dir.glob("scripts/*.py"))

    if not reader_scripts:
        print(f"❌ 未找到 arxiv-paper-reader 脚本", file=sys.stderr)
        sys.exit(1)

    # 找入口脚本（优先 main.py / reader.py / arxiv_paper_reader.py）
    entry = None
    for name in ["main.py", "reader.py", "arxiv_paper_reader.py", "run.py"]:
        candidate = skill_dir / "scripts" / name
        if candidate.exists():
            entry = candidate
            break
    if entry is None:
        entry = reader_scripts[0]

    result = subprocess.run(
        [sys.executable, str(entry),
         "--arxiv-id", args.arxiv_id,
         "--output", args.output],
        timeout=300,
    )
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
