from __future__ import annotations

import random
from pathlib import Path

from PIL import Image, ImageDraw

from gsuid_core.utils.image.convert import convert_img

from ..utils.image import (
    COLOR_WHITE,
    add_footer,
    make_nte_role_title,
)
from ..utils.database import SIGN_KIND_APP, SIGN_KIND_GAME, NTEUser, NTESignRecord
from ..utils.fonts.nte_fonts import nte_font_origin
from ..utils.sdk.tajiduo_model import RoleHome

TEXTURE_PATH = Path(__file__).parent / "texture2d" / "realtime"
FASHION_DIR = TEXTURE_PATH / "fashion"

COLOR_VAL_RED = (235, 80, 100)
COLOR_LABEL = (210, 210, 220)
COLOR_SUB_GRAY = (170, 170, 180)


def _load_icon(name: str, size: int) -> Image.Image:
    return Image.open(TEXTURE_PATH / name).convert("RGBA").resize((size, size), Image.Resampling.LANCZOS)


def _fit_centered(img: Image.Image, output_size: tuple[int, int]) -> Image.Image:
    """长边缩到 frame 对应边、短边居中、出血居中裁，输出永远是 output_size 的透明 RGBA。"""
    iw, ih = img.size
    tw, th = output_size
    if iw > ih:
        scale = tw / iw
        new_size = (tw, round(ih * scale))
    else:
        scale = th / ih
        new_size = (round(iw * scale), th)
    resized = img.resize(new_size, Image.Resampling.LANCZOS)
    out = Image.new("RGBA", output_size, (0, 0, 0, 0))
    out.paste(resized, ((tw - new_size[0]) // 2, (th - new_size[1]) // 2), resized)
    return out


def _draw_stat_cell(
    canvas: Image.Image,
    draw: ImageDraw.ImageDraw,
    icon: Image.Image,
    label: str,
    value: str,
    maximum: str,
    xy: tuple[int, int],
) -> None:
    cx, cy = xy
    canvas.alpha_composite(icon, (cx + 16, cy + 3))

    text_x = cx + 166
    mid_y = cy + 67
    font_value = nte_font_origin(58)
    font_max = nte_font_origin(40)
    font_label = nte_font_origin(24)

    draw.text((text_x, mid_y - 4), value, font=font_value, fill=COLOR_VAL_RED, anchor="lb")
    val_w = draw.textlength(value, font=font_value)
    draw.text(
        (text_x + val_w + 4, mid_y - 4),
        f"/{maximum}",
        font=font_max,
        fill=COLOR_WHITE,
        anchor="lb",
    )
    draw.text((text_x, mid_y + 14), label, font=font_label, fill=COLOR_LABEL, anchor="lt")


async def draw_realtime_img(avatar: Image.Image, user: NTEUser, home: RoleHome):
    canvas = Image.new("RGBA", (1786, 1000), (0, 0, 0, 0))
    canvas.alpha_composite(Image.open(TEXTURE_PATH / "bg.jpg").convert("RGBA"), (0, 0))

    fashion_pool = [p for p in FASHION_DIR.iterdir() if p.is_file() and not p.name.startswith(".")]
    fashion_raw = Image.open(random.choice(fashion_pool)).convert("RGBA")
    canvas.alpha_composite(_fit_centered(fashion_raw, (800, 1000)), (-40, 0))
    canvas.alpha_composite(Image.open(TEXTURE_PATH / "fg.png").convert("RGBA"), (0, 0))

    canvas.alpha_composite(make_nte_role_title(avatar, user.role_name, user.uid, home.lev), (676, 180))

    badges = []
    if await NTESignRecord.is_signed(f"{user.game_id}:{user.uid}", SIGN_KIND_GAME):
        badges.append("今日异环已签到")
    if await NTESignRecord.is_signed(user.center_uid, SIGN_KIND_APP):
        badges.append("今日塔吉多已签到")
    for i, text in enumerate(badges):
        badge = Image.open(TEXTURE_PATH / "title2.png").convert("RGBA").crop((0, 0, 320, 45))
        ImageDraw.Draw(badge).text((60, 22), text, font=nte_font_origin(24), fill=(235, 240, 245), anchor="lm")
        canvas.alpha_composite(badge, (1166 + i * 280, 408))

    draw = ImageDraw.Draw(canvas)
    canvas.alpha_composite(_load_icon("sec_icon.png", 54), (716, 466))
    draw.text((780, 462), "实时信息", font=nte_font_origin(42), fill=COLOR_WHITE, anchor="lt")
    draw.text(
        (780, 512),
        "REAL - TIME INFOMATION",
        font=nte_font_origin(20),
        fill=COLOR_SUB_GRAY,
        anchor="lt",
    )

    canvas.alpha_composite(Image.open(TEXTURE_PATH / "bg1.png").convert("RGBA"), (696, 568))

    cards = (
        ("stamina.png", "本性像素", str(home.stamina_value), str(home.stamina_max_value)),
        ("citystamina.png", "都市活力", str(home.city_stamina_value), str(home.city_stamina_max_value)),
        ("activity.png", "活跃度", str(home.day_value), "100"),
        ("weekcopies.png", "周本次数", str(home.week_copies_remain_cnt), "3"),
    )
    for i, (icon_name, label, val, mx) in enumerate(cards):
        row, col = divmod(i, 2)
        _draw_stat_cell(
            canvas,
            draw,
            _load_icon(icon_name, 128),
            label,
            val,
            mx,
            (736 + col * 500, 598 + row * 143),
        )

    add_footer(canvas)
    return await convert_img(canvas)
