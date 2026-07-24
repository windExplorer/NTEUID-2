"""生成 drive 高阶等级图标（SS/SSS/ACE）。

原仓库 texture2d 只有 rank_S/A/B，drive 评分的更高阶等级（SS/SSS/ACE）没有对应图标，
导致 drive 卡片上不显示这些等级。本脚本以横向授带徽章风格补画这三种图标，
输出到本目录的 ranks/ 子目录，与原始仓库资源完全分离。

运行：从仓库根目录执行
    python NTEUID/extra/drive/make_rank_icons.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# 字体复用项目内置字体，保证与卡片其余文字一致
FONT = Path(__file__).resolve().parents[2] / "utils" / "fonts" / "nte_fonts.ttf"
OUT_DIR = Path(__file__).resolve().parent / "ranks"
OUT_DIR.mkdir(parents=True, exist_ok=True)

SIZE = 100  # 正方形画布，便于 _grade_img 等比缩小不变形
BODY_W, BODY_H = 92, 52
TAIL_H = 20

# 等级 -> (显示文字, 主色)
RANKS: dict[str, tuple[str, tuple[int, int, int]]] = {
    "SS": ("SS", (222, 48, 48)),    # 红：高于 S(橙金)
    "SSS": ("SSS", (233, 64, 152)),  # 品红：高于 SS
    "ACE": ("ACE", (0, 188, 212)),   # 青：王牌最高阶
}


def _darker(color: tuple[int, int, int], k: float = 0.62) -> tuple[int, int, int]:
    return tuple(int(c * k) for c in color)


def _make(grade: str, text: str, color: tuple[int, int, int]) -> None:
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    bx0 = (SIZE - BODY_W) // 2
    bx1 = bx0 + BODY_W
    by0 = (SIZE - (BODY_H + TAIL_H)) // 2
    by1 = by0 + BODY_H
    cx = SIZE // 2
    o = 3  # 描边厚度

    # 暗色描边底层（向外扩 o）
    d.rounded_rectangle([bx0 - o, by0 - o, bx1 + o, by1 + o], radius=16, fill=_darker(color))
    d.polygon([(bx0 + 4 - o, by1 - o), (cx - 8, by1 - o), (cx - 2, by1 + TAIL_H + o)], fill=_darker(color))
    d.polygon([(cx + 2, by1 + TAIL_H + o), (cx + 8, by1 - o), (bx1 - 4 + o, by1 - o)], fill=_darker(color))

    # 主色面层
    d.rounded_rectangle([bx0, by0, bx1, by1], radius=14, fill=color)
    # 燕尾双飘带（中间 V 形缺口）
    d.polygon([(bx0 + 4, by1), (cx - 8, by1), (cx - 2, by1 + TAIL_H)], fill=color)
    d.polygon([(cx + 2, by1 + TAIL_H), (cx + 8, by1), (bx1 - 4, by1)], fill=color)

    # 文字（白色 + 暗色描边，保证在任意底色上可读）
    font_size = 38 if len(text) <= 2 else 30
    font = ImageFont.truetype(str(FONT), size=font_size)
    while d.textlength(text, font=font) > BODY_W - 14 and font_size > 14:
        font_size -= 1
        font = ImageFont.truetype(str(FONT), size=font_size)
    tx, ty = cx, by0 + BODY_H // 2
    d.text((tx, ty), text, font=font, fill=(20, 20, 20), anchor="mm", stroke_width=4, stroke_fill=(20, 20, 20))
    d.text((tx, ty), text, font=font, fill=(255, 255, 255), anchor="mm")

    out = OUT_DIR / f"rank_{grade}.png"
    img.save(out)
    print("saved", out, img.size)


def main() -> None:
    for grade, (text, color) in RANKS.items():
        _make(grade, text, color)


if __name__ == "__main__":
    main()
