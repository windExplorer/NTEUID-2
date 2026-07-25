"""刮刮乐统计图渲染。
渲染函数直接来自 _test_scratch_card.py / _test_scratch_today.py，保持完全一致。
"""
from __future__ import annotations

import json, re, math, random
from pathlib import Path
from datetime import datetime, timedelta, timezone
from collections import OrderedDict

from PIL import Image, ImageDraw, ImageFont

from gsuid_core.logger import logger

TZ_BJ = timezone(timedelta(hours=8))
_TEX = Path(__file__).resolve().parent.parent / "utils" / "texture2d"


def _apply_bg(img: Image.Image, bg: str = "bg") -> Image.Image:
    """叠加背景贴图。"""
    try:
        bg_img = Image.open(_TEX / f"{bg}.jpg").convert("RGBA").resize(img.size, Image.LANCZOS)
        img = Image.alpha_composite(bg_img, img)
    except Exception:
        pass
    return img

# ── 字体 ──
_FONT_CACHE: dict[int, ImageFont.FreeTypeFont] = {}

def _f(size: int) -> ImageFont.FreeTypeFont:
    if size not in _FONT_CACHE:
        candidates = [
            Path(__file__).resolve().parent.parent / "utils" / "fonts" / "nte_fonts.ttf",
            Path(r"C:\Windows\Fonts\msyh.ttc"),
            Path(r"C:\Windows\Fonts\simhei.ttf"),
        ]
        for p in candidates:
            if p.exists():
                _FONT_CACHE[size] = ImageFont.truetype(str(p), size, encoding="utf-8")
                break
        else:
            _FONT_CACHE[size] = ImageFont.load_default()
    return _FONT_CACHE[size]

F12 = _f(12); F13 = _f(13); F14 = _f(14); F15 = _f(15); F16 = _f(16)
F18 = _f(18); F20 = _f(22); F24 = _f(24); F28 = _f(28); F30 = _f(30); F36 = _f(36)

# ── 颜色 ──
BG = (28, 28, 36)
CARD_BG = (38, 38, 46)
CARD_ALT = (44, 44, 52)
TEXT = (220, 220, 230)
MUTED = (150, 150, 160)
DIM = (120, 120, 130)
GOLD = (245, 158, 11)
GREEN = (16, 185, 129)
RED = (239, 68, 68)
PURPLE = (200, 160, 255)
YELLOW_BRIGHT = (255, 184, 0)

W = 860
M = 28

# ── 工具 ──

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
    d.rectangle([M, y, W - M, y + 1], fill=(50, 50, 58))

def _load_avatar(size=56):
    """随机加载角色头像，圆形裁剪。"""
    res = Path(__file__).resolve().parent.parent / "resource"
    files = sorted((res / "char" / "avatar").rglob("player_*_256.png")) if (res / "char" / "avatar").exists() else []
    try:
        path = random.choice(files) if files else (res.parent / "ICON.png")
        img = Image.open(path).convert("RGBA").resize((size, size), Image.LANCZOS)
        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).ellipse([0, 0, size, size], fill=255)
        rgba = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        rgba.paste(img, (0, 0), mask)
        return rgba
    except Exception:
        return None

# ── 总计统计图 ──

def _render_stats_image(summary: dict, last_updated: str, role_id: str) -> Image.Image:
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

    # 按周
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

    # 刮刮卡统计
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

    h = 340 + 268 + 30 + 84 * wk_rows + 60 + 34 * aw_rows + 60 + 34 * card_rows + 60 + 28 * detail_rows + 120

    img = Image.new("RGBA", (W, h), BG)
    img = _apply_bg(img)
    d = ImageDraw.Draw(img)
    # ── 标题 ──
    d.rectangle([0, 0, W, 200], fill=(20, 20, 26))
    d.text((M, 50), "猫亭刮刮乐", fill=(255, 255, 255), font=F36)
    # 标题后面角色头像
    avatar = _load_avatar(56)
    if avatar:
        tw = int(F36.getlength("猫亭刮刮乐"))
        img.paste(avatar, (M + tw + 16, 42), avatar)
    d.text((M, 100), "午夜猫刊亭刮刮乐数据统计", fill=MUTED, font=F16)
    d.text((M, 130), f"更新于 {last_updated} · 角色 {role_id}", fill=DIM, font=F14)
    d.rectangle([M, 160, M + 60, 162], fill=GOLD)
    y = 220

    # ── 概况 6 宫格 ──
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
        SD.rr(d, (x, yy, x + cw, yy + 78), 16, CARD_BG)
        d.text((x + 16, yy + 12), lb, fill=MUTED, font=F15)
        d.text((x + 16, yy + 42), val, fill=clr, font=F30)
        if unit:
            d.text((x + 16 + F30.getlength(val) + 4, yy + 46), unit, fill=DIM, font=F14)
    y += 258 + 10

    # ── 趋势（按周）──
    d.text((M, y), "趋势（按周）", fill=TEXT, font=F20)
    y += 32
    _line(d, y)
    y += 10
    for idx, (wk, st) in enumerate(weekly_items):
        c, r = idx % 2, idx // 2
        x = M + c * (cw + 12)
        yy = y + r * 84
        SD.rr(d, (x, yy, x + cw, yy + 76), 12, CARD_BG)
        spent = st["count"] * 10000
        profit = st["income"] - spent
        rt = st["income"] / spent * 100 if spent else None
        d.text((x + 14, yy + 10), f"{st['start']} ~ {st['end']}", fill=MUTED, font=F13)
        d.text((x + 14, yy + 34), f"盈亏: {profit:+,}", fill=GREEN if profit >= 0 else RED, font=F18)
        if rt is not None:
            d.text((x + 14, yy + 56), f"{st['count']}次 · 回报率 {rt:.1f}%", fill=MUTED, font=F14)
        else:
            d.text((x + 14, yy + 56), f"{st['count']}次", fill=MUTED, font=F14)
    y += (len(weekly_items) // 2 + len(weekly_items) % 2) * 84 + 10

    # ── 奖励分布 ──
    d.text((M, y), "奖励分布", fill=TEXT, font=F20)
    y += 32
    _line(d, y)
    y += 8
    SD.rr(d, (M, y, W - M, y + 30), 8, (48, 48, 56))
    d.text((M + 20, y + 6), "奖励", fill=TEXT, font=F15)
    d.text((M + 280, y + 6), "次数", fill=TEXT, font=F15)
    d.text((M + 360, y + 6), "总计金额", fill=TEXT, font=F15)
    d.text((M + 490, y + 6), "占比", fill=TEXT, font=F15)
    y += 34
    for idx, (aw, cnt) in enumerate(award_items):
        bg2 = CARD_BG if idx % 2 == 0 else CARD_ALT
        SD.rr(d, (M, y, W - M, y + 28), 6, bg2)
        clr = _ac(aw)
        lb = aw if aw else "未中奖"
        v = _aval(aw)
        tv = v * cnt
        pct = cnt / total_cnt * 100 if total_cnt else 0
        SD.rr(d, (M + 14, y + 7, M + 26, y + 21), 4, clr)
        d.text((M + 34, y + 5), lb, fill=TEXT, font=F14)
        d.text((M + 280, y + 5), str(cnt), fill=clr, font=F14)
        d.text((M + 360, y + 5), f"{tv:,}" if tv else "", fill=MUTED, font=F14)
        d.text((M + 490, y + 5), f"{pct:.1f}%", fill=MUTED, font=F14)
        y += 30
    y += 10

    # ── 各刮刮卡统计 ──
    d.text((M, y), "各刮刮卡统计", fill=TEXT, font=F20)
    y += 32
    _line(d, y)
    y += 8
    SD.rr(d, (M, y, W - M, y + 30), 8, (48, 48, 56))
    d.text((M + 20, y + 6), "刮刮卡", fill=TEXT, font=F15)
    d.text((M + 200, y + 6), "次数", fill=TEXT, font=F15)
    d.text((M + 280, y + 6), "中奖次数", fill=TEXT, font=F15)
    d.text((M + 390, y + 6), "中奖金额", fill=TEXT, font=F15)
    d.text((M + 530, y + 6), "净盈亏", fill=TEXT, font=F15)
    y += 34
    for idx, (cid, st) in enumerate(card_items):
        bg2 = CARD_BG if idx % 2 == 0 else CARD_ALT
        SD.rr(d, (M, y, W - M, y + 28), 6, bg2)
        spent = st["count"] * 10000
        profit = st["award_sum"] - spent
        d.text((M + 14, y + 5), cid, fill=TEXT, font=F14)
        d.text((M + 200, y + 5), str(st["count"]), fill=TEXT, font=F14)
        d.text((M + 280, y + 5), str(st["award_count"]), fill=MUTED, font=F14)
        d.text((M + 390, y + 5), f"{st['award_sum']:,}", fill=GREEN, font=F14)
        d.text((M + 530, y + 5), f"{profit:+,}", fill=GREEN if profit >= 0 else RED, font=F14)
        y += 30
    y += 10

    # ── 最近明细 ──
    d.text((M, y), "最近明细", fill=TEXT, font=F20)
    y += 32
    _line(d, y)
    y += 8
    records_sorted = sorted(all_records, key=lambda r: r.get("logTime", ""), reverse=True)
    for idx, rec in enumerate(records_sorted[:15]):
        bg2 = CARD_BG if idx % 2 == 0 else CARD_ALT
        SD.rr(d, (M, y, W - M, y + 24), 6, bg2)
        lt = rec.get("logTime", "") or ""
        cn = _sc(rec.get("scratchCardId", "") or "")
        aw = rec.get("award", "") or "未中奖"
        d.text((M + 14, y + 4), lt, fill=DIM, font=F13)
        d.text((M + 160, y + 4), cn, fill=MUTED, font=F13)
        d.text((W - 220, y + 4), aw, fill=_ac(rec.get("award", "")), font=F13)
        y += 25
    if len(records_sorted) > 15:
        d.text((M + 14, y + 4), f"... 共 {len(records_sorted)} 条记录", fill=DIM, font=F14)
        y += 28

    y += 30
    d.rectangle([0, y, W, y + 60], fill=(20, 20, 26))
    d.text((M, y + 22), "NTEUID · 一切正常，就是异常。", fill=DIM, font=F14)
    y += 60

    img = img.crop((0, 0, W, y))
    return img


# ── 今日统计图 ──

def _render_today_image(today: dict, today_str: str) -> Image.Image:
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

    h = 240 + 30 + min(len(award_items), 6) * 30 + 30 + len(records) * 30 + 60 + 60

    img = Image.new("RGBA", (W - 100, h), BG)
    img = _apply_bg(img)
    d = ImageDraw.Draw(img)
    # ── 标题 ──
    d.rectangle([0, 0, img.width, 170], fill=(20, 20, 26))
    d.text((M, 28), f"今日刮刮乐", fill=(255, 255, 255), font=F36)
    avatar = _load_avatar(50)
    if avatar:
        tw = int(F36.getlength("今日刮刮乐"))
        img.paste(avatar, (M + tw + 14, 24), avatar)
    # 日期标签
    SD.rr(d, (M + tw + 74, 30, M + tw + 154, 54), 12, (42, 42, 52))
    d.text((M + tw + 84, 33), today_str, fill=GOLD, font=F18)
    d.text((M, 82), f"今日刮刮乐数据", fill=MUTED, font=F16)
    d.rectangle([M, 120, M + 60, 122], fill=GOLD)
    y = 150

    # ── 三列卡片 ──
    cw = (img.width - 80) // 3
    for i, (lb, val, clr, unit) in enumerate([
        ("消费", f"{spent:,}", MUTED, "方斯"),
        ("收入", f"{income:,}", GREEN, "方斯"),
        ("盈亏", f"{profit:+,}", GREEN if profit >= 0 else RED, "方斯"),
    ]):
        x = M + i * (cw + 12)
        yy = y
        SD.rr(d, (x, yy, x + cw, yy + 76), 14, CARD_BG)
        cx = x + cw // 2
        d.text((cx, yy + 10), lb, fill=MUTED, font=F14, anchor="mt")
        d.text((cx, yy + 34), val, fill=clr, font=F28, anchor="mt")
        d.text((cx, yy + 60), unit, fill=DIM, font=F12, anchor="mt")
    SD.rr(d, (M, y + 84, 200, y + 84 + 34), 10, (42, 50, 60))
    d.text((M + 12, y + 89), f"回报率 {rate:.2f}%" if rate else "回报率 N/A", fill=GOLD, font=F16)
    y += 138

    # ── 奖励分布 ──
    if award_items:
        SD.rr(d, (M, y, img.width - M, y + 30), 8, (48, 48, 56))
        d.text((M + 14, y + 6), "奖励", fill=MUTED, font=F14)
        d.text((M + 200, y + 6), "次数", fill=MUTED, font=F14)
        d.text((M + 280, y + 6), "金额", fill=MUTED, font=F14)
        d.text((M + 400, y + 6), "小计", fill=MUTED, font=F14)
        y += 34
        for idx, (aw, cnt) in enumerate(award_items):
            bg2 = CARD_BG if idx % 2 == 0 else CARD_ALT
            SD.rr(d, (M, y, img.width - M, y + 26), 6, bg2)
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
    SD.rr(d, (M, y, img.width - M, y + 30), 8, (48, 48, 56))
    d.text((M + 14, y + 6), "时间", fill=MUTED, font=F14)
    d.text((M + 200, y + 6), "奖励", fill=MUTED, font=F14)
    y += 34
    for idx, r in enumerate(records):
        bg2 = CARD_BG if idx % 2 == 0 else CARD_ALT
        SD.rr(d, (M, y, img.width - M, y + 26), 6, bg2)
        aw = r.get("award", "") or "未中奖"
        clr = GREEN if aw != "未中奖" else MUTED
        d.text((M + 14, y + 4), (r.get("logTime") or "")[-8:], fill=DIM, font=F13)
        d.text((M + 200, y + 4), aw, fill=clr, font=F13)
        d.text((img.width - 50, y + 4), "✓" if aw != "未中奖" else "✗", fill=GREEN if aw != "未中奖" else RED, font=F15)
        y += 28

    y += 20
    d.rectangle([0, y, img.width, y + 50], fill=(20, 20, 26))
    d.text((M, y + 16), "NTEUID · 一切正常，就是异常。", fill=DIM, font=F13)
    y += 50

    img = img.crop((0, 0, img.width, y))
    return img


# ── 公开 async 接口 ──


async def draw_scratch_stats(user_id: str, bot_id: str) -> Image.Image | str:
    from ..utils.database import NTEKfCookie
    row = await NTEKfCookie.get_by_user(user_id, bot_id)
    if row is None or not row.raw_data or row.raw_data == "{}":
        return "暂无刮刮乐数据，请先去私聊【添加刮刮乐ck】"
    s = json.loads(row.raw_data)
    return _render_stats_image(s, row.last_updated, row.uid)


async def draw_scratch_today(user_id: str, bot_id: str) -> Image.Image | str:
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
    ts = datetime.now(TZ_BJ).strftime("%Y-%m-%d")
    return _render_today_image(today, ts)
