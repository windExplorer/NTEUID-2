from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from gsuid_core.models import Event
from gsuid_core.utils.image.convert import convert_img
from gsuid_core.utils.image.image_tools import get_event_avatar

from ..utils.image import COLOR_WHITE, SmoothDrawer, add_footer, get_nte_bg, open_texture, make_nte_role_title
from ..utils.resource.cdn import (
    get_weapon_img,
    get_char_skill_img,
    get_char_detail_img,
    get_char_element_img,
    get_char_property_img,
    get_char_suit_drive_img,
)
from ..utils.fonts.nte_fonts import nte_font_origin
from ..utils.sdk.tajiduo_model import (
    CharQuality,
    CharacterFork,
    CharacterSkill,
    CharacterDetail,
    CharacterProperty,
    CharacterSuitItem,
)

WIDTH = 1100
BODY_TOP = 248
GAP = 28
TEX = Path(__file__).parent / "texture2d" / "character"

ROW_HILITE = (255, 0, 235)
ZERO_VALUES = {"", "0", "0%", "0.0", "0.0%"}


def _format_value(value: str) -> str:
    raw = value.strip()
    if raw.endswith("%"):
        try:
            num = float(raw[:-1])
        except ValueError:
            return value
        return f"{num:.1f}%" if num % 1 else f"{num:.0f}%"
    try:
        return str(round(float(raw)))
    except ValueError:
        return value


def _visible_props(props: list[CharacterProperty], limit: int) -> list[CharacterProperty]:
    return [prop for prop in props if prop.name and prop.value.strip() not in ZERO_VALUES][:limit]


def _fit_text(draw: ImageDraw.ImageDraw, text: str, width: int, font) -> str:
    if round(draw.textlength(text, font=font)) <= width:
        return text
    value = text
    while value and round(draw.textlength(f"{value}...", font=font)) > width:
        value = value[:-1]
    return f"{value}..." if value else "..."


async def _prop_icon(prop_id: str, size: int) -> Image.Image | None:
    icon = await get_char_property_img(prop_id)
    return icon.resize((size, size), Image.Resampling.LANCZOS) if icon is not None else None


def _badge(icon: Image.Image, size: int) -> Image.Image:
    ring = open_texture(TEX / "char_ring.png", (size, size))
    ring.alpha_composite(icon.convert("RGBA").resize((size, size), Image.Resampling.LANCZOS))
    return ring


def _rank_img(quality: CharQuality | None, size: int) -> Image.Image | None:
    if quality is CharQuality.S:
        rank = "S"
    elif quality is CharQuality.A:
        rank = "A"
    else:
        rank = "B"
    return open_texture(TEX / f"rank_{rank}.png", (size, size))


def _drive_rank(item_id: str) -> Image.Image | None:
    rank = {"orange": "S", "purple": "A", "blue": "B"}.get(item_id.rsplit("_", 1)[-1].lower())
    return open_texture(TEX / f"rank_{rank}.png", (48, 48)) if rank else None


async def _draw_attrs(canvas: Image.Image, draw: ImageDraw.ImageDraw, props: list[CharacterProperty]) -> None:
    font_name = nte_font_origin(28)
    font_value = nte_font_origin(34)
    for index, prop in enumerate(_visible_props(props, 9)):
        x, y = 620, BODY_TOP + 204 + index * 64
        canvas.alpha_composite(open_texture(TEX / "attr_bar.png"), (x, y))
        icon = await _prop_icon(prop.id, 40)
        if icon is not None:
            canvas.alpha_composite(icon, (x + 10, y + 10))
        draw.text((x + 66, y + 31), prop.name, font=font_name, fill=COLOR_WHITE, anchor="lm")
        draw.text((x + 414, y + 31), _format_value(prop.value), font=font_value, fill=COLOR_WHITE, anchor="rm")


async def _draw_skills(canvas: Image.Image, draw: ImageDraw.ImageDraw, skills: list[CharacterSkill]) -> None:
    font_name = nte_font_origin(18)
    font_level = nte_font_origin(20)
    for index, skill in enumerate([s for s in skills if s.name and s.type != "Passive"][:4]):
        x, y = 58 + index * 130, BODY_TOP + 735
        canvas.alpha_composite(open_texture(TEX / "skill_bg.png"), (x, y))
        icon = await get_char_skill_img(skill.id) if skill.id else None
        if icon is not None:
            canvas.alpha_composite(icon.convert("RGBA").resize((64, 64)), (x + 18, y + 18))
        canvas.alpha_composite(open_texture(TEX / "skill_fg.png"), (x, y))
        draw.text((x + 50, y + 89), skill.name[:4], font=font_name, fill=COLOR_WHITE, anchor="mm")
        draw.text((x + 50, y + 115), f"Lv{skill.level}", font=font_level, fill=COLOR_WHITE, anchor="mm")


def _draw_score(
    canvas: Image.Image, draw: ImageDraw.ImageDraw, xy: tuple[int, int], quality: CharQuality | None
) -> None:
    x, y = xy
    canvas.alpha_composite(open_texture(TEX / "score_bg.png"), (x, y))
    canvas.alpha_composite(open_texture(TEX / "score_fg.png"), (x, y))
    rank = _rank_img(quality, 92)
    if rank is not None:
        canvas.alpha_composite(rank, (x + 130, y + 58))
    draw.text((x + 180, y + 218), "--分", font=nte_font_origin(42), fill=COLOR_WHITE, anchor="mm")


async def _draw_weapon(
    canvas: Image.Image,
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    fork: CharacterFork,
) -> None:
    x, y = xy
    font_name = nte_font_origin(36)
    font_text = nte_font_origin(26)
    canvas.alpha_composite(open_texture(TEX / "weapon_bg.png"), (x, y))
    weapon = await get_weapon_img(fork.id)
    if weapon is not None:
        weapon.thumbnail((205, 205), Image.Resampling.LANCZOS)
        canvas.alpha_composite(weapon.convert("RGBA"), (x + 20, y + 12))
    canvas.alpha_composite(open_texture(TEX / "weapon_fg.png"), (x, y))

    name = _fit_text(draw, fork.name, 295, font_name)
    draw.text((x + 318, y + 41), name, font=font_name, fill=COLOR_WHITE, anchor="lm")
    stage = int(fork.blev) if fork.blev.isdigit() else 0
    stage_text = f"{stage}阶"
    stage_w = round(draw.textlength(stage_text, font=font_text)) + 34
    SmoothDrawer().rounded_rectangle(
        (x + 568, y + 23, x + 568 + stage_w, y + 69),
        23,
        fill=(231, 46, 58, 245),
        target=canvas,
    )
    draw.text((x + 568 + stage_w // 2, y + 46), stage_text, font=font_text, fill=COLOR_WHITE, anchor="mm")

    star = open_texture(TEX / "drive_star.png", (34, 34))
    star_none = open_texture(TEX / "drive_star_none.png", (34, 34))
    for index in range(5):
        canvas.alpha_composite(star if index < max(0, min(5, stage)) else star_none, (x + 257 + index * 38, y + 74))

    draw.text((x + 124, y + 224), f"Lv{fork.alev}", font=font_name, fill=COLOR_WHITE, anchor="mm")
    for index, prop in enumerate(_visible_props(fork.properties, 2)):
        px, py = x + 251, y + 125 + index * 66
        canvas.alpha_composite(open_texture(TEX / "weapon_attr_bar.png"), (px, py))
        icon = await _prop_icon(prop.id, 48)
        if icon is not None:
            canvas.alpha_composite(icon, (px + 8, py + 7))
        draw.text((px + 78, py + 31), prop.name, font=font_text, fill=COLOR_WHITE, anchor="lm")
        draw.text((px + 334, py + 31), f"+{_format_value(prop.value)}", font=font_text, fill=COLOR_WHITE, anchor="rm")


async def _draw_drive_prop(
    canvas: Image.Image,
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    prop: CharacterProperty,
    color: tuple[int, int, int],
) -> None:
    x, y = xy
    font = nte_font_origin(24)
    canvas.alpha_composite(open_texture(TEX / "ad_attr_bg.png"), (x, y))
    icon = await _prop_icon(prop.id, 34)
    if icon is not None:
        canvas.alpha_composite(icon, (x + 6, y + 6))
    draw.text(
        (x + 52, y + 24),
        _fit_text(draw, prop.name, 170, font),
        font=font,
        fill=color,
        anchor="lm",
    )
    draw.text((x + 306, y + 24), _format_value(prop.value), font=font, fill=color, anchor="rm")


async def _draw_drive(
    canvas: Image.Image, draw: ImageDraw.ImageDraw, xy: tuple[int, int], item: CharacterSuitItem
) -> None:
    x, y = xy
    font_name = nte_font_origin(26)
    font_label = nte_font_origin(24)
    canvas.alpha_composite(open_texture(TEX / "ad_bg.png"), (x, y))
    drive = await get_char_suit_drive_img(item.id) if item.id else None
    if drive is not None:
        canvas.alpha_composite(drive.convert("RGBA").resize((92, 92)), (x + 18, y + 16))
    rank = _drive_rank(item.id)
    if rank is not None:
        canvas.alpha_composite(rank, (x + 110, y + 62))
    draw.text(
        (x + 116, y + 34),
        _fit_text(draw, item.name, 220, font_name),
        font=font_name,
        fill=COLOR_WHITE,
        anchor="lm",
    )
    cursor = y + 124
    for title, props, limit in (("基础属性", item.main_properties, 2), ("附加属性", item.properties, 4)):
        items = _visible_props(props, limit)
        if not items:
            continue
        canvas.alpha_composite(open_texture(TEX / "ad_title_bg.png"), (x + 34, cursor))
        draw.text((x + 130, cursor + 18), title, font=font_label, fill=(25, 25, 25), anchor="mm")
        cursor += 49
        for index, prop in enumerate(items):
            await _draw_drive_prop(canvas, draw, (x + 20, cursor), prop, COLOR_WHITE)
            cursor += 49


async def draw_character_card_img(ev: Event, character: CharacterDetail, role_name: str, uid: str) -> bytes:
    suit_items = [*character.suit.core, *character.suit.pie] if character.suit.id else []
    drive_rows = (len(suit_items) + 2) // 3
    drive_h = 0 if not suit_items else drive_rows * 554 + (drive_rows - 1) * GAP
    gear_h = 272 if suit_items or character.fork.id else 0
    height = BODY_TOP + 880 + (GAP + gear_h if gear_h else 0) + (GAP + drive_h if drive_h else 0) + 96

    canvas = get_nte_bg(WIDTH, height, bg="bg3")
    title = make_nte_role_title(await get_event_avatar(ev), role_name, uid).resize(
        (1024, 201), Image.Resampling.LANCZOS
    )
    canvas.alpha_composite(title, (38, 30))
    draw = ImageDraw.Draw(canvas)

    art = await get_char_detail_img(character.id)
    if art is not None:
        canvas.alpha_composite(art.convert("RGBA").resize((718, 850), Image.Resampling.LANCZOS), (0, BODY_TOP - 28))

    x, y = 620, BODY_TOP + 8
    canvas.alpha_composite(open_texture(TEX / "base_info_bg.png"), (x, y))
    elem = await get_char_element_img(character.element_type.value)
    if elem is not None:
        canvas.alpha_composite(_badge(elem, 44), (x + 8, y + 7))
    font_level = nte_font_origin(30)
    font_title = nte_font_origin(44)
    draw.text((x + 111, y + 29), f"Lv{character.alev}", font=font_level, fill=COLOR_WHITE, anchor="mm")
    draw.text(
        (x + 176, y + 29),
        _fit_text(draw, character.name, 220, font_title),
        font=font_title,
        fill=COLOR_WHITE,
        anchor="lm",
    )

    y = BODY_TOP + 92
    font_heading = nte_font_origin(34)
    font_text = nte_font_origin(26)
    canvas.alpha_composite(open_texture(TEX / "banner.png", (300, 81)), (x, y))
    draw.text((x + 105, y + 41), "角色属性", font=font_heading, fill=(25, 25, 25), anchor="lm")
    canvas.alpha_composite(open_texture(TEX / "heart.png", (60, 52)), (x + 305, y + 15))
    like = character.likeability_lev if character.likeability_lev <= 10 else min(10, character.likeability_lev // 40)
    draw.text((x + 335, y + 41), str(max(0, like)), font=font_text, fill=COLOR_WHITE, anchor="mm")
    canvas.alpha_composite(open_texture(TEX / "jue.png", (63, 48)), (x + 374, y + 17))
    draw.text((x + 405, y + 41), f"{character.awaken_lev}觉", font=font_text, fill=COLOR_WHITE, anchor="mm")

    await _draw_attrs(canvas, draw, character.properties)
    await _draw_skills(canvas, draw, character.skills)

    cursor = BODY_TOP + 880 + GAP
    if gear_h:
        if suit_items:
            _draw_score(canvas, draw, (18, cursor), character.quality)
        if character.fork.id:
            await _draw_weapon(canvas, draw, (406 if suit_items else 18, cursor), character.fork)
        cursor += gear_h + GAP
    for index, item in enumerate(suit_items):
        await _draw_drive(canvas, draw, (4 + index % 3 * 366, cursor + index // 3 * (554 + GAP)), item)

    add_footer(canvas)
    return await convert_img(canvas)
