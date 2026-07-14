#!/usr/bin/env python3
"""
发布论文笔记到小红书

用法：
  # 发布单篇论文
  python3 publish_to_xhs.py --arxiv-id 2301.12345 --cookie 'a1=xxx;web_session=xxx;webId=xxx'

  # 发布已生成的文案（私密预览）
  python3 publish_to_xhs.py --content-json /path/to/content.json --cookie '...' --private

  # 发布并更新已发布列表
  python3 publish_to_xhs.py --arxiv-id 2301.12345 --cookie '...' --mark-published

  # 定时发布
  python3 publish_to_xhs.py --arxiv-id 2301.12345 --cookie '...' --schedule '2026-07-03 09:00:00'
"""

import argparse
import json
import sys
import os
import subprocess
from pathlib import Path
from datetime import datetime, timedelta

try:
    from xhs import XhsClient
    from xhshow import Xhshow
    _HAS_XHS = True
except ImportError:
    _HAS_XHS = False

# 路径
BASE_DIR = Path(__file__).parent.parent
PUBLISHED_PATH = BASE_DIR / "references" / "published_papers.json"
COVERS_DIR = BASE_DIR / "assets" / "covers"
CONTENT_DIR = BASE_DIR / "references"


def parse_cookie(cookie_str):
    """解析 Cookie 字符串"""
    cookie = {}
    for item in cookie_str.split(';'):
        item = item.strip()
        if '=' in item:
            key, value = item.split('=', 1)
            cookie[key.strip()] = value.strip()
    return cookie


def load_published_list():
    """加载已发布论文列表"""
    if not PUBLISHED_PATH.exists():
        return {"published": []}
    with open(PUBLISHED_PATH, "r") as f:
        return json.load(f)


def save_published_list(data):
    """保存已发布论文列表"""
    PUBLISHED_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(PUBLISHED_PATH, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"💾 已更新发布列表: {PUBLISHED_PATH}")


def create_xhs_client(cookie_str):
    """创建带签名的小红书客户端

    注：xhs 库对 is_creator=True 的请求（如发布笔记的 get_upload_files_permit、
    create_image_note）会绕过传入的 sign 回调，转而调用库内置的 xhs.help.sign()——
    该算法是早期版本硬编码的签名规则，早已被小红书风控识别为无效签名，服务端会
    返回 code=-100「无登录信息」（实际是签名校验失败，而非真的未登录）。
    这里将 xhs.core.sign 替换为基于 xhshow 的实时签名，让创作者接口与普通接口
    共用同一套有效签名逻辑。
    """
    if not _HAS_XHS:
        print("❌ 缺少依赖，请安装：pip install xhs xhshow", file=sys.stderr)
        sys.exit(1)
    cookie = parse_cookie(cookie_str)
    signer = Xhshow()

    # 签名函数（用于普通 web 接口，is_creator=False）
    def sign_func(url, data, a1=None, web_session=None):
        return signer.sign_headers_post(
            uri=url,
            cookies=cookie,
            payload=data if data else {},
            x_rap=True,
        )

    _patch_creator_sign(signer, cookie)

    return XhsClient(cookie=cookie_str, sign=sign_func)


def _patch_creator_sign(signer, cookie):
    """将 xhs.core 内置的过时签名函数替换为 xhshow 实时签名（仅影响 is_creator=True 请求）"""
    import xhs.core as _xhs_core

    def _real_sign(uri, data=None, ctime=None, a1="", b1=""):
        headers = signer.sign_headers_post(
            uri=uri,
            cookies=cookie,
            payload=data if data else {},
            x_rap=True,
        )
        return {
            "x-s": headers["x-s"],
            "x-t": headers["x-t"],
            "x-s-common": headers["x-s-common"],
        }

    _xhs_core.sign = _real_sign


def generate_cover(arxiv_id, title="", abstract="", categories=None):
    """生成论文封面图（使用 GPT Image + 文字叠加）"""
    cover_path_png = COVERS_DIR / f"{arxiv_id.replace('.', '_')}.png"
    cover_path_jpg = COVERS_DIR / f"{arxiv_id.replace('.', '_')}.jpg"

    if cover_path_png.exists():
        print(f"✅ 封面已存在: {cover_path_png}")
        return str(cover_path_png)
    if cover_path_jpg.exists():
        print(f"✅ 封面已存在: {cover_path_jpg}")
        return str(cover_path_jpg)

    script = Path(__file__).parent / "capture_cover.py"
    cmd = [
        sys.executable, str(script),
        "--arxiv-id", arxiv_id,
        "--output", str(cover_path_png),
    ]
    if title:
        cmd += ["--title", title]
    if abstract:
        cmd += ["--abstract", abstract[:300]]
    if categories:
        cmd += ["--categories", ",".join(categories)]

    result = subprocess.run(cmd, timeout=250)

    if result.returncode != 0:
        print("❌ 封面生成失败")
        return None

    return str(cover_path_png) if cover_path_png.exists() else None


def generate_content(arxiv_id):
    """生成小红书文案"""
    content_json = CONTENT_DIR / f"content_{arxiv_id.replace('.', '_')}.json"

    if content_json.exists():
        with open(content_json, "r") as f:
            data = json.load(f)
        print(f"✅ 使用已生成的文案: {content_json}")
        return data

    # 调用 generate_content.py
    script = Path(__file__).parent / "generate_content.py"
    result = subprocess.run(
        [sys.executable, str(script), "--arxiv-id", arxiv_id],
        timeout=60
    )

    if result.returncode != 0:
        print("❌ 文案生成失败")
        return None

    # 重新读取
    if content_json.exists():
        with open(content_json, "r") as f:
            return json.load(f)

    return None


def generate_reading_report(arxiv_id, title=""):
    """
    用 arxiv-paper-reader skill 生成论文精读报告。
    在子进程中异步启动，不阻塞主发布流程。
    返回子进程对象（调用方负责 wait / poll）。
    """
    arxiv_reader_skill = (
        Path(__file__).parent.parent.parent / "arxiv-paper-reader" / "SKILL.md"
    )
    if not arxiv_reader_skill.exists():
        print("⚠️  arxiv-paper-reader skill 未安装，跳过精读报告", file=sys.stderr)
        return None

    # 构造 prompt：让 arxiv-paper-reader 生成精读报告
    report_dir = BASE_DIR / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"report_{arxiv_id.replace('.', '_')}.md"

    if report_path.exists():
        print(f"✅ 精读报告已存在: {report_path}")
        return None

    print(f"📖 启动论文精读报告生成（arXiv: {arxiv_id}）...")

    # 通过 kiro-cli 的 skill 机制调用 arxiv-paper-reader
    # 采用 subprocess 非阻塞启动
    proc = subprocess.Popen(
        [
            sys.executable,
            str(Path(__file__).parent / "run_paper_reader.py"),
            "--arxiv-id", arxiv_id,
            "--output", str(report_path),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return proc


def fetch_topics(client, tag_names: list) -> list:
    """
    将话题名称列表转为 xhs API 所需的结构化 topic 对象列表。
    失败时降级返回空列表，不中断发布流程。
    """
    topics = []
    for name in tag_names:
        try:
            results = client.get_suggest_topic(keyword=name.lstrip("#"))
            if results:
                topics.append(results[0])
        except Exception as e:
            print(f"⚠️  话题查询失败 [{name}]: {e}", file=sys.stderr)
    print(f"   话题数: {len(topics)}/{len(tag_names)}")
    return topics


def extract_tags_from_content(content: str) -> list:
    """从正文中提取 #话题 标签列表"""
    import re
    return re.findall(r'#[\w\u4e00-\u9fff·]+', content)


def _clean_markdown(text: str) -> str:
    """清理小红书不支持的 markdown 语法。

    小红书 API 不渲染 markdown，**加粗**、*斜体* 等会直接显示原始符号。
    在文案中保留语义可读性，但去掉或替换 markdown 符号。
    """
    import re
    # 1. **加粗** → 去掉 **，保留文字（文字本身可读）
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    # 2. *斜体* → 去掉 *
    text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'\1', text)
    # 3. __下划线__ → 去掉 __
    text = re.sub(r'__(.+?)__', r'\1', text)
    # 4. ~~删除线~~ → 去掉 ~~
    text = re.sub(r'~~(.+?)~~', r'\1', text)
    # 5. `行内代码` → 去掉 `
    text = re.sub(r'`(.+?)`', r'\1', text)
    return text


def publish_note(client, content_data, cover_path, is_private=False, schedule_time=None):
    """发布笔记"""
    title = content_data["xhs_title"]
    desc = content_data["xhs_content"]

    # 从正文提取话题标签并查询结构化 topic 对象
    tag_names = extract_tags_from_content(desc)
    topics = fetch_topics(client, tag_names) if tag_names else []

    print(f"\n📤 发布设置")
    print(f"   标题: {title[:50]}...")
    print(f"   私密: {'是' if is_private else '否'}")
    if schedule_time:
        print(f"   定时: {schedule_time}")

    try:
        result = client.create_image_note(
            title=title,
            desc=desc,
            files=[cover_path],
            is_private=is_private,
            post_time=schedule_time,
            topics=topics if topics else None,
        )
        
        # 提取笔记 ID
        note_id = result.get("data", {}).get("id", "")
        share_link = result.get("share_link", "")
        
        print(f"\n✅ 发布成功!")
        print(f"   笔记 ID: {note_id}")
        print(f"   链接: {share_link}")
        
        return {
            "success": True,
            "note_id": note_id,
            "share_link": share_link,
            "raw_result": result
        }
    
    except Exception as e:
        print(f"\n❌ 发布失败: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e)
        }


def save_to_draft_via_browser(content_data: dict, cover_path: str) -> dict:
    """通过 Chrome Bridge 填写发布表单并保存到草稿箱。

    依赖：
      - bridge_server.py 正在运行（ws://localhost:9333）
      - 已安装 XHS Bridge Chrome 扩展并连接到 bridge_server
      - 本地 Chrome 已打开并登录小红书创作者中心

    Returns:
        {"success": bool, "error": str | None}
    """
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).parent))
    try:
        from xhs_browser import BridgePage, fill_publish_form, save_as_draft, PublishError
        from xhs_browser.types import PublishImageContent
    except ImportError as e:
        return {"success": False, "error": f"xhs_browser 模块导入失败: {e}"}

    page = BridgePage()

    if not page.is_server_running():
        return {
            "success": False,
            "error": (
                "bridge server 未运行，请先启动：\n"
                "  python3 bridge_server.py\n"
                "并确认 XHS Bridge Chrome 扩展已安装并连接。"
            ),
        }

    if not page.is_extension_connected():
        return {
            "success": False,
            "error": (
                "XHS Bridge 扩展未连接到 bridge server。\n"
                "请在 Chrome 中安装并启用 XHS Bridge 扩展，然后重试。"
            ),
        }

    # 提取标签
    import re as _re
    tags = _re.findall(r'#[\w\u4e00-\u9fff·]+', content_data.get("xhs_content", ""))

    publish_content = PublishImageContent(
        title=content_data.get("xhs_title", "")[:20],
        content=content_data.get("xhs_content", ""),
        image_paths=[cover_path],
        tags=[t.lstrip("#") for t in tags],
        visibility="公开可见",
    )

    try:
        print("🌐 正在填写小红书发布表单...")
        fill_publish_form(page, publish_content)
        print("📥 正在保存到草稿箱...")
        save_as_draft(page)
        print("✅ 已保存到草稿箱！请在小红书创作中心草稿箱中查看。")
        return {"success": True, "error": None}
    except PublishError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": f"浏览器操作异常: {e}"}


def main():
    parser = argparse.ArgumentParser(
        description="发布论文笔记到小红书",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
发布模式说明：
  --mcp     通过 xiaohongshu-mcp 服务发布（推荐，稳定性最高）
            需要先启动：./xiaohongshu-mcp-linux-amd64
            项目：https://github.com/xpzouying/xiaohongshu-mcp
  --draft   通过 Chrome Bridge 保存到草稿箱（人工检查后再发）
            需要先启动：python3 bridge_server.py + XHS Bridge 扩展
  默认       通过 xhs Python 库直接调用 API，需要 --cookie
        """,
    )
    parser.add_argument("--arxiv-id", help="arXiv 论文 ID")
    parser.add_argument("--content-json", help="已生成的文案 JSON 文件")
    parser.add_argument("--cookie", help="小红书 Cookie 字符串（可选，不传则自动从缓存读取或扫码登录）")
    parser.add_argument("--refresh-cookie", action="store_true", help="强制重新扫码获取 Cookie（忽略缓存）")
    parser.add_argument("--private", action="store_true", help="发布为私密笔记")
    parser.add_argument("--mark-published", action="store_true", help="发布后加入已发布列表")
    parser.add_argument("--schedule", help="定时发布时间 (YYYY-MM-DD HH:MM:SS)")
    parser.add_argument("--force", action="store_true", help="强制发布（跳过确认）")
    parser.add_argument(
        "--draft",
        action="store_true",
        help="保存到草稿箱（浏览器模式，通过 XHS Bridge 扩展控制本地 Chrome）",
    )
    parser.add_argument(
        "--mcp",
        action="store_true",
        help="通过 xiaohongshu-mcp 服务发布（无需 cookie，需先启动 mcp 服务）",
    )
    parser.add_argument(
        "--mcp-url",
        default="http://localhost:18060/mcp",
        help="xiaohongshu-mcp 服务 URL（默认 http://localhost:18060/mcp）",
    )
    args = parser.parse_args()

    # 模式互斥校验
    if args.mcp and args.draft:
        print("❌ --mcp 和 --draft 不能同时使用")
        sys.exit(1)

    # cookie 校验（默认 API 模式需要）
    if not args.mcp and not args.draft and not args.cookie:
        # 尝试从 cookie_manager 自动获取
        try:
            sys.path.insert(0, str(Path(__file__).parent))
            from cookie_manager import get_valid_cookie
            args.cookie = get_valid_cookie(force_refresh=args.refresh_cookie)
        except SystemExit:
            raise
        except Exception as e:
            print(f"❌ 自动获取 Cookie 失败: {e}")
            print("请手动提供 --cookie 参数")
            sys.exit(1)

    # 创建客户端（仅默认 API 模式需要）
    client = create_xhs_client(args.cookie) if not args.mcp and not args.draft else None
    
    # 获取内容
    if args.content_json:
        with open(args.content_json, "r") as f:
            content_data = json.load(f)
        arxiv_id = content_data.get("arxiv_id")
    elif args.arxiv_id:
        arxiv_id = args.arxiv_id
        content_data = generate_content(arxiv_id)
        if not content_data:
            sys.exit(1)
    else:
        print("❌ 请提供 --arxiv-id 或 --content-json")
        sys.exit(1)

    # 并行启动论文精读报告（非阻塞）
    report_proc = generate_reading_report(
        arxiv_id,
        title=content_data.get("original_title", ""),
    )

    # 清理正文中的 markdown 语法（小红书 API 不支持 ** ** 等标记）
    content_data["xhs_content"] = _clean_markdown(content_data["xhs_content"])

    # 生成封面（下载 arXiv 首页 → GPT Image 图生图）
    cover_path = generate_cover(
        arxiv_id,
        title=content_data.get("original_title", ""),
        abstract=content_data.get("abstract", ""),
        categories=content_data.get("categories", []),
    )
    if not cover_path:
        print("❌ 封面生成失败")
        sys.exit(1)
    
    # 预览内容
    print("\n" + "=" * 60)
    print("📋 发布预览")
    print("=" * 60)
    print(f"\n标题: {content_data['xhs_title']}")
    print(f"\n正文:\n{content_data['xhs_content'][:500]}...")
    print(f"\n封面: {cover_path}")
    
    # ── xiaohongshu-mcp 模式（推荐）────────────────────────────────
    if args.mcp:
        import sys as _sys
        _sys.path.insert(0, str(Path(__file__).parent))
        from xhs_mcp_client import publish_via_mcp
        result = publish_via_mcp(content_data, cover_path, mcp_url=args.mcp_url)
        if result["success"]:
            print(f"✅ 发布成功（xiaohongshu-mcp）: {result.get('text', '')[:200]}")
        else:
            print(f"❌ 发布失败: {result['error']}")
        _wait_for_report(report_proc, arxiv_id)
        return 0 if result["success"] else 1

    # ── 草稿箱模式（浏览器 Bridge）──────────────────────────────────
    if args.draft:
        result = save_to_draft_via_browser(content_data, cover_path)
        _wait_for_report(report_proc, arxiv_id)
        return 0 if result["success"] else 1

    # ── API 发布模式 ────────────────────────────────────────────────
    # 确认
    if not args.force:
        print("\n" + "=" * 60)
        print("⚠️  请确认内容是否正确")
        print("=" * 60)
        confirm = input("确认发布? (y/n): ").strip().lower()
        if confirm not in ["y", "yes", "是"]:
            print("❌ 已取消发布")
            sys.exit(0)

    result = publish_note(
        client=client,
        content_data=content_data,
        cover_path=cover_path,
        is_private=args.private,
        schedule_time=args.schedule
    )

    # 更新已发布列表
    if result["success"] and args.mark_published:
        published = load_published_list()
        published["published"].append({
            "arxiv_id": arxiv_id,
            "title": content_data["original_title"],
            "published_at": datetime.now().isoformat(),
            "xhs_note_id": result.get("note_id", ""),
            "xhs_link": result.get("share_link", ""),
            "tags": ["机器学习", "强化学习"]
        })
        save_published_list(published)
        print(f"✅ 已添加到发布列表")

    # 保存发布结果
    if result["success"]:
        result_path = CONTENT_DIR / f"result_{arxiv_id.replace('.', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(result_path, "w") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"💾 发布结果已保存: {result_path}")

    _wait_for_report(report_proc, arxiv_id)
    return 0 if result["success"] else 1


def _wait_for_report(report_proc, arxiv_id: str) -> None:
    """等待后台精读报告生成完成。"""
    if report_proc is None:
        return
    print("\n⏳ 等待论文精读报告生成完成...")
    try:
        stdout, stderr = report_proc.communicate(timeout=300)
        if report_proc.returncode == 0:
            report_dir = BASE_DIR / "reports"
            report_path = report_dir / f"report_{arxiv_id.replace('.', '_')}.md"
            if report_path.exists():
                print(f"📖 精读报告已生成: {report_path}")
            else:
                print("⚠️  精读报告未生成")
        else:
            print(f"⚠️  精读报告生成失败")
            if stderr:
                print(stderr.strip(), file=sys.stderr)
    except subprocess.TimeoutExpired:
        report_proc.kill()
        print("⚠️  精读报告生成超时，已跳过")


if __name__ == "__main__":
    sys.exit(main())
