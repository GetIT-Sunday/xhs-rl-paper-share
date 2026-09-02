#!/usr/bin/env python3
"""
下载 arXiv 论文首页 PNG 作为小红书封面（默认直出）。

流程：
  1. 下载 arXiv PDF → 提取首页为 PNG
  2. 直接输出首页截图（真实感强，有利于推流）
  3. 可选：加 --gpt-cover 参数改用生图模型二次创作

--gpt-cover 的生图后端按以下顺序解析，任一可用即生效，全部不可用则降级为首页直出：
  1. 外部生图脚本：环境变量 XHS_IMAGE_SCRIPT 指向一个接受
     --prompt / --image / --output / --size 参数的脚本
  2. 生图 API：环境变量 XHS_IMAGE_API_KEY（或 OPENAI_API_KEY），可选配
     XHS_IMAGE_BASE_URL（默认 https://api.openai.com/v1）、
     XHS_IMAGE_MODEL（默认 gpt-image-1），走 OpenAI 兼容的 images/edits 接口

用法：
  python3 capture_cover.py --arxiv-id 2301.12345
  python3 capture_cover.py --arxiv-id 2301.12345 --gpt-cover
  python3 capture_cover.py --arxiv-id 2301.12345 --output /path/to/cover.png
"""

import argparse
import base64
import json
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path


# 生图后端配置：全部通过环境变量注入，不假设任何目录布局
IMAGE_SCRIPT = os.environ.get("XHS_IMAGE_SCRIPT", "").strip()
IMAGE_API_KEY = (
    os.environ.get("XHS_IMAGE_API_KEY", "").strip()
    or os.environ.get("OPENAI_API_KEY", "").strip()
)
IMAGE_BASE_URL = os.environ.get(
    "XHS_IMAGE_BASE_URL", "https://api.openai.com/v1"
).strip().rstrip("/")
IMAGE_MODEL = os.environ.get("XHS_IMAGE_MODEL", "gpt-image-1").strip()
IMAGE_SIZE = os.environ.get("XHS_IMAGE_SIZE", "1024x1536").strip()


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
# Step 2: build the image-generation prompt
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
# Step 3: call the image-generation backend (edit / image-to-image mode)
# ---------------------------------------------------------------------------

def _encode_multipart(fields: dict, file_field: str, file_path: str) -> tuple:
    """手搓 multipart/form-data，避免为一个上传引入额外依赖"""
    import uuid

    boundary = "----xhsCover" + uuid.uuid4().hex
    crlf = b"\r\n"
    body = bytearray()
    for key, value in fields.items():
        if value is None:
            continue
        body += b"--" + boundary.encode() + crlf
        body += f'Content-Disposition: form-data; name="{key}"'.encode() + crlf + crlf
        body += str(value).encode() + crlf
    filename = Path(file_path).name
    body += b"--" + boundary.encode() + crlf
    body += (
        f'Content-Disposition: form-data; name="{file_field}"; filename="{filename}"'
    ).encode() + crlf
    body += b"Content-Type: image/png" + crlf + crlf
    body += open(file_path, "rb").read() + crlf
    body += b"--" + boundary.encode() + b"--" + crlf
    return bytes(body), f"multipart/form-data; boundary={boundary}"


def _generate_via_script(ref_image_path: str, output_path: str, prompt: str) -> bool:
    """调用用户自备的外部生图脚本（XHS_IMAGE_SCRIPT）"""
    script = Path(IMAGE_SCRIPT)
    if not script.exists():
        print(f"❌ XHS_IMAGE_SCRIPT 指向的脚本不存在: {script}", file=sys.stderr)
        return False

    print(f"🎨 调用外部生图脚本生成封面: {script.name}")
    result = subprocess.run(
        [sys.executable, str(script),
         "--prompt", prompt,
         "--image", ref_image_path,
         "--output", output_path,
         "--size", IMAGE_SIZE],
        timeout=180,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0 and Path(output_path).exists():
        print(f"✅ 封面生成成功: {output_path}")
        return True
    print("❌ 外部生图脚本执行失败", file=sys.stderr)
    if result.stderr:
        print(result.stderr.strip()[:500], file=sys.stderr)
    return False


def _generate_via_api(ref_image_path: str, output_path: str, prompt: str) -> bool:
    """以论文首页图为参考，调 OpenAI 兼容的 images/edits 接口生成封面"""
    url = f"{IMAGE_BASE_URL}/images/edits"
    print(f"🎨 调用生图接口生成封面: {IMAGE_MODEL} @ {IMAGE_BASE_URL}")

    body, content_type = _encode_multipart(
        {"model": IMAGE_MODEL, "prompt": prompt, "size": IMAGE_SIZE, "n": 1},
        "image",
        ref_image_path,
    )
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Authorization", f"Bearer {IMAGE_API_KEY}")
    req.add_header("Content-Type", content_type)

    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            payload = json.load(resp)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        # 只回显接口报错，绝不回显 API Key
        print(f"❌ 生图接口返回 HTTP {e.code}: {detail}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"❌ 生图接口调用失败: {e}", file=sys.stderr)
        return False

    items = payload.get("data") or []
    if not items:
        print("❌ 生图接口未返回图片数据", file=sys.stderr)
        return False

    item = items[0]
    if item.get("b64_json"):
        with open(output_path, "wb") as f:
            f.write(base64.b64decode(item["b64_json"]))
    elif item.get("url"):
        req_img = urllib.request.Request(item["url"], headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req_img, timeout=120) as resp:
            data = resp.read()
        with open(output_path, "wb") as f:
            f.write(data)
    else:
        print("❌ 生图接口返回的数据里既没有 b64_json 也没有 url", file=sys.stderr)
        return False

    print(f"✅ 封面生成成功: {output_path}")
    return True


def generate_cover_with_model(ref_image_path: str, output_path: str,
                              title: str, abstract: str) -> bool:
    """以论文首页图为参考做图生图封面。

    按「外部脚本 → 生图 API」的顺序尝试，都不可用时返回 False，
    由调用方降级为 arXiv 首页直出。
    """
    prompt = build_edit_prompt(title, abstract)
    print(f"   参考图: {ref_image_path}")

    if IMAGE_SCRIPT:
        return _generate_via_script(ref_image_path, output_path, prompt)
    if IMAGE_API_KEY:
        return _generate_via_api(ref_image_path, output_path, prompt)

    print(
        "⚠️  未配置生图后端（XHS_IMAGE_SCRIPT 或 XHS_IMAGE_API_KEY），"
        "降级为 arXiv 首页直出",
        file=sys.stderr,
    )
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
                        help="用生图模型二次创作封面（默认关闭，直出 arXiv 首页截图）；\n需配置 XHS_IMAGE_SCRIPT 或 XHS_IMAGE_API_KEY")
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

        # Step 3: 直出 or 生图模型二次创作
        if args.gpt_cover:
            ok = generate_cover_with_model(ref_png_path, final_path, args.title, args.abstract)
            if not ok:
                # 生图失败时降级为直出
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
