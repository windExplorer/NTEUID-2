"""生成 drive 八档等级图标（D/C/B/A/S/SS/SSS/ACE）。

设计原则（与“原仓库 texture2d 缎带徽章”彻底区分）：
  - 透明背景，无底框/无徽章，纯文字；
  - 文字颜色按档位递增（参考二游稀有度色阶：灰→绿→蓝→紫→金→橙→红→青）；
  - 仅叠加一层柔和投影增强立体感与可读性。

输出到本目录的 ranks/ 子目录，与原始仓库资源完全分离。
运行：从仓库根目录执行
    python NTEUID/extra/drive/make_rank_icons.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter

# 全部档位统一使用 LuckiestGuy（圆润卡通粗体，契合二游评级观感）。
# 单字档输出 320×320 方形；多字档（SS/SSS/ACE）输出“宽画布”矩形：
# 字母按与单字相同的视觉高度、正常字距（不重叠），画布随字数加宽。
# 卡牌侧按比例缩放（contain），故宽图标在卡上也能和单字一样高、且不压扁。
FONTS_DIR = Path(__file__).resolve().parent / "fonts"
FONT = FONTS_DIR / "LuckiestGuy-Regular.ttf"
OUT_DIR = Path(__file__).resolve().parent / "ranks"
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT = 320   # 单字档方形输出画布；多字档矩形画布的高度也取此值，保证卡上缩放比例一致
WORK = 420  # 单字档绘制画布（比 OUT 大，给投影与光学居中下移留出余量，避免裁切）
TEXT_H = 0.84  # 文字高度占 OUT 的比例（略留余量以便下移做光学居中）
MARGIN_X = 60   # 多字档宽画布左右留白（容纳投影）

# 等级 -> (显示文字, 主色)。颜色参考二游常见稀有度色阶，按阶位递增。
RANKS: dict[str, tuple[str, tuple[int, int, int]]] = {
    "D": ("D", (154, 163, 173)),     # 灰
    "C": ("C", (87, 217, 138)),      # 绿
    "B": ("B", (77, 159, 255)),      # 蓝
    "A": ("A", (176, 124, 255)),     # 紫
    "S": ("S", (255, 210, 77)),      # 金
    "SS": ("SS", (255, 138, 61)),    # 橙
    "SSS": ("SSS", (255, 90, 122)),  # 红/品红
    "ACE": ("ACE", (63, 224, 224)),  # 青：王牌最高阶
}

SHADOW_OFFSET = (2, 3)      # 投影偏移
SHADOW_BLUR = 3             # 投影模糊半径
SHADOW_ALPHA = 150          # 投影不透明度


def _tracked_width(text: str, font: ImageFont.ImageFont, tracking_px: int) -> int:
    """按字逐字绘制时的总宽度（含字距）。"""
    total = 0
    for ch in text:
        b = font.getbbox(ch)
        total += b[2] - b[0]
    total += tracking_px * max(0, len(text) - 1)
    return total


def _draw_tracked(
    draw: ImageDraw.ImageDraw,
    x0: float,
    y0: float,
    text: str,
    font: ImageFont.ImageFont,
    fill: tuple[int, int, int, int],
    tracking_px: int,
) -> None:
    """逐字绘制（字距=0 时为正常排布，字母不重叠）。"""
    x = x0
    for ch in text:
        draw.text((x, y0), ch, font=font, fill=fill)
        b = font.getbbox(ch)
        x += (b[2] - b[0]) + tracking_px


def _make(grade: str, text: str, color: tuple[int, int, int], wide: bool) -> None:
    # 字号取“字母墨迹高度≈ TEXT_H*OUT”，与单字档一致，保证卡上缩放后高度相同
    target_h = int(OUT * TEXT_H)
    font = ImageFont.truetype(str(FONT), target_h)
    b = font.getbbox(text)
    th = b[3] - b[1]
    size = int(round(target_h * target_h / th))
    font = ImageFont.truetype(str(FONT), size)
    bbox = font.getbbox(text)
    th = bbox[3] - bbox[1]

    # 光学居中修正：大写字母无下伸部(descender)，字体为下伸部预留的
    # 空白全堆在字母下方，导致视觉上偏上。按 descent 下移半个下伸高度补偿。
    _, descent = font.getmetrics()
    shift = min(descent * 0.5, OUT * 0.045)

    if wide:
        # 宽画布：画布高度=OUT（与单字同高，卡上缩放一致），宽度随文字加宽
        total_w = _tracked_width(text, font, 0)
        CW = total_w + 2 * MARGIN_X
        CH = OUT
        canvas = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
        tx = MARGIN_X
        ty = (CH - th) / 2 - bbox[1] + shift
    else:
        # 单字档：方形绘制画布，居中后裁到 OUT
        canvas = Image.new("RGBA", (WORK, WORK), (0, 0, 0, 0))
        total_w = _tracked_width(text, font, 0)
        tx = (WORK - total_w) / 2
        ty = (WORK - th) / 2 - bbox[1] + shift

    # 投影层：黑色文字模糊后偏移
    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    _draw_tracked(
        ImageDraw.Draw(shadow),
        tx + SHADOW_OFFSET[0], ty + SHADOW_OFFSET[1], text, font,
        (0, 0, 0, SHADOW_ALPHA), 0,
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(SHADOW_BLUR))

    # 主文字层：纯档位色
    main = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    _draw_tracked(ImageDraw.Draw(main), tx, ty, text, font, color, 0)

    out_img = Image.alpha_composite(shadow, main)
    if not wide:
        m = (WORK - OUT) // 2
        out_img = out_img.crop((m, m, m + OUT, m + OUT))
    out = OUT_DIR / f"rank_{grade}.png"
    out_img.save(out)
    print("saved", out, out_img.size)


def main() -> None:
    for grade, (text, color) in RANKS.items():
        _make(grade, text, color, wide=len(text) > 1)


if __name__ == "__main__":
    main()
