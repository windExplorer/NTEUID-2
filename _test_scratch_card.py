"""刮刮乐统计图渲染测试（纯 PIL，与 scratch_card.py 逻辑一致）"""
import json, re, math, random, os
from pathlib import Path
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).parent
# 数据目录 / 输出路径可通过环境变量覆盖，便于对比不同账号的数据
DATA_DIR = Path(os.environ.get("SCRATCH_DATA_DIR", str(ROOT / "cat" / "data")))
OUT = Path(os.environ.get("SCRATCH_OUT", str(ROOT / "test_result" / "scratch_stats.png")))

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

TEXT2D = ROOT / "NTEUID" / "utils" / "texture2d"

def _ringed_avatar(size=96, src=None):
    """圆形头像 + 白色描边环（面板图同款：头像圆直径小于块，四周留白边距）"""
    av = src if isinstance(src, Image.Image) else _load_avatar(size)
    if av is None:
        return None
    # 头像圆直径明显小于块，四周留更大边距（用户要求间隙更大）
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
        outline=(255, 255, 255, 230), width=4,
    )
    base.alpha_composite(ring)
    return base

def _load_card_long_local():
    """面板图头部背景：随机一张 card_long 角色长图"""
    p = ROOT / "NTEUID" / "resource" / "common" / "card_long"
    files = sorted(p.rglob("*.png")) if p.exists() else []
    if not files:
        return Image.new("RGBA", (1100, 199), (40, 44, 52))
    return Image.open(random.choice(files)).convert("RGBA")

def _make_role_title_local(role_name, role_id, W, avatar=None):
    """复刻面板图 make_nte_role_title：card_long 横条背景(199高+下移8) + maskB 遮罩 + 环形头像 + 昵称 + UID"""
    H = int(216 * W / 1100)         # canvas 总高，头像占满
    BH = int(199 * W / 1100)        # banner 区域高度（原版 199，非 216）——决定圆角形状
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    # 1) card_long 横条背景（面板同款 1528×128 比例 + maskB 遮罩，下移 8）
    card = _load_card_long_local()
    card_long = card.resize((int(1528 * W / 1100), int(128 * W / 1100)), Image.LANCZOS)
    ox, oy = int(-428 * W / 1100), int(56 * W / 1100)
    banner_layer = Image.new("RGBA", (W, BH), (0, 0, 0, 0))
    banner_layer.paste(card_long, (ox, oy), card_long)
    maskB = Image.open(TEXT2D / "maskB.png").convert("RGBA").resize((W, BH), Image.LANCZOS)
    mb = maskB.split()[3].point(lambda a: 255 if a > 128 else 0)  # 二值化：立绘内部完全不透明，仅形状取 maskB
    banner = Image.new("RGBA", (W, BH), (0, 0, 0, 0))
    banner.paste(banner_layer, (0, 0), mask=mb)
    banner.putalpha(mb)  # 强制 banner alpha = 二值化 mask，避免 card_long 自身半透明导致整体发虚
    canvas.alpha_composite(banner, (0, int(8 * W / 1100)))
    # 2) 环形头像（四周留白边距，见 _ringed_avatar）
    av = _ringed_avatar(int(216 * W / 1100), src=avatar)
    if av is not None:
        canvas.alpha_composite(av, (0, 0))
    # 3) 昵称 + UID 文字（原版：昵称(240,98)，UID(240,145→下移8后绝对153)）
    tx = int(240 * W / 1100)
    d = ImageDraw.Draw(canvas)
    d.text((tx, int(98 * W / 1100)), role_name, fill=(255, 255, 255), font=F20, anchor="lm")
    if role_id:
        d.text((tx, int(153 * W / 1100)), f"UID {role_id}", fill=(236, 238, 242), font=F14, anchor="lm")
    return canvas

def _read_role_id():
    m = re.search(r"data(\d+)", str(DATA_DIR))
    suffix = m.group(1) if m else ""
    role_file = ROOT / "cat" / f"role{suffix}.txt"
    if not role_file.exists():
        role_file = ROOT / "cat" / "role.txt"
    if role_file.exists():
        return role_file.read_text("utf-8").strip().splitlines()[0].strip()
    return ""

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
summary = json.loads((DATA_DIR / "summary.json").read_text("utf-8"))
all_pages = []
for sl in summary.get("slices", []):
    sf = DATA_DIR / f"slice_{sl['key']}.json"
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
# 单张消耗按整数分摊：总消耗 // 总次数，余数逐条 +1 方斯
if total_cnt:
    _base_cost = ts // total_cnt
    _rem_cost = ts % total_cnt
    _cost_of = [_base_cost + (1 if i < _rem_cost else 0) for i in range(total_cnt)]
else:
    _cost_of = []
dates_all = sorted(set((r.get("logTime") or "")[:10] for r in all_records if r.get("logTime")))

# 趋势（按周）：直接复用官方切片的权威汇总，与 scratch_card.py 保持一致
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

# 画布
_MAX_H = 6000
canvas = _load_bg(W, _MAX_H)
overlay = Image.new("RGBA", (W, _MAX_H), (20, 22, 28, 120))
canvas.paste(overlay, (0, 0), overlay)
d = ImageDraw.Draw(canvas)

# 顶部用户信息（面板图同款：card_long 背景横条 + 环形头像 + 昵称 + UID）——仅本地预览，生产环境待确认后同步
role_id = _read_role_id()
header_img = _make_role_title_local("玩家", role_id, W, avatar=_load_avatar(140))
canvas.paste(header_img, (0, 0), header_img)
y = header_img.height + 14
d.text((M, y), "猫亭刮刮乐 · 午夜猫刊亭刮刮乐数据统计", fill=TEXT, font=F18)
d.text((M, y + 30), f"更新于 {summary.get('generated_at', 'N/A')} · 共 {total_cnt} 条记录 · {len(dates_all)} 天", fill=MUTED, font=F14)
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
for idx, st in enumerate(weekly_items):
    c, r = idx % 2, idx // 2
    x = M + c * (cw + 14)
    yy = y + r * 96
    _draw_card(d, (x, yy, x + cw, yy + 78), 12, CARD_FILL)
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
d.text((M + 280, y + 6), "中奖/未中", fill=TEXT, font=F14)
d.text((M + 390, y + 6), "中奖金额", fill=TEXT, font=F14)
d.text((M + 530, y + 6), "净盈亏", fill=TEXT, font=F14)
y += 34
for idx, (cid, st) in enumerate(card_items):
    bg2 = CARD_FILL if idx % 2 == 0 else CARD_ALT
    _rr(d, (M, y, W - M, y + 36), 8, bg2)
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
