#!/usr/bin/env python3
"""
下载 arXiv 论文首页 PNG 作为小红书封面（默认直出）。

流程：
  1. 下载 arXiv PDF → 提取首页为 PNG
  2. 直接输出首页截图（真实感强，有利于推流）
  3. 可选：加 --gpt-cover 参数改用 GPT Image 二次创作

用法：
  python3 capture_cover.py --arxiv-id 2301.12345
  python3 capture_cover.py --arxiv-id 2301.12345 --gpt-cover
  python3 capture_cover.py --arxiv-id 2301.12345 --output /path/to/cover.png
"""

import argparse
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path


GPT_IMAGE_SCRIPT = Path(__file__).parent.parent.parent / "gpt-image" / "scripts" / "gpt_image.py"


# ---------------------------------------------------------------------------
# Step 1: download arXiv PDF and extract first page as PNG
# ---------------------------------------------------------------------------

def download_arxiv_pdf(arxiv_id: str, dest_path: str) -> bool:
    """从 arXiv 下载论文 PDF"""
    pdf_url = f"https://arxiv.org/pdf/{arxiv_id}"
    print(f"📥 下载 arXiv PDF: {pdf_url}")
    try:
        req = urllib.request.Request(pdf_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = resp.read()
        with open(dest_path, "wb") as f:
            f.write(data)
        print(f"✅ PDF 下载完成")
        return True
    except Exception as e:
        print(f"❌ PDF 下载失败: {e}", file=sys.stderr)
        return False


def pdf_first_page_to_image(pdf_path: str, output_path: str) -> bool:
    """将 PDF 首页转为 PNG（依次尝试 PyMuPDF / pdftoppm / ghostscript）"""

    # 方案1: PyMuPDF（沙箱默认有）
    try:
        import fitz  # type: ignore
        doc = fitz.open(pdf_path)
        page = doc[0]
        mat = fitz.Matrix(2.0, 2.0)
        pix = page.get_pixmap(matrix=mat)
        pix.save(output_path)
        doc.close()
        print(f"✅ 首页提取完成 (PyMuPDF)")
        return True
    except ImportError:
        pass
    except Exception as e:
        print(f"⚠️  PyMuPDF 失败: {e}", file=sys.stderr)

    # 方案2: pdftoppm
    try:
        stem = str(Path(output_path).with_suffix(""))
        result = subprocess.run(
            ["pdftoppm", "-r", "150", "-l", "1", "-png", pdf_path, stem],
            capture_output=True, text=True, timeout=60,
        )
        candidate = stem + "-1.png"
        if result.returncode == 0 and Path(candidate).exists():
            Path(candidate).rename(output_path)
            print(f"✅ 首页提取完成 (pdftoppm)")
            return True
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"⚠️  pdftoppm 失败: {e}", file=sys.stderr)

    # 方案3: ghostscript
    try:
        result = subprocess.run(
            ["gs", "-dNOPAUSE", "-dBATCH", "-sDEVICE=png16m",
             "-r150", "-dFirstPage=1", "-dLastPage=1",
             f"-sOutputFile={output_path}", pdf_path],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode == 0 and Path(output_path).exists():
            print(f"✅ 首页提取完成 (ghostscript)")
            return True
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"⚠️  ghostscript 失败: {e}", file=sys.stderr)

    print("❌ PDF 转图失败，请安装 PyMuPDF / poppler-utils / ghostscript", file=sys.stderr)
    return False


# ---------------------------------------------------------------------------
# Step 2: build GPT Image prompt
# ---------------------------------------------------------------------------

def build_edit_prompt(title: str, abstract: str) -> str:
    """构建图生图 prompt：以论文首页为参考，生成小红书封面"""
    topic = title[:100] if title else "reinforcement learning research"
    abstract_hint = abstract[:200].strip() if abstract else ""
    content_hint = f"{topic}. {abstract_hint}" if abstract_hint else topic

    return f"""You are given the first page of an academic paper as a reference image.
Create a vertical mobile poster (portrait 1024x1536) for Xiaohongshu (Chinese social media) based on this paper.

Design requirements:
- Extract the paper title and key concepts from the reference image
- Create a warm, kawaii educational poster aesthetic popular on Xiaohongshu
- Feature a cute chubby 3D glossy bee mascot (round yellow-black striped body, tiny wings, honey pot on head, sleepy gentle eyes) as the presenter
- The bee stands beside a small whiteboard showing 3-4 simple cute doodle icons that represent the paper's core idea: {content_hint}
- TOP SECTION (~20%): warm honey-yellow gradient banner with paper domain label area — write the main research domain in bold Chinese (e.g. "强化学习 · AI对齐")
- MIDDLE SECTION (~55%): bee mascot + whiteboard with cute doodle icons. Reference the actual figures/diagrams from the paper if visible in the reference image.
- BOTTOM SECTION (~25%): soft cream card area with arXiv paper title displayed in clean sans-serif font, plus small decorative honeycomb border pattern
- Color palette: honey yellow #F5C842, cream white, soft coral pink accent
- Do NOT copy text verbatim from the reference — redesign it into the poster layout above
- Portrait format, no harsh borders, soft gradients throughout
"""


# ---------------------------------------------------------------------------
# Step 3: call gpt-image in edit mode
# ---------------------------------------------------------------------------

def generate_cover_with_gpt(ref_image_path: str, output_path: str,
                             title: str, abstract: str) -> bool:
    """以论文首页图为参考，调用 gpt-image 图生图生成封面"""
    if not GPT_IMAGE_SCRIPT.exists():
        print(f"❌ 未找到 gpt-image 脚本: {GPT_IMAGE_SCRIPT}", file=sys.stderr)
        return False

    prompt = build_edit_prompt(title, abstract)
    print(f"🎨 正在用 GPT Image 图生图生成封面...")
    print(f"   参考图: {ref_image_path}")

    result = subprocess.run(
        [sys.executable, str(GPT_IMAGE_SCRIPT),
         "--prompt", prompt,
         "--image", ref_image_path,
         "--output", output_path,
         "--size", "1024x1536"],
        timeout=180,
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        print(f"✅ 封面生成成功: {output_path}")
        return True
    else:
        print(f"❌ GPT Image 图生图失败", file=sys.stderr)
        if result.stderr:
            print(result.stderr.strip(), file=sys.stderr)
        return False


# ---------------------------------------------------------------------------
# Fallback: use the raw first-page PNG directly
# ---------------------------------------------------------------------------

def use_raw_cover(ref_image_path: str, output_path: str) -> bool:
    """直接使用 arXiv 首页截图作为封面（默认模式）"""
    import shutil
    shutil.copy(ref_image_path, output_path)
    print(f"✅ 使用 arXiv 原始首页作为封面: {output_path}")
    return True


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="下载 arXiv 论文首页作为小红书封面（默认直出首页截图）")
    parser.add_argument("--arxiv-id", required=True, help="arXiv 论文 ID")
    parser.add_argument("--title", default="", help="论文标题（英文，供 --gpt-cover 使用）")
    parser.add_argument("--abstract", default="", help="论文摘要（英文，供 --gpt-cover 使用）")
    parser.add_argument("--categories", default="cs.LG", help="arXiv categories 逗号分隔（保留兼容）")
    parser.add_argument("--output", default=None, help="输出封面图片路径（.png）")
    parser.add_argument("--gpt-cover", action="store_true",
                        help="用 GPT Image 二次创作封面（默认关闭，直出 arXiv 首页截图）")
    args = parser.parse_args()

    output_dir = Path(__file__).parent.parent / "assets" / "covers"
    output_dir.mkdir(parents=True, exist_ok=True)

    safe_id = args.arxiv_id.replace(".", "_")
    final_path = args.output or str(output_dir / f"{safe_id}.png")

    # 临时文件：PDF 和首页 PNG
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False, dir=str(output_dir)) as tmp_pdf:
        pdf_path = tmp_pdf.name
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False, dir=str(output_dir)) as tmp_png:
        ref_png_path = tmp_png.name

    try:
        # Step 1: 下载 PDF
        ok = download_arxiv_pdf(args.arxiv_id, pdf_path)
        if not ok:
            return False

        # Step 2: 提取首页为 PNG
        ok = pdf_first_page_to_image(pdf_path, ref_png_path)
        if not ok:
            return False

        # Step 3: 直出 or GPT Image
        if args.gpt_cover:
            ok = generate_cover_with_gpt(ref_png_path, final_path, args.title, args.abstract)
            if not ok:
                # GPT Image 失败时降级为直出
                ok = use_raw_cover(ref_png_path, final_path)
        else:
            # 默认：直接使用 arXiv 首页截图
            ok = use_raw_cover(ref_png_path, final_path)

    finally:
        import os
        for p in [pdf_path, ref_png_path]:
            if os.path.exists(p) and p != final_path:
                os.unlink(p)

    if ok:
        print(f"\n📄 arXiv 链接: https://arxiv.org/abs/{args.arxiv_id}")
        print(f"🖼️  封面图片: {final_path}")

    return ok


if __name__ == "__main__":
    result = main()
    sys.exit(0 if result else 1)
