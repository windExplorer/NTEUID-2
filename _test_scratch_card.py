"""刮刮乐统计图渲染测试（纯 PIL，与 scratch_card.py 逻辑一致）"""
import json, re, math, random
from pathlib import Path
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).parent
OUT = ROOT / "test_result" / "scratch_stats.png"

def _f(size):
    candidates = [ROOT / "NTEUID" / "utils" / "fonts" / "nte_fonts.ttf", Path(r"C:\Windows\Fonts\msyh.ttc"), Path(r"C:\Windows\Fonts\simhei.ttf")]
    for p in candidates:
        if p.exists():
            return ImageFont.truetype(str(p), size, encoding="utf-8")
    return ImageFont.load_default()

F13 = _f(13); F14 = _f(14); F15 = _f(15); F16 = _f(16); F18 = _f(18)
F20 = _f(20); F24 = _f(24); F28 = _f(28); F30 = _f(30); F36 = _f(36)

CARD_FILL = (45, 48, 56)
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

W = 760
M = 22

def _rr(d, b, r, f):
    d.rounded_rectangle(b, r, fill=f)

def _draw_card(d, b, r, f):
    x1, y1, x2, y2 = b
    d.rounded_rectangle((x1, y1 + 8, x2, y2 + 8), r, fill=SHADOW_COLOR)
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

def _load_bg(w, h):
    try:
        return Image.open(ROOT / "NTEUID" / "utils" / "texture2d" / "bg3.jpg").convert("RGBA").resize((w, h), Image.LANCZOS)
    except:
        return Image.new("RGBA", (w, h), (28, 30, 36))

def _load_avatar(size=60):
    res_dir = ROOT / "NTEUID" / "resource"
    files = sorted((res_dir / "char" / "avatar").rglob("player_*_256.png")) if (res_dir / "char" / "avatar").exists() else []
    try:
        path = random.choice(files) if files else (ROOT / "ICON.png")
        img = Image.open(path).convert("RGBA").resize((size, size), Image.LANCZOS)
        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).ellipse([0, 0, size, size], fill=255)
        rgba = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        rgba.paste(img, (0, 0), mask)
        return rgba
    except:
        return None

# 读取数据
summary = json.loads((ROOT / "cat" / "data" / "summary.json").read_text("utf-8"))
all_pages = []
for sl in summary.get("slices", []):
    sf = ROOT / "cat" / "data" / f"slice_{sl['key']}.json"
    if sf.exists():
        sd = json.loads(sf.read_text("utf-8"))
        all_pages.extend(sd.get("pages", []))
summary["pages"] = all_pages

all_records = []
for raw in all_pages:
    try:
        r = (json.loads(raw).get("data") or {}).get("result") or []
        if isinstance(r, list): all_records.extend(r)
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

# 画布
_MAX_H = 3000
canvas = _load_bg(W, _MAX_H)
overlay = Image.new("RGBA", (W, _MAX_H), (20, 22, 28, 120))
canvas.paste(overlay, (0, 0), overlay)
d = ImageDraw.Draw(canvas)

# 标题（半透明）
_title_overlay = Image.new("RGBA", (W, 170), (30, 32, 40, 180))
canvas.paste(_title_overlay, (0, 0), _title_overlay)
d.rectangle([M, 168, M + 60, 170], fill=(80, 140, 210))
d.text((M, 30), "猫亭刮刮乐", fill=(255, 255, 255), font=F36)
avatar = _load_avatar(60)
if avatar:
    tw = int(F36.getlength("猫亭刮刮乐"))
    canvas.paste(avatar, (M + tw + 14, 24), avatar)
d.text((M, 80), "午夜猫刊亭刮刮乐数据统计", fill=(170, 178, 190), font=F16)
d.text((M, 108), "更新于 2026-07-25 03:40:56 · 角色 215020172015", fill=(130, 138, 150), font=F14)
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
    _draw_card(d, (x, yy, x + cw, yy + 82), 16, CARD_FILL)
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
    _draw_card(d, (x, yy, x + cw, yy + 78), 12, CARD_FILL)
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
_rr(d, (M, y, W - M, y + 30), 8, (55, 58, 66))
d.text((M + 20, y + 6), "奖励", fill=TEXT, font=F14)
d.text((M + 280, y + 6), "次数", fill=TEXT, font=F14)
d.text((M + 360, y + 6), "总计金额", fill=TEXT, font=F14)
d.text((M + 490, y + 6), "占比", fill=TEXT, font=F14)
y += 34
for idx, (aw, cnt) in enumerate(award_items):
    bg2 = CARD_FILL if idx % 2 == 0 else CARD_ALT
    _rr(d, (M, y, W - M, y + 36), 8, bg2)
    clr = _ac(aw)
    lb = aw if aw else "未中奖"
    v = _aval(aw)
    tv = v * cnt
    pct = cnt / total_cnt * 100 if total_cnt else 0
    _rr(d, (M + 14, y + 10, M + 26, y + 26), 4, clr)
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
_rr(d, (M, y, W - M, y + 30), 8, (55, 58, 66))
d.text((M + 20, y + 6), "刮刮卡", fill=TEXT, font=F14)
d.text((M + 200, y + 6), "次数", fill=TEXT, font=F14)
d.text((M + 280, y + 6), "中奖次数", fill=TEXT, font=F14)
d.text((M + 390, y + 6), "中奖金额", fill=TEXT, font=F14)
d.text((M + 530, y + 6), "净盈亏", fill=TEXT, font=F14)
y += 34
for idx, (cid, st) in enumerate(card_items):
    bg2 = CARD_FILL if idx % 2 == 0 else CARD_ALT
    _rr(d, (M, y, W - M, y + 36), 8, bg2)
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
    bg2 = CARD_FILL if idx % 2 == 0 else CARD_ALT
    _rr(d, (M, y, W - M, y + 30), 8, bg2)
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
_rr(d, (0, y, W, y + 36), 0, (30, 32, 40))
d.text((M, y + 10), "NTEUID · 一切正常，就是异常。", fill=(100, 105, 115), font=F13)
y += 36

canvas = canvas.crop((0, 0, W, y))
canvas.save(OUT)
print(f"OK {OUT}  {canvas.width}x{canvas.height}")
