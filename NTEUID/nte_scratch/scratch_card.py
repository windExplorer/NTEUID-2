"""刮刮乐统计图渲染"""
from __future__ import annotations

import json, re, math, random
from pathlib import Path
from datetime import datetime, timedelta, timezone

from PIL import Image, ImageDraw

from gsuid_core.logger import logger
from gsuid_core.models import Event

from ..utils.image import get_nte_bg, draw_card, make_nte_role_title, _load_card_long, TEXT_PATH

TZ_BJ = timezone(timedelta(hours=8))
SCALE = 2  # 超采样倍数：原生分辨率 ×2，放大后依旧清晰

W = 760
W_TODAY = 680
M = 20


def _f(size: int):
    from ..utils.fonts.nte_fonts import nte_font_bold
    return nte_font_bold(size * SCALE)

F12 = _f(12)
F13 = _f(13); F14 = _f(14); F15 = _f(15); F16 = _f(16)
F18 = _f(18); F20 = _f(20); F24 = _f(24); F28 = _f(28)
F30 = _f(30); F36 = _f(36)

CARD = (45, 48, 56)
CARD_ALT = (52, 55, 63)
TEXT = (230, 232, 236)
MUTED = (160, 165, 175)
DIM = (120, 125, 135)
GOLD = (255, 190, 50)
GREEN = (60, 200, 110)
RED = (240, 80, 80)
PURPLE = (180, 130, 255)
YELLOW_BRIGHT = (255, 200, 60)
SHADOW_COLOR = (30, 32, 38)


class ScaledDraw:
    """把 760 坐标系的绘制自动放大 SCALE 倍，使输出为高清图。"""

    def __init__(self, draw: ImageDraw.ImageDraw, k: int):
        self._d = draw
        self._k = k

    def _s(self, v: float) -> float:
        return v * self._k

    def text(self, xy, *args, **kwargs):
        x, y = xy
        self._d.text((self._s(x), self._s(y)), *args, **kwargs)

    def rectangle(self, xy, *args, **kwargs):
        if len(xy) == 2:
            x0 = y0 = x1 = y1 = 0
            (x0, y0), (x1, y1) = xy, xy
        else:
            x0, y0, x1, y1 = xy
        self._d.rectangle(
            [self._s(x0), self._s(y0), self._s(x1), self._s(y1)], *args, **kwargs
        )

    def rounded_rectangle(self, xy, radius=0, *args, **kwargs):
        x0, y0, x1, y1 = xy
        self._d.rounded_rectangle(
            [self._s(x0), self._s(y0), self._s(x1), self._s(y1)],
            radius=self._s(radius), *args, **kwargs,
        )

    def line(self, xy, *args, **kwargs):
        self._d.line([tuple(self._s(v) for v in p) for p in xy], *args, **kwargs)

    def ellipse(self, xy, *args, **kwargs):
        x0, y0, x1, y1 = xy
        self._d.ellipse(
            [self._s(x0), self._s(y0), self._s(x1), self._s(y1)], *args, **kwargs
        )


def _to_image_bytes(canvas: "Image.Image") -> bytes:
    from io import BytesIO
    buf = BytesIO()
    # 关闭色度子采样 + 高质量，保证文字放大锐利（与帮助图一致）
    canvas.convert("RGB").save(buf, format="JPEG", quality=95, subsampling=0)
    return buf.getvalue()


class SD:
    @staticmethod
    def rr(d, b, r, f):
        d.rounded_rectangle(b, r, fill=f)

def _sc(name):
    return (name or "").replace("《", "").replace("》", "")

def _ac(award):
    if not award: return DIM
    if "方斯" not in award: return GOLD
    m = re.search(r"方斯\*(\d+)", award)
    v = int(m.group(1)) if m else 0
    if v >= 30000: return YELLOW_BRIGHT
    if v >= 20000: return PURPLE
    if v >= 10000: return GREEN
    return DIM

def _aval(aw):
    m = re.search(r"方斯\*(\d+)", aw)
    return int(m.group(1)) if m else 0

def _line(d, y):
    d.rectangle([M, y, W - M, y + 1], fill=(60, 63, 70))

def _load_avatar(size=60):
    res_dir = Path(__file__).resolve().parent.parent / "resource"
    files = sorted((res_dir / "char" / "avatar").rglob("player_*_256.png")) if (res_dir / "char" / "avatar").exists() else []
    try:
        path = random.choice(files) if files else (res_dir.parent / "ICON.png")
        img = Image.open(path).convert("RGBA").resize((size, size), Image.LANCZOS)
        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).ellipse([0, 0, size, size], fill=255)
        rgba = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        rgba.paste(img, (0, 0), mask)
        return rgba
    except Exception:
        return None


def _ringed_avatar_prod(size, src=None):
    """圆形头像 + 白色描边环（大边距版，SCALE 坐标下绘制）"""
    av = src if isinstance(src, Image.Image) else _load_avatar(size)
    if av is None:
        return None
    inner = int(size * 4 / 5)
    off = (size - inner) // 2
    av = av.resize((inner, inner), Image.LANCZOS)
    base = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    mask = Image.new("L", (inner, inner), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, inner, inner], fill=255)
    base.paste(av, (off, off), mask)
    ring = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(ring).ellipse(
        [off, off, off + inner - 1, off + inner - 1],
        outline=(255, 255, 255, 230), width=max(2, SCALE * 2),
    )
    base.alpha_composite(ring)
    return base


def _make_role_title_prod(W, role_name, role_id, avatar):
    """面板图同款风格头部：card_long 不透明横条 + 大边距环形头像 + 昵称 + UID（SCALE 坐标）"""
    w = W * SCALE
    H = int(216 * w / 1100)
    BH = int(199 * w / 1100)
    canvas = Image.new("RGBA", (w, H), (0, 0, 0, 0))
    # 1) card_long 横条背景（199 比例 + maskB 二值化不透明 + 下移 8）
    card = _load_card_long(None)
    card_long = card.resize((int(1528 * w / 1100), int(128 * w / 1100)), Image.LANCZOS)
    ox, oy = int(-428 * w / 1100), int(56 * w / 1100)
    banner_layer = Image.new("RGBA", (w, BH), (0, 0, 0, 0))
    banner_layer.paste(card_long, (ox, oy), card_long)
    maskB = Image.open(TEXT_PATH / "maskB.png").convert("RGBA").resize((w, BH), Image.LANCZOS)
    mb = maskB.split()[3].point(lambda a: 255 if a > 128 else 0)
    banner = Image.new("RGBA", (w, BH), (0, 0, 0, 0))
    banner.paste(banner_layer, (0, 0), mask=mb)
    banner.putalpha(mb)  # 强制 banner alpha = 二值化 mask，避免 card_long 自身半透明导致整体发虚
    canvas.alpha_composite(banner, (0, int(8 * w / 1100)))
    # 2) 环形头像（大边距）
    av = _ringed_avatar_prod(int(216 * w / 1100), src=avatar)
    if av is not None:
        canvas.alpha_composite(av, (0, 0))
    # 3) 昵称 + UID 文字（用已含 SCALE 的字体，逻辑坐标）
    tx = int(240 * w / 1100)
    d = ImageDraw.Draw(canvas)
    d.text((tx, int(98 * w / 1100)), role_name, fill=(255, 255, 255), font=F20, anchor="lm")
    if role_id:
        d.text((tx, int(153 * w / 1100)), f"UID {role_id}", fill=(236, 238, 242), font=F14, anchor="lm")
    return canvas


# ── 总计统计图 ──

async def draw_scratch_stats(ev: Event) -> bytes | str:
    from ..utils.database import NTEKfCookie
    row = await NTEKfCookie.get_by_user(ev.user_id, ev.bot_id)
    if row is None or not row.raw_data or row.raw_data == "{}":
        return "暂无刮刮乐数据，请先去私聊【nte添加刮刮乐ck】"
    s = json.loads(row.raw_data)
    # 用户信息（复用面板图头部：头像 + 昵称 + UID）
    from gsuid_core.utils.image.image_tools import get_event_avatar
    from ..utils.database import NTEUser
    qq_avatar = None
    try:
        qq_avatar = await get_event_avatar(ev)
    except Exception:
        qq_avatar = None
    role_name = "玩家"
    if row.uid:
        try:
            mp = await NTEUser.identity_by_uids([row.uid])
            if row.uid in mp and mp[row.uid][1]:
                role_name = mp[row.uid][1]
        except Exception:
            pass
    return await _render_stats_image(s, row.last_updated, row.uid, qq_avatar, role_name)


async def _render_stats_image(
    summary: dict, last_updated: str, role_id: str,
    qq_avatar=None, role_name: str = "玩家",
) -> bytes:
    slices = summary.get("slices", [])
    all_pages = []
    for p in summary.get("pages", []):
        if isinstance(p, str): all_pages.append(p)
        else: all_pages.append(json.dumps(p))

    all_records = []
    for raw in all_pages:
        try:
            result = (json.loads(raw).get("data") or {}).get("result") or []
            if isinstance(result, list): all_records.extend(result)
        except: pass

    award_counts = {}
    for r in all_records:
        aw = r.get("award") or ""
        award_counts[aw] = award_counts.get(aw, 0) + 1

    ts = summary.get("total_spent", 0)
    ti = summary.get("total_income", 0)
    tp = summary.get("total_profit", 0)
    tr = summary.get("total_return_rate")
    total_cnt = len(all_records)
    # 单张消耗按整数分摊：总消耗 // 总次数，余数逐条 +1 方斯。
    # 这样每条记录消耗都是整数，各卡合计精确等于官方总消耗，全程不出现小数。
    if total_cnt:
        _base_cost = ts // total_cnt
        _rem_cost = ts % total_cnt
        _cost_of = [_base_cost + (1 if i < _rem_cost else 0) for i in range(total_cnt)]
    else:
        _cost_of = []
    dates_all = sorted(set((r.get("logTime") or "")[:10] for r in all_records if r.get("logTime")))

    # 趋势（按周）：直接复用官方切片的权威汇总，避免本地估算与总计口径不一致
    weekly_items = []
    for sl in summary.get("slices", []):
        sp = sl.get("spent", 0)
        inc = sl.get("income", 0)
        weekly_items.append({
            "start": (sl.get("start", "") or "")[:10],
            "end": (sl.get("end", "") or "")[:10],
            "spent": sp,
            "income": inc,
            "profit": inc - sp,
            "return_rate": (inc / sp * 100) if sp else None,
        })

    card_stats = {}
    for idx, r in enumerate(all_records):
        cid = _sc(r.get("scratchCardId", "") or "未知")
        if cid not in card_stats:
            card_stats[cid] = {"count": 0, "award_sum": 0, "award_count": 0, "cost_sum": 0}
        st = card_stats[cid]
        st["count"] += 1
        st["cost_sum"] += _cost_of[idx] if _cost_of else 0
        aw = r.get("award") or ""
        if aw and "方斯" in aw:
            v = _aval(aw)
            st["award_sum"] += v
            st["award_count"] += 1
    card_items = sorted(card_stats.items(), key=lambda x: -x[1]["count"])

    award_items = sorted(award_counts.items(), key=lambda x: -_aval(x[0]))

    _MAX_H = 6000
    canvas = get_nte_bg(W * SCALE, _MAX_H * SCALE, bg="bg3")
    _overlay = Image.new("RGBA", (W * SCALE, _MAX_H * SCALE), (20, 22, 28, 120))
    canvas.paste(_overlay, (0, 0), _overlay)
    d = ScaledDraw(ImageDraw.Draw(canvas), SCALE)

    # 顶部用户信息（面板图同款风格：card_long 不透明横条 + 大边距环形头像 + 昵称 + UID）
    if not isinstance(qq_avatar, Image.Image):
        qq_avatar = _load_avatar(96) or Image.new("RGBA", (96, 96), (70, 74, 84))
    header_img = _make_role_title_prod(W, role_name, role_id, qq_avatar)
    canvas.paste(header_img, (0, 0), header_img)
    y = header_img.height // SCALE + 14
    d.text((M, y), "猫亭刮刮乐 · 午夜猫刊亭刮刮乐数据统计", fill=TEXT, font=F18)
    d.text((M, y + 30), f"更新于 {last_updated} · 共 {total_cnt} 条记录 · {len(dates_all)} 天", fill=MUTED, font=F14)
    y += 64

    # 概况
    stats = [
        ("总消费", f"{ts:,}", "方斯", TEXT),
        ("总收入", f"{ti:,}", "方斯", TEXT),
        ("总盈亏", f"{tp:+,}", "方斯", GREEN if tp >= 0 else RED),
        ("回报率", f"{tr:.2f}%" if tr else "N/A", "", GOLD),
        ("总刮卡次数", f"{total_cnt}", "次", MUTED),
        ("刮卡天数", f"{len(dates_all)}", "天", MUTED),
    ]
    cw = (W - M * 2 - 12) // 2
    for i, (lb, val, unit, clr) in enumerate(stats):
        c, r = i % 2, i // 2
        x = M + c * (cw + 14)
        yy = y + r * 100
        draw_card(d, (x, yy, x + cw, yy + 82), radius=16, fill=CARD)
        d.text((x + 18, yy + 12), lb, fill=MUTED, font=F14)
        d.text((x + 18, yy + 44), val, fill=clr, font=F30)
        if unit:
            d.text((x + 18 + F30.getlength(val) + 4, yy + 48), unit, fill=DIM, font=F13)
    y += 300 + 30

    # 每周趋势
    d.text((M, y), "趋势（按周）", fill=TEXT, font=F20)
    y += 36
    _line(d, y)
    y += 14
    for idx, st in enumerate(weekly_items):
        c, r = idx % 2, idx // 2
        x = M + c * (cw + 14)
        yy = y + r * 96
        draw_card(d, (x, yy, x + cw, yy + 78), radius=12, fill=CARD)
        pft = st["profit"]
        rt = st["return_rate"]
        d.text((x + 16, yy + 12), f"{st['start']} ~ {st['end']}", fill=MUTED, font=F13)
        d.text((x + 16, yy + 38), f"盈亏: {pft:+,}", fill=GREEN if pft >= 0 else RED, font=F18)
        if rt is not None:
            d.text((x + 16, yy + 58), f"消耗 {st['spent']:,} · 收入 {st['income']:,} · 回报率 {rt:.1f}%", fill=MUTED, font=F13)
        else:
            d.text((x + 16, yy + 58), f"消耗 {st['spent']:,} · 收入 {st['income']:,}", fill=MUTED, font=F13)
    y += math.ceil(len(weekly_items) / 2) * 96 + 30

    # 奖励分布
    d.text((M, y), "奖励分布", fill=TEXT, font=F20)
    y += 36
    _line(d, y)
    y += 12
    SD.rr(d, (M, y, W - M, y + 30), 8, (55, 58, 66))
    d.text((M + 20, y + 6), "奖励", fill=TEXT, font=F14)
    d.text((M + 280, y + 6), "次数", fill=TEXT, font=F14)
    d.text((M + 360, y + 6), "总计金额", fill=TEXT, font=F14)
    d.text((M + 490, y + 6), "占比", fill=TEXT, font=F14)
    y += 34
    for idx, (aw, cnt) in enumerate(award_items):
        bg2 = CARD if idx % 2 == 0 else CARD_ALT
        SD.rr(d, (M, y, W - M, y + 36), 8, bg2)
        clr = _ac(aw)
        lb = aw if aw else "未中奖"
        v = _aval(aw)
        tv = v * cnt
        pct = cnt / total_cnt * 100 if total_cnt else 0
        SD.rr(d, (M + 14, y + 10, M + 26, y + 26), 4, clr)
        d.text((M + 34, y + 8), lb, fill=TEXT, font=F13)
        d.text((M + 280, y + 8), str(cnt), fill=clr, font=F13)
        d.text((M + 360, y + 8), f"{tv:,}" if tv else "", fill=DIM, font=F13)
        d.text((M + 490, y + 8), f"{pct:.1f}%", fill=MUTED, font=F13)
        y += 44
    y += 30

    # 各刮刮卡统计
    d.text((M, y), "各刮刮卡统计", fill=TEXT, font=F20)
    y += 36
    _line(d, y)
    y += 12
    SD.rr(d, (M, y, W - M, y + 30), 8, (55, 58, 66))
    d.text((M + 20, y + 6), "刮刮卡", fill=TEXT, font=F14)
    d.text((M + 200, y + 6), "次数", fill=TEXT, font=F14)
    d.text((M + 280, y + 6), "中奖/未中", fill=TEXT, font=F14)
    d.text((M + 390, y + 6), "中奖金额", fill=TEXT, font=F14)
    d.text((M + 530, y + 6), "净盈亏", fill=TEXT, font=F14)
    y += 34
    for idx, (cid, st) in enumerate(card_items):
        bg2 = CARD if idx % 2 == 0 else CARD_ALT
        SD.rr(d, (M, y, W - M, y + 36), 8, bg2)
        sp = st["cost_sum"]
        pft = st["award_sum"] - sp
        d.text((M + 14, y + 8), cid, fill=TEXT, font=F13)
        d.text((M + 200, y + 8), str(st["count"]), fill=TEXT, font=F13)
        d.text((M + 280, y + 8), f"{st['award_count']}/{st['count'] - st['award_count']}", fill=MUTED, font=F13)
        d.text((M + 390, y + 8), f"{st['award_sum']:,}", fill=GREEN, font=F13)
        d.text((M + 530, y + 8), f"{pft:+,}", fill=GREEN if pft >= 0 else RED, font=F13)
        y += 44
    y += 30

    # 最近明细
    d.text((M, y), "最近明细", fill=TEXT, font=F20)
    y += 36
    _line(d, y)
    y += 12
    records_sorted = sorted(all_records, key=lambda r: r.get("logTime", ""), reverse=True)
    for idx, rec in enumerate(records_sorted[:15]):
        bg2 = CARD if idx % 2 == 0 else CARD_ALT
        SD.rr(d, (M, y, W - M, y + 30), 8, bg2)
        lt = rec.get("logTime", "") or ""
        cn = _sc(rec.get("scratchCardId", "") or "")
        aw = rec.get("award", "") or "未中奖"
        d.text((M + 14, y + 6), lt, fill=MUTED, font=F13)
        d.text((M + 160, y + 6), cn, fill=MUTED, font=F13)
        d.text((W - 220, y + 6), aw, fill=_ac(rec.get("award", "")), font=F13)
        y += 34
    if len(records_sorted) > 15:
        d.text((M + 14, y + 3), f"... 共 {len(records_sorted)} 条记录", fill=MUTED, font=F13)

    # 底部
    y += 40
    d.rectangle([0, y, W, y + 36], fill=(30, 32, 40))
    d.text((M, y + 10), "NTEUID · 一切正常，就是异常。", fill=(100, 105, 115), font=F13)
    y += 36

    canvas = canvas.crop((0, 0, W * SCALE, y * SCALE))
    return _to_image_bytes(canvas)


# ── 今日统计图 ──

async def draw_scratch_today(user_id: str, bot_id: str) -> bytes | str:
    from ..utils.database import NTEKfCookie
    row = await NTEKfCookie.get_by_user(user_id, bot_id)
    if row is None or not row.cookie or not row.uid:
        return "你还没有绑定刮刮乐 ck！请【私聊】nte添加刮刮乐ck"
    from .scratch_service import fetch_today_data
    try:
        today = await fetch_today_data(row.cookie, row.uid)
    except Exception as e:
        logger.exception(f"[刮刮乐] 今日查询失败: {e}")
        return "今日刮刮乐数据查询失败，请稍后重试或联系管理员。"
    if today is None:
        return f"📅 {datetime.now(TZ_BJ).strftime('%Y-%m-%d')} 暂无刮刮乐记录"
    return await _render_today_image(today, datetime.now(TZ_BJ).strftime("%Y-%m-%d"))


async def _render_today_image(today: dict, today_str: str) -> bytes:
    records = today.get("records", [])
    spent = today.get("spent", 0)
    income = today.get("income", 0)
    profit = today.get("profit", 0)
    rate = today.get("return_rate")

    award_cnt = {}
    for r in records:
        aw = r.get("award") or ""
        award_cnt[aw] = award_cnt.get(aw, 0) + 1
    award_items = sorted(award_cnt.items(), key=lambda x: -_aval(x[0]))[:6]

    _MAX_H = 3000
    canvas = get_nte_bg(W_TODAY * SCALE, _MAX_H * SCALE, bg="bg3")
    _overlay = Image.new("RGBA", (W_TODAY * SCALE, _MAX_H * SCALE), (20, 22, 28, 120))
    canvas.paste(_overlay, (0, 0), _overlay)
    d = ScaledDraw(ImageDraw.Draw(canvas), SCALE)

    # 标题（半透明背景让 bg3 透出）
    _title_overlay = Image.new("RGBA", (W_TODAY * SCALE, 160 * SCALE), (30, 32, 40, 180))
    canvas.paste(_title_overlay, (0, 0), _title_overlay)
    d.rectangle([M, 158, M + 60, 160], fill=(80, 140, 210))
    d.text((M, 28), "今日刮刮乐", fill=(255, 255, 255), font=F36)
    avatar = _load_avatar(56 * SCALE)
    if avatar:
        tw = int(F36.getlength("今日刮刮乐"))
        canvas.paste(avatar, ((M + tw + 14) * SCALE, 24 * SCALE), avatar)
    tt = M + tw + 80 if avatar else M + 220
    SD.rr(d, (tt, 34, tt + 80, 58), 12, (50, 54, 64))
    d.text((tt + 10, 37), today_str, fill=GOLD, font=F16)
    d.text((M, 80), "午夜猫刊亭刮刮乐数据统计", fill=(170, 178, 190), font=F16)
    d.text((M, 108), f"今日刮了 {len(records)} 次", fill=(130, 138, 150), font=F14)
    y = 180

    # 四张卡片
    cw = (W_TODAY - M * 2 - 14) // 2
    for i, (lb, val, clr, unit) in enumerate([
        ("消费", f"{spent:,}", MUTED, "方斯"),
        ("收入", f"{income:,}", GREEN, "方斯"),
        ("盈亏", f"{profit:+,}", GREEN if profit >= 0 else RED, "方斯"),
        ("回报率", f"{rate:.2f}%" if rate else "N/A", GOLD, ""),
    ]):
        c, r = i % 2, i // 2
        x = M + c * (cw + 14)
        yy = y + r * 88
        draw_card(d, (x, yy, x + cw, yy + 76), radius=14, fill=CARD)
        cx = x + cw // 2
        d.text((cx, yy + 10), lb, fill=MUTED, font=F14, anchor="mt")
        d.text((cx, yy + 34), val, fill=clr, font=F28, anchor="mt")
        if unit:
            d.text((cx, yy + 58), unit, fill=DIM, font=F12, anchor="mt")
    y += 176 + 30

    # 奖励分布
    if award_items:
        SD.rr(d, (M, y, W_TODAY - M, y + 30), 8, (55, 58, 66))
        d.text((M + 14, y + 6), "奖励", fill=TEXT, font=F14)
        d.text((M + 200, y + 6), "次数", fill=TEXT, font=F14)
        d.text((M + 280, y + 6), "金额", fill=TEXT, font=F14)
        d.text((M + 400, y + 6), "小计", fill=TEXT, font=F14)
        y += 34
        for idx, (aw, cnt) in enumerate(award_items):
            bg2 = CARD if idx % 2 == 0 else CARD_ALT
            SD.rr(d, (M, y, W_TODAY - M, y + 36), 8, bg2)
            v = _aval(aw)
            tv = v * cnt
            clr = PURPLE if v >= 20000 else GREEN if v >= 10000 else MUTED
            lb = aw if aw else "未中奖"
            SD.rr(d, (M + 12, y + 10, M + 24, y + 26), 4, clr)
            d.text((M + 30, y + 8), lb, fill=TEXT, font=F13)
            d.text((M + 200, y + 8), str(cnt), fill=clr, font=F13)
            d.text((M + 280, y + 8), f"{v:,}" if v else "", fill=MUTED, font=F13)
            d.text((M + 400, y + 8), f"{tv:,}" if tv else "", fill=clr, font=F13)
            y += 44
        y += 30

    # 今日记录
    SD.rr(d, (M, y, W_TODAY - M, y + 30), 8, (55, 58, 66))
    d.text((M + 14, y + 6), "时间", fill=TEXT, font=F14)
    d.text((M + 100, y + 6), "卡名", fill=TEXT, font=F14)
    d.text((M + 280, y + 6), "奖励", fill=TEXT, font=F14)
    y += 34
    for idx, r in enumerate(records):
        bg2 = CARD if idx % 2 == 0 else CARD_ALT
        SD.rr(d, (M, y, W_TODAY - M, y + 30), 8, bg2)
        aw = r.get("award", "") or "未中奖"
        clr = GREEN if aw != "未中奖" else MUTED
        cn = (r.get("scratchCardId", "") or "").replace("《", "").replace("》", "")
        d.text((M + 14, y + 6), (r.get("logTime") or "")[-8:], fill=MUTED, font=F13)
        d.text((M + 100, y + 6), cn, fill=MUTED, font=F13)
        d.text((M + 280, y + 6), aw, fill=clr, font=F13)
        d.text((W_TODAY - 50, y + 6), "✓" if aw != "未中奖" else "✗", fill=GREEN if aw != "未中奖" else RED, font=F15)
        y += 34

    # 底部
    y += 30
    d.rectangle([0, y, W_TODAY, y + 36], fill=(30, 32, 40))
    d.text((M, y + 10), "NTEUID · 一切正常，就是异常。", fill=(100, 105, 115), font=F13)
    y += 36

    canvas = canvas.crop((0, 0, W_TODAY * SCALE, y * SCALE))
    return _to_image_bytes(canvas)


# ── 排名图 ──

async def draw_scratch_rank() -> bytes | str:
    from ..utils.database import NTEKfCookie, NTEUser

    rows = await NTEKfCookie.list_ranked_by_profit(limit=10)
    if not rows:
        return "暂无刮刮乐排名数据。"

    # 取用户展示名 + QQ头像
    from ..utils.avatar import get_qq_avatar

    user_names: dict[str, str] = {}
    user_avatars: dict[str, Image.Image] = {}
    for row in rows:
        name = row.user_id
        try:
            u = await NTEUser.get_active(row.user_id, row.bot_id)
            if u and u.role_name:
                name = u.role_name
        except Exception:
            pass
        user_names[row.user_id] = name
        try:
            av = await get_qq_avatar(row.user_id)
            av = av.resize((30 * SCALE, 30 * SCALE), Image.LANCZOS)
            mask = Image.new("L", (30 * SCALE, 30 * SCALE), 0)
            ImageDraw.Draw(mask).ellipse([0, 0, 30 * SCALE, 30 * SCALE], fill=255)
            av_rgba = Image.new("RGBA", (30 * SCALE, 30 * SCALE), (0, 0, 0, 0))
            av_rgba.paste(av, (0, 0), mask)
            user_avatars[row.user_id] = av_rgba
        except Exception:
            pass

    _MAX_H = 2000
    rank_w = 700
    canvas = get_nte_bg(rank_w * SCALE, _MAX_H * SCALE, bg="bg3")
    _overlay = Image.new("RGBA", (rank_w * SCALE, _MAX_H * SCALE), (20, 22, 28, 120))
    canvas.paste(_overlay, (0, 0), _overlay)
    d = ScaledDraw(ImageDraw.Draw(canvas), SCALE)

    # 标题
    _title = Image.new("RGBA", (rank_w * SCALE, 120 * SCALE), (30, 32, 40, 180))
    canvas.paste(_title, (0, 0), _title)
    d.rectangle([20, 118, 80, 120], fill=(80, 140, 210))
    d.text((20, 28), "刮刮乐排行", fill=(255, 255, 255), font=F36)
    d.text((20, 74), "累计总盈亏排名 TOP10", fill=(170, 178, 190), font=F16)
    y = 140

    # 表头
    SD.rr(d, (20, y, rank_w - 20, y + 28), 8, (55, 58, 66))
    d.text((36, y + 5), "#", fill=MUTED, font=F14)
    d.text((104, y + 5), "用户", fill=TEXT, font=F14)
    d.text((180, y + 5), "总次数", fill=TEXT, font=F14)
    d.text((260, y + 5), "总消费", fill=TEXT, font=F14)
    d.text((360, y + 5), "总盈亏", fill=TEXT, font=F14)
    d.text((480, y + 5), "回报率", fill=TEXT, font=F14)
    y += 32

    # 排名
    for idx, row in enumerate(rows):
        bg2 = CARD if idx % 2 == 0 else CARD_ALT
        SD.rr(d, (20, y, rank_w - 20, y + 36), 8, bg2)
        rank_clr = GOLD if idx == 0 else (200, 200, 210) if idx == 1 else (180, 140, 100) if idx == 2 else MUTED
        d.text((34, y + 8), str(idx + 1), fill=rank_clr, font=F18)
        av = user_avatars.get(row.user_id)
        if av:
            canvas.paste(av, (66 * SCALE, (y + 3) * SCALE), av)
        disp = user_names.get(row.user_id, row.user_id)[:10]
        d.text((104, y + 8), disp, fill=TEXT, font=F14)
        cnt = row.total_spent // 10000 if row.total_spent else 0
        d.text((180, y + 8), str(cnt), fill=MUTED, font=F13)
        d.text((260, y + 8), f"{row.total_spent:,}", fill=MUTED, font=F13)
        pft_clr = GREEN if row.profit >= 0 else RED
        d.text((360, y + 8), f"{row.profit:+,}", fill=pft_clr, font=F14)
        if row.return_rate is not None:
            rt_clr = GREEN if row.return_rate >= 100 else RED if row.return_rate < 50 else GOLD
            d.text((480, y + 8), f"{row.return_rate:.1f}%", fill=rt_clr, font=F13)
        y += 44

    y += 30
    d.rectangle([0, y, rank_w, y + 36], fill=(30, 32, 40))
    d.text((20, y + 10), "NTEUID · 一切正常，就是异常。", fill=(100, 105, 115), font=F13)
    y += 36

    canvas = canvas.crop((0, 0, rank_w * SCALE, y * SCALE))
    return _to_image_bytes(canvas)
