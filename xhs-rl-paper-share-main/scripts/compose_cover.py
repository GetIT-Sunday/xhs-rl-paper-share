#!/usr/bin/env python3
"""
在 GPT Image 生成的封面底图上叠加中文文字：
  - 上方模块：论文领域标签（AI 自动识别）
  - 下方模块：arXiv categories + 核心关键词

用法：
  python3 compose_cover.py \
    --image cover_bg.png \
    --domain "强化学习 · 概率推理" \
    --keywords "最大熵RL · 变分推理 · 统一框架" \
    --output cover_final.png
"""

import argparse
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("❌ 缺少依赖：pip install Pillow", file=sys.stderr)
    sys.exit(1)


# 字体查找顺序（系统内置路径优先，fallback 用 PIL 默认）
FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/truetype/arphic/uming.ttc",
]


def get_font(size: int):
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    # Pillow 内置字体（不支持中文，但至少不崩溃）
    return ImageFont.load_default()


def infer_domain(title: str, abstract: str, categories: list[str]) -> str:
    """根据论文内容推断领域标签（规则匹配 + categories 映射）"""
    text = (title + " " + abstract).lower()

    # categories 映射
    cat_map = {
        "cs.ro": "机器人学习",
        "cs.ai": "人工智能",
        "cs.lg": "机器学习",
        "cs.ne": "神经网络",
        "cs.ma": "多智能体",
        "stat.ml": "统计学习",
        "q-bio": "计算生物学",
    }
    domain_parts = []
    for cat in categories:
        cat_lower = cat.lower()
        for key, val in cat_map.items():
            if key in cat_lower and val not in domain_parts:
                domain_parts.append(val)

    # 关键词补充识别
    if any(k in text for k in ["embodied", "robot", "manipulation", "locomotion"]):
        if "机器人学习" not in domain_parts:
            domain_parts.insert(0, "具身智能")
    if any(k in text for k in ["multi-agent", "multiagent", "cooperative", "competitive"]):
        if "多智能体" not in domain_parts:
            domain_parts.append("多智能体RL")
    if any(k in text for k in ["offline", "batch rl", "offline reinforcement"]):
        domain_parts.append("离线RL")
    if any(k in text for k in ["world model", "model-based", "dreamer", "muzero"]):
        domain_parts.append("世界模型")
    if any(k in text for k in ["probabilistic", "bayesian", "inference", "variational"]):
        domain_parts.append("概率推理")
    if any(k in text for k in ["survey", "review", "overview", "tutorial"]):
        domain_parts.append("综述")

    # 始终保证有"强化学习"
    if "强化学习" not in domain_parts and "机器学习" not in domain_parts:
        domain_parts.insert(0, "强化学习")
    elif "强化学习" not in domain_parts:
        domain_parts.insert(0, "强化学习")

    return " · ".join(domain_parts[:4])  # 最多4个领域标签


def build_keywords(categories: list[str], abstract: str) -> str:
    """用 arXiv categories + 摘要关键词构建下方关键词行"""
    # arXiv categories 转短标签
    cat_short = {
        "cs.ro": "Robotics",
        "cs.ai": "AI",
        "cs.lg": "ML",
        "cs.ne": "Neural Nets",
        "cs.ma": "Multi-Agent",
        "stat.ml": "Stat.ML",
        "cs.cv": "Vision",
        "cs.cl": "NLP",
    }
    tags = []
    for cat in categories[:3]:
        c = cat.lower()
        for key, val in cat_short.items():
            if key in c:
                tags.append(val)
                break
        else:
            tags.append(cat)

    # 从摘要提炼 RL 方法关键词
    method_kw_map = {
        "ppo": "PPO", "sac": "SAC", "dqn": "DQN", "td3": "TD3",
        "dreamer": "Dreamer", "muzero": "MuZero", "reinforce": "REINFORCE",
        "q-learning": "Q-Learning", "actor-critic": "Actor-Critic",
        "maximum entropy": "MaxEnt-RL", "variational": "变分推理",
        "offline rl": "Offline RL", "world model": "World Model",
        "multi-agent": "MARL", "hierarchical": "层次RL",
    }
    abs_lower = abstract.lower()
    for kw, label in method_kw_map.items():
        if kw in abs_lower and label not in tags:
            tags.append(label)
        if len(tags) >= 5:
            break

    return "  ·  ".join(tags[:5])


def draw_text_with_shadow(draw, pos, text, font, fill, shadow_color=(0, 0, 0, 80), shadow_offset=2):
    """带阴影绘制文字"""
    x, y = pos
    draw.text((x + shadow_offset, y + shadow_offset), text, font=font, fill=shadow_color)
    draw.text((x, y), text, font=font, fill=fill)


def compose(image_path: str, domain: str, keywords: str, output_path: str) -> bool:
    """在封面底图上叠加上下模块文字"""
    img = Image.open(image_path).convert("RGBA")
    w, h = img.size

    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # ── 上方模块：领域标签 ──────────────────────────────
    top_h = int(h * 0.22)        # 上方区域高度约22%
    font_domain_size = max(36, w // 18)
    font_domain = get_font(font_domain_size)

    # 计算文字宽度居中
    try:
        bbox = draw.textbbox((0, 0), domain, font=font_domain)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
    except AttributeError:
        tw, th = draw.textsize(domain, font=font_domain)

    tx = (w - tw) // 2
    ty = top_h // 2 - th // 2 + int(h * 0.02)

    # 黄色粗体领域文字
    draw_text_with_shadow(draw, (tx, ty), domain, font_domain,
                          fill=(30, 20, 10, 240),
                          shadow_color=(255, 220, 50, 120), shadow_offset=3)

    # ── 下方模块：关键词 ──────────────────────────────
    bottom_start = int(h * 0.76)
    font_kw_size = max(28, w // 24)
    font_kw = get_font(font_kw_size)

    try:
        bbox2 = draw.textbbox((0, 0), keywords, font=font_kw)
        kw_w = bbox2[2] - bbox2[0]
        kw_h = bbox2[3] - bbox2[1]
    except AttributeError:
        kw_w, kw_h = draw.textsize(keywords, font=font_kw)

    kx = (w - kw_w) // 2
    ky = bottom_start + (h - bottom_start) // 2 - kw_h // 2

    draw_text_with_shadow(draw, (kx, ky), keywords, font_kw,
                          fill=(50, 30, 10, 230),
                          shadow_color=(255, 200, 0, 100), shadow_offset=2)

    # 合并图层
    result = Image.alpha_composite(img, overlay).convert("RGB")
    result.save(output_path, "PNG", quality=95)
    print(f"✅ 封面合成完成: {output_path}")
    return True


def main():
    parser = argparse.ArgumentParser(description="在封面底图上叠加文字")
    parser.add_argument("--image", required=True, help="GPT Image 生成的底图路径")
    parser.add_argument("--domain", default="", help="领域标签文字（留空则自动推断）")
    parser.add_argument("--keywords", default="", help="关键词文字（留空则自动推断）")
    parser.add_argument("--title", default="", help="论文标题（用于自动推断）")
    parser.add_argument("--abstract", default="", help="论文摘要（用于自动推断）")
    parser.add_argument("--categories", default="", help="arXiv categories 逗号分隔")
    parser.add_argument("--output", required=True, help="输出图片路径")
    args = parser.parse_args()

    categories = [c.strip() for c in args.categories.split(",") if c.strip()]

    domain = args.domain or infer_domain(args.title, args.abstract, categories)
    keywords = args.keywords or build_keywords(categories, args.abstract)

    print(f"📌 领域标签: {domain}")
    print(f"🔑 关键词: {keywords}")

    success = compose(args.image, domain, keywords, args.output)
    return success


if __name__ == "__main__":
    result = main()
    sys.exit(0 if result else 1)
