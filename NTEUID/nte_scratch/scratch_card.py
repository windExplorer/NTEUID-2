"""刮刮乐统计图渲染（与角色面板同背景/转码逻辑）。"""
from __future__ import annotations

import json, re, math, random
from pathlib import Path
from datetime import datetime, timedelta, timezone

from PIL import Image, ImageDraw, ImageFont

from gsuid_core.logger import logger
from gsuid_core.utils.image.convert import convert_img

from ..utils.image import get_nte_bg, draw_card, get_nte_title_bg
from ..utils.fonts.nte_fonts import nte_font_origin as _f

TZ_BJ = timezone(timedelta(hours=8))
W = 1100
M = 28


def _fload(size: int) -> ImageFont.FreeTypeFont:
    return _f(size)

F13 = _fload(13); F14 = _fload(14); F15 = _fload(15); F16 = _fload(16)
F18 = _fload(18); F20 = _fload(20); F24 = _fload(24); F28 = _fload(28)
F30 = _fload(30); F36 = _fload(36)


BG = (245, 242, 234)
CARD = (255, 253, 248)
CARD_ALT = (248, 246, 240)
TEXT = (60, 60, 70)
MUTED = (140, 140, 150)
DIM = (170, 170, 180)
GOLD = (200, 150, 60)
GREEN = (40, 160, 90)
RED = (220, 60, 60)
PURPLE = (150, 100, 200)
YELLOW_BRIGHT = (220, 170, 40)
TITLE_BG = (40, 80, 120)


class SD:
    @staticmethod
    def rr(d, b, r, f):
        d.rounded_rectangle(b, r, fill=f)

def _sc(name):
    return (name or "").replace("《", "").replace("》", "")

def _ac(award):
    if not award: return MUTED
    if "方斯" not in award: return GOLD
    m = re.search(r"方斯\*(\d+)", award)
    v = int(m.group(1)) if m else 0
    if v >= 30000: return YELLOW_BRIGHT
    if v >= 20000: return PURPLE
    if v >= 10000: return GREEN
    return MUTED

def _aval(aw):
    m = re.search(r"方斯\*(\d+)", aw)
    return int(m.group(1)) if m else 0

def _line(d, y):
    d.rectangle([M, y, W - M, y + 1], fill=(220, 218, 210))

def _load_avatar(size=64):
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


# ── 总计统计图 ──

async def draw_scratch_stats(user_id: str, bot_id: str) -> bytes | str:
    from ..utils.database import NTEKfCookie
    row = await NTEKfCookie.get_by_user(user_id, bot_id)
    if row is None or not row.raw_data or row.raw_data == "{}":
        return "暂无刮刮乐数据，请先去私聊【添加刮刮乐ck】"
    s = json.loads(row.raw_data)
    return await _render_stats_image(s, row.last_updated, row.uid)


async def _render_stats_image(summary: dict, last_updated: str, role_id: str) -> bytes:
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
    dates_all = sorted(set((r.get("logTime") or "")[:10] for r in all_records if r.get("logTime")))

    weekly = {}
    for r in all_records:
        lt = (r.get("logTime") or "")[:10]
        if not lt: continue
        d = datetime.strptime(lt, "%Y-%m-%d")
        wk = d.strftime("%Y-W%V")
        if wk not in weekly:
            weekly[wk] = {"count": 0, "income": 0, "start": lt, "end": lt}
        weekly[wk]["count"] += 1
        weekly[wk]["end"] = lt
        aw = r.get("award") or ""
        if "方斯" in aw: weekly[wk]["income"] += _aval(aw)
    weekly_items = sorted(weekly.items(), key=lambda x: x[0])

    card_stats = {}
    for r in all_records:
        cid = _sc(r.get("scratchCardId", "") or "未知")
        if cid not in card_stats:
            card_stats[cid] = {"count": 0, "award_sum": 0, "award_count": 0}
        card_stats[cid]["count"] += 1
        aw = r.get("award") or ""
        if aw and "方斯" in aw:
            v = _aval(aw)
            card_stats[cid]["award_sum"] += v
            card_stats[cid]["award_count"] += 1
    card_items = sorted(card_stats.items(), key=lambda x: -x[1]["count"])

    award_items = sorted(award_counts.items(), key=lambda x: -_aval(x[0]))[:8]
    aw_rows = len(award_items)
    card_rows = len(card_items)
    wk_rows = math.ceil(len(weekly_items) / 2)
    detail_rows = min(len(all_records), 15)

    h = 240 + 268 + 30 + 84 * wk_rows + 60 + 34 * aw_rows + 60 + 34 * card_rows + 60 + 28 * detail_rows + 120

    canvas = get_nte_bg(W, h, bg="bg3")
    d = ImageDraw.Draw(canvas)

    # ── 标题（深色横幅，与角色面板一致）──
    title_h = 180
    title_img = get_nte_title_bg(W, title_h)
    canvas.paste(title_img, (0, 0), title_img)
    d.text((M, 36), "猫亭刮刮乐", fill=(255, 255, 255), font=F36)
    avatar = _load_avatar(64)
    if avatar:
        tw = int(F36.getlength("猫亭刮刮乐"))
        canvas.paste(avatar, (M + tw + 16, 28), avatar)
    d.text((M, 86), "午夜猫刊亭刮刮乐数据统计", fill=(200, 210, 220), font=F16)
    d.text((M, 114), f"更新于 {last_updated} · 角色 {role_id}", fill=(170, 180, 190), font=F14)
    if total_cnt:
        d.text((M, 140), f"共 {total_cnt} 条记录 · {len(dates_all)} 天", fill=(170, 180, 190), font=F13)

    y = title_h + 20

    # ── 概况 ──
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
        x = M + c * (cw + 12)
        yy = y + r * 86
        draw_card(d, (x, yy, x + cw, yy + 78), radius=16, fill=CARD)
        d.text((x + 18, yy + 12), lb, fill=MUTED, font=F14)
        d.text((x + 18, yy + 40), val, fill=clr, font=F30)
        if unit:
            d.text((x + 18 + F30.getlength(val) + 4, yy + 44), unit, fill=DIM, font=F13)
    y += 258 + 10

    # ── 每周趋势 ──
    d.text((M, y), "趋势（按周）", fill=TEXT, font=F20)
    y += 32
    _line(d, y)
    y += 10
    for idx, (wk, st) in enumerate(weekly_items):
        c, r = idx % 2, idx // 2
        x = M + c * (cw + 12)
        yy = y + r * 84
        draw_card(d, (x, yy, x + cw, yy + 76), radius=12, fill=CARD)
        sp = st["count"] * 10000
        pft = st["income"] - sp
        rt = st["income"] / sp * 100 if sp else None
        d.text((x + 14, yy + 10), f"{st['start']} ~ {st['end']}", fill=MUTED, font=F13)
        d.text((x + 14, yy + 34), f"盈亏: {pft:+,}", fill=GREEN if pft >= 0 else RED, font=F18)
        if rt is not None:
            d.text((x + 14, yy + 56), f"{st['count']}次 · 回报率 {rt:.1f}%", fill=MUTED, font=F13)
        else:
            d.text((x + 14, yy + 56), f"{st['count']}次", fill=MUTED, font=F13)
    y += (len(weekly_items) // 2 + len(weekly_items) % 2) * 84 + 10

    # ── 奖励分布 ──
    d.text((M, y), "奖励分布", fill=TEXT, font=F20)
    y += 32
    _line(d, y)
    y += 8
    SD.rr(d, (M, y, W - M, y + 30), 8, (220, 218, 210))
    d.text((M + 20, y + 6), "奖励", fill=TEXT, font=F14)
    d.text((M + 280, y + 6), "次数", fill=TEXT, font=F14)
    d.text((M + 360, y + 6), "总计金额", fill=TEXT, font=F14)
    d.text((M + 490, y + 6), "占比", fill=TEXT, font=F14)
    y += 34
    for idx, (aw, cnt) in enumerate(award_items):
        bg2 = CARD if idx % 2 == 0 else CARD_ALT
        SD.rr(d, (M, y, W - M, y + 28), 6, bg2)
        clr = _ac(aw)
        lb = aw if aw else "未中奖"
        v = _aval(aw)
        tv = v * cnt
        pct = cnt / total_cnt * 100 if total_cnt else 0
        SD.rr(d, (M + 14, y + 7, M + 26, y + 21), 4, clr)
        d.text((M + 34, y + 5), lb, fill=TEXT, font=F13)
        d.text((M + 280, y + 5), str(cnt), fill=clr, font=F13)
        d.text((M + 360, y + 5), f"{tv:,}" if tv else "", fill=MUTED, font=F13)
        d.text((M + 490, y + 5), f"{pct:.1f}%", fill=MUTED, font=F13)
        y += 30
    y += 10

    # ── 各刮刮卡统计 ──
    d.text((M, y), "各刮刮卡统计", fill=TEXT, font=F20)
    y += 32
    _line(d, y)
    y += 8
    SD.rr(d, (M, y, W - M, y + 30), 8, (220, 218, 210))
    d.text((M + 20, y + 6), "刮刮卡", fill=TEXT, font=F14)
    d.text((M + 200, y + 6), "次数", fill=TEXT, font=F14)
    d.text((M + 280, y + 6), "中奖次数", fill=TEXT, font=F14)
    d.text((M + 390, y + 6), "中奖金额", fill=TEXT, font=F14)
    d.text((M + 530, y + 6), "净盈亏", fill=TEXT, font=F14)
    y += 34
    for idx, (cid, st) in enumerate(card_items):
        bg2 = CARD if idx % 2 == 0 else CARD_ALT
        SD.rr(d, (M, y, W - M, y + 28), 6, bg2)
        sp = st["count"] * 10000
        pft = st["award_sum"] - sp
        d.text((M + 14, y + 5), cid, fill=TEXT, font=F13)
        d.text((M + 200, y + 5), str(st["count"]), fill=TEXT, font=F13)
        d.text((M + 280, y + 5), str(st["award_count"]), fill=MUTED, font=F13)
        d.text((M + 390, y + 5), f"{st['award_sum']:,}", fill=GREEN, font=F13)
        d.text((M + 530, y + 5), f"{pft:+,}", fill=GREEN if pft >= 0 else RED, font=F13)
        y += 30
    y += 10

    # ── 最近明细 ──
    d.text((M, y), "最近明细", fill=TEXT, font=F20)
    y += 32
    _line(d, y)
    y += 8
    records_sorted = sorted(all_records, key=lambda r: r.get("logTime", ""), reverse=True)
    for idx, rec in enumerate(records_sorted[:15]):
        bg2 = CARD if idx % 2 == 0 else CARD_ALT
        SD.rr(d, (M, y, W - M, y + 24), 6, bg2)
        lt = rec.get("logTime", "") or ""
        cn = _sc(rec.get("scratchCardId", "") or "")
        aw = rec.get("award", "") or "未中奖"
        d.text((M + 14, y + 3), lt, fill=MUTED, font=F13)
        d.text((M + 160, y + 3), cn, fill=MUTED, font=F13)
        d.text((W - 220, y + 3), aw, fill=_ac(rec.get("award", "")), font=F13)
        y += 25
    if len(records_sorted) > 15:
        d.text((M + 14, y + 3), f"... 共 {len(records_sorted)} 条记录", fill=MUTED, font=F13)

    canvas = canvas.crop((0, 0, W, max(y + 10, title_h)))
    return await convert_img(canvas)


# ── 今日统计图 ──

async def draw_scratch_today(user_id: str, bot_id: str) -> bytes | str:
    from ..utils.database import NTEKfCookie
    row = await NTEKfCookie.get_by_user(user_id, bot_id)
    if row is None or not row.cookie or not row.uid:
        return "你还没有绑定刮刮乐 ck！请【私聊】添加刮刮乐ck"
    from .scratch_service import fetch_today_data
    try:
        today = await fetch_today_data(row.cookie, row.uid)
    except Exception as e:
        logger.exception(f"[刮刮乐] 今日查询失败: {e}")
        return f"今日数据查询失败：{e}"
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

    h = 200 + 30 + min(len(award_items), 6) * 30 + 30 + len(records) * 30 + 60 + 60

    canvas = get_nte_bg(W, h, bg="bg3")
    d = ImageDraw.Draw(canvas)

    # ── 标题（深色横幅，与角色面板一致）──
    title_h = 160
    title_img = get_nte_title_bg(W, title_h)
    canvas.paste(title_img, (0, 0), title_img)
    d.text((M, 30), "今日刮刮乐", fill=(255, 255, 255), font=F36)
    avatar = _load_avatar(60)
    if avatar:
        tw = int(F36.getlength("今日刮刮乐"))
        canvas.paste(avatar, (M + tw + 14, 26), avatar)
    _tt = M + tw + 80 if avatar else M + 220
    d.rounded_rectangle([_tt, 34, _tt + 80, 58], 12, fill=(60, 70, 100))
    d.text((_tt + 10, 37), today_str, fill=GOLD, font=F16)
    d.text((M, 80), "午夜猫刊亭刮刮乐数据统计", fill=(200, 210, 220), font=F16)
    d.text((M, 108), f"今日刮了 {len(records)} 次", fill=(170, 180, 190), font=F13)
    y = title_h + 20

    # ── 三列卡片 ──
    cw = (W - 80) // 3
    for i, (lb, val, clr, unit) in enumerate([
        ("消费", f"{spent:,}", MUTED, "方斯"),
        ("收入", f"{income:,}", GREEN, "方斯"),
        ("盈亏", f"{profit:+,}", GREEN if profit >= 0 else RED, "方斯"),
    ]):
        x = M + i * (cw + 12)
        draw_card(d, (x, y, x + cw, y + 76), radius=14, fill=CARD)
        cx = x + cw // 2
        d.text((cx, y + 10), lb, fill=MUTED, font=F14, anchor="mt")
        d.text((cx, y + 34), val, fill=clr, font=F28, anchor="mt")
        d.text((cx, y + 60), unit, fill=DIM, font=F12, anchor="mt")
    SD.rr(d, (M, y + 84, 200, y + 84 + 34), 10, (230, 228, 220))
    d.text((M + 12, y + 89), f"回报率 {rate:.2f}%" if rate else "回报率 N/A", fill=GOLD, font=F16)
    y += 138

    # ── 奖励分布 ──
    if award_items:
        SD.rr(d, (M, y, W - M, y + 30), 8, (220, 218, 210))
        d.text((M + 14, y + 6), "奖励", fill=TEXT, font=F14)
        d.text((M + 200, y + 6), "次数", fill=TEXT, font=F14)
        d.text((M + 280, y + 6), "金额", fill=TEXT, font=F14)
        d.text((M + 400, y + 6), "小计", fill=TEXT, font=F14)
        y += 34
        for idx, (aw, cnt) in enumerate(award_items):
            bg2 = CARD if idx % 2 == 0 else CARD_ALT
            SD.rr(d, (M, y, W - M, y + 26), 6, bg2)
            v = _aval(aw)
            tv = v * cnt
            clr = PURPLE if v >= 20000 else GREEN if v >= 10000 else MUTED
            lb = aw if aw else "未中奖"
            SD.rr(d, (M + 12, y + 6, M + 24, y + 20), 4, clr)
            d.text((M + 30, y + 4), lb, fill=TEXT, font=F13)
            d.text((M + 200, y + 4), str(cnt), fill=clr, font=F13)
            d.text((M + 280, y + 4), f"{v:,}" if v else "", fill=MUTED, font=F13)
            d.text((M + 400, y + 4), f"{tv:,}" if tv else "", fill=clr, font=F13)
            y += 28
        y += 6

    # ── 今日记录 ──
    SD.rr(d, (M, y, W - M, y + 30), 8, (220, 218, 210))
    d.text((M + 14, y + 6), "时间", fill=TEXT, font=F14)
    d.text((M + 200, y + 6), "奖励", fill=TEXT, font=F14)
    y += 34
    for idx, r in enumerate(records):
        bg2 = CARD if idx % 2 == 0 else CARD_ALT
        SD.rr(d, (M, y, W - M, y + 26), 6, bg2)
        aw = r.get("award", "") or "未中奖"
        clr = GREEN if aw != "未中奖" else MUTED
        d.text((M + 14, y + 4), (r.get("logTime") or "")[-8:], fill=MUTED, font=F13)
        d.text((M + 200, y + 4), aw, fill=clr, font=F13)
        d.text((W - 50, y + 4), "✓" if aw != "未中奖" else "✗", fill=GREEN if aw != "未中奖" else RED, font=F15)
        y += 28

    canvas = canvas.crop((0, 0, W, y + 10))
    return await convert_img(canvas)
