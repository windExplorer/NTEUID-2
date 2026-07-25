"""刮刮乐统计图渲染"""
from __future__ import annotations

import json, re, math, random
from pathlib import Path
from datetime import datetime, timedelta, timezone

from PIL import Image, ImageDraw

from gsuid_core.logger import logger
from gsuid_core.utils.image.convert import convert_img

from ..utils.image import get_nte_bg, draw_card

TZ_BJ = timezone(timedelta(hours=8))
W = 760
W_TODAY = 680
M = 20


def _f(size: int):
    from ..utils.fonts.nte_fonts import nte_font_bold
    return nte_font_bold(size)

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

    _MAX_H = 3000
    canvas = get_nte_bg(W, _MAX_H, bg="bg3")
    _overlay = Image.new("RGBA", (W, _MAX_H), (20, 22, 28, 120))
    canvas.paste(_overlay, (0, 0), _overlay)
    d = ImageDraw.Draw(canvas)

    # 标题（半透明背景让 bg3 透出）
    _title_overlay = Image.new("RGBA", (W, 170), (30, 32, 40, 180))
    canvas.paste(_title_overlay, (0, 0), _title_overlay)
    d.rectangle([M, 168, M + 60, 170], fill=(80, 140, 210))
    d.text((M, 30), "猫亭刮刮乐", fill=(255, 255, 255), font=F36)
    avatar = _load_avatar(60)
    if avatar:
        tw = int(F36.getlength("猫亭刮刮乐"))
        canvas.paste(avatar, (M + tw + 14, 24), avatar)
    d.text((M, 80), "午夜猫刊亭刮刮乐数据统计", fill=(170, 178, 190), font=F16)
    d.text((M, 108), f"更新于 {last_updated} · 角色 {role_id}", fill=(130, 138, 150), font=F14)
    if total_cnt:
        d.text((M, 135), f"共 {total_cnt} 条记录 · {len(dates_all)} 天", fill=(130, 138, 150), font=F13)
    y = 190

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
    for idx, (wk, st) in enumerate(weekly_items):
        c, r = idx % 2, idx // 2
        x = M + c * (cw + 14)
        yy = y + r * 96
        draw_card(d, (x, yy, x + cw, yy + 78), radius=12, fill=CARD)
        sp = st["count"] * 10000
        pft = st["income"] - sp
        rt = st["income"] / sp * 100 if sp else None
        d.text((x + 16, yy + 12), f"{st['start']} ~ {st['end']}", fill=MUTED, font=F13)
        d.text((x + 16, yy + 38), f"盈亏: {pft:+,}", fill=GREEN if pft >= 0 else RED, font=F18)
        if rt is not None:
            d.text((x + 16, yy + 58), f"{st['count']}次 · 回报率 {rt:.1f}%", fill=MUTED, font=F13)
        else:
            d.text((x + 16, yy + 58), f"{st['count']}次", fill=MUTED, font=F13)
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
    d.text((M + 280, y + 6), "中奖次数", fill=TEXT, font=F14)
    d.text((M + 390, y + 6), "中奖金额", fill=TEXT, font=F14)
    d.text((M + 530, y + 6), "净盈亏", fill=TEXT, font=F14)
    y += 34
    for idx, (cid, st) in enumerate(card_items):
        bg2 = CARD if idx % 2 == 0 else CARD_ALT
        SD.rr(d, (M, y, W - M, y + 36), 8, bg2)
        sp = st["count"] * 10000
        pft = st["award_sum"] - sp
        d.text((M + 14, y + 8), cid, fill=TEXT, font=F13)
        d.text((M + 200, y + 8), str(st["count"]), fill=TEXT, font=F13)
        d.text((M + 280, y + 8), str(st["award_count"]), fill=MUTED, font=F13)
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

    canvas = canvas.crop((0, 0, W, y))
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
    canvas = get_nte_bg(W_TODAY, _MAX_H, bg="bg3")
    _overlay = Image.new("RGBA", (W_TODAY, _MAX_H), (20, 22, 28, 120))
    canvas.paste(_overlay, (0, 0), _overlay)
    d = ImageDraw.Draw(canvas)

    # 标题（半透明背景让 bg3 透出）
    _title_overlay = Image.new("RGBA", (W_TODAY, 160), (30, 32, 40, 180))
    canvas.paste(_title_overlay, (0, 0), _title_overlay)
    d.rectangle([M, 158, M + 60, 160], fill=(80, 140, 210))
    d.text((M, 28), "今日刮刮乐", fill=(255, 255, 255), font=F36)
    avatar = _load_avatar(56)
    if avatar:
        tw = int(F36.getlength("今日刮刮乐"))
        canvas.paste(avatar, (M + tw + 14, 24), avatar)
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

    canvas = canvas.crop((0, 0, W_TODAY, y))
    return await convert_img(canvas)


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
            av = av.resize((30, 30), Image.LANCZOS)
            mask = Image.new("L", (30, 30), 0)
            ImageDraw.Draw(mask).ellipse([0, 0, 30, 30], fill=255)
            av_rgba = Image.new("RGBA", (30, 30), (0, 0, 0, 0))
            av_rgba.paste(av, (0, 0), mask)
            user_avatars[row.user_id] = av_rgba
        except Exception:
            pass

    _MAX_H = 2000
    rank_w = 700
    canvas = get_nte_bg(rank_w, _MAX_H, bg="bg3")
    _overlay = Image.new("RGBA", (rank_w, _MAX_H), (20, 22, 28, 120))
    canvas.paste(_overlay, (0, 0), _overlay)
    d = ImageDraw.Draw(canvas)

    # 标题
    _title = Image.new("RGBA", (rank_w, 120), (30, 32, 40, 180))
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
            canvas.paste(av, (66, y + 3), av)
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

    canvas = canvas.crop((0, 0, rank_w, y))
    return await convert_img(canvas)
