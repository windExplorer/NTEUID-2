"""今日刮刮乐卡片渲染测试（与 scratch_card.py 逻辑一致）"""
import re
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).parent
OUT = ROOT / "test_result" / "scratch_today.png"

def _f(size):
    candidates = [ROOT / "NTEUID" / "utils" / "fonts" / "nte_fonts.ttf", Path(r"C:\Windows\Fonts\msyh.ttc"), Path(r"C:\Windows\Fonts\simhei.ttf")]
    for p in candidates:
        if p.exists():
            return ImageFont.truetype(str(p), size, encoding="utf-8")
    return ImageFont.load_default()

F12 = _f(12); F13 = _f(13); F14 = _f(14); F15 = _f(15); F16 = _f(16)
F18 = _f(18); F20 = _f(20); F24 = _f(24); F28 = _f(28); F36 = _f(36)

CARD_FILL = (45, 48, 56)
CARD_ALT = (52, 55, 63)
TEXT = (230, 232, 236)
MUTED = (160, 165, 175)
DIM = (120, 125, 135)
GOLD = (255, 190, 50)
GREEN = (60, 200, 110)
RED = (240, 80, 80)
PURPLE = (180, 130, 255)
SHADOW_COLOR = (30, 32, 38)

W = 680
M = 20

def _rr(d, b, r, f):
    d.rounded_rectangle(b, r, fill=f)

def _draw_card(d, b, r, f):
    x1, y1, x2, y2 = b
    d.rounded_rectangle((x1, y1 + 8, x2, y2 + 8), r, fill=SHADOW_COLOR)
    d.rounded_rectangle(b, r, fill=f)

def _aval(aw):
    m = re.search(r"方斯\*(\d+)", aw)
    return int(m.group(1)) if m else 0

def _load_bg(w, h):
    try:
        return Image.open(ROOT / "NTEUID" / "utils" / "texture2d" / "bg3.jpg").convert("RGBA").resize((w, h), Image.LANCZOS)
    except:
        return Image.new("RGBA", (w, h), (28, 30, 36))

def _load_avatar(size=56):
    res_dir = ROOT / "NTEUID" / "resource"
    files = sorted((res_dir / "char" / "avatar").rglob("player_*_256.png")) if (res_dir / "char" / "avatar").exists() else []
    try:
        path = ROOT / "ICON.png"
        if files: path = __import__("random").choice(files)
        img = Image.open(path).convert("RGBA").resize((size, size), Image.LANCZOS)
        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).ellipse([0, 0, size, size], fill=255)
        rgba = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        rgba.paste(img, (0, 0), mask)
        return rgba
    except:
        return None

# Mock 今日数据
today_str = "2026-07-25"
records_mock = [
    {"logTime":"21:34:07","scratchCardId":"猫刊亭·异闻","award":"方斯*10000"},
    {"logTime":"21:33:21","scratchCardId":"猫刊亭·异闻","award":""},
    {"logTime":"21:32:32","scratchCardId":"猫刊亭·异闻","award":"方斯*10000"},
    {"logTime":"21:31:32","scratchCardId":"猫刊亭·密令","award":"方斯*10000"},
    {"logTime":"21:30:42","scratchCardId":"猫刊亭·密令","award":""},
    {"logTime":"21:29:33","scratchCardId":"猫刊亭·异闻","award":"方斯*20000"},
    {"logTime":"21:28:42","scratchCardId":"猫刊亭·异闻","award":"方斯*10000"},
    {"logTime":"21:27:44","scratchCardId":"猫刊亭·密令","award":""},
    {"logTime":"21:26:13","scratchCardId":"猫刊亭·异闻","award":"方斯*10000"},
    {"logTime":"21:24:46","scratchCardId":"猫刊亭·异闻","award":"方斯*10000"},
]
spent = len(records_mock) * 10000
income = sum(_aval(r.get("award","")) for r in records_mock)
profit = income - spent
rate = income / spent * 100 if spent else None

award_cnt = {}
for r in records_mock:
    aw = r.get("award") or ""
    award_cnt[aw] = award_cnt.get(aw, 0) + 1
award_items = sorted(award_cnt.items(), key=lambda x: -_aval(x[0]))[:6]

h = 250 + 30 + min(len(award_items), 6) * 44 + 30 + len(records_mock) * 34 + 60

max_h = 3000
canvas = _load_bg(W, max_h)
overlay = Image.new("RGBA", (W, max_h), (20, 22, 28, 120))
canvas.paste(overlay, (0, 0), overlay)
d = ImageDraw.Draw(canvas)

# 标题（半透明）
_title_overlay = Image.new("RGBA", (W, 160), (30, 32, 40, 180))
canvas.paste(_title_overlay, (0, 0), _title_overlay)
d.rectangle([M, 158, M + 60, 160], fill=(80, 140, 210))
d.text((M, 28), "今日刮刮乐", fill=(255, 255, 255), font=F36)
avatar = _load_avatar(56)
if avatar:
    tw = int(F36.getlength("今日刮刮乐"))
    canvas.paste(avatar, (M + tw + 14, 24), avatar)
tt = M + tw + 80 if avatar else M + 220
_rr(d, (tt, 34, tt + 80, 58), 12, (50, 54, 64))
d.text((tt + 10, 37), today_str, fill=GOLD, font=F16)
d.text((M, 80), "午夜猫刊亭刮刮乐数据统计", fill=(170, 178, 190), font=F16)
d.text((M, 108), f"今日刮了 {len(records_mock)} 次", fill=(130, 138, 150), font=F14)
y = 180

# 四宫格卡片
cw = (W - M * 2 - 14) // 2
for i, (lb, val, clr, unit) in enumerate([
    ("消费", f"{spent:,}", MUTED, "方斯"),
    ("收入", f"{income:,}", GREEN, "方斯"),
    ("盈亏", f"{profit:+,}", GREEN if profit >= 0 else RED, "方斯"),
    ("回报率", f"{rate:.2f}%" if rate else "N/A", GOLD, ""),
]):
    c, r = i % 2, i // 2
    x = M + c * (cw + 14)
    yy = y + r * 88
    _draw_card(d, (x, yy, x + cw, yy + 76), 14, CARD_FILL)
    cx = x + cw // 2
    d.text((cx, yy + 10), lb, fill=MUTED, font=F14, anchor="mt")
    d.text((cx, yy + 34), val, fill=clr, font=F28, anchor="mt")
    if unit:
        d.text((cx, yy + 58), unit, fill=DIM, font=F12, anchor="mt")
y += 176 + 30

# 奖励分布
if award_items:
    _rr(d, (M, y, W - M, y + 30), 8, (55, 58, 66))
    d.text((M + 14, y + 6), "奖励", fill=TEXT, font=F14)
    d.text((M + 200, y + 6), "次数", fill=TEXT, font=F14)
    d.text((M + 280, y + 6), "金额", fill=TEXT, font=F14)
    d.text((M + 400, y + 6), "小计", fill=TEXT, font=F14)
    y += 34
    for idx, (aw, cnt) in enumerate(award_items):
        bg2 = CARD_FILL if idx % 2 == 0 else CARD_ALT
        _rr(d, (M, y, W - M, y + 36), 8, bg2)
        v = _aval(aw)
        tv = v * cnt
        clr = PURPLE if v >= 20000 else GREEN if v >= 10000 else MUTED
        lb = aw if aw else "未中奖"
        _rr(d, (M + 12, y + 10, M + 24, y + 26), 4, clr)
        d.text((M + 30, y + 8), lb, fill=TEXT, font=F13)
        d.text((M + 200, y + 8), str(cnt), fill=clr, font=F13)
        d.text((M + 280, y + 8), f"{v:,}" if v else "", fill=MUTED, font=F13)
        d.text((M + 400, y + 8), f"{tv:,}" if tv else "", fill=clr, font=F13)
        y += 44
    y += 30

# 今日记录
_rr(d, (M, y, W - M, y + 30), 8, (55, 58, 66))
d.text((M + 14, y + 6), "时间", fill=TEXT, font=F14)
d.text((M + 110, y + 6), "卡名", fill=TEXT, font=F14)
d.text((M + 310, y + 6), "奖励", fill=TEXT, font=F14)
y += 34
for idx, r in enumerate(records_mock):
    bg2 = CARD_FILL if idx % 2 == 0 else CARD_ALT
    _rr(d, (M, y, W - M, y + 30), 8, bg2)
    tm = r.get("logTime","")[-8:]
    cn = (r.get("scratchCardId","") or "").replace("《","").replace("》","")
    aw = r.get("award","") or "未中奖"
    clr = GREEN if aw != "未中奖" else MUTED
    d.text((M + 14, y + 6), tm, fill=MUTED, font=F13)
    d.text((M + 110, y + 6), cn, fill=MUTED, font=F13)
    d.text((M + 310, y + 6), aw, fill=clr, font=F13)
    d.text((W - 50, y + 6), "✓" if aw != "未中奖" else "✗", fill=GREEN if aw != "未中奖" else RED, font=F15)
    y += 34

# 底部
y += 30
_rr(d, (0, y, W, y + 36), 0, (30, 32, 40))
d.text((M, y + 10), "NTEUID · 一切正常，就是异常。", fill=(100, 105, 115), font=F13)
y += 36

canvas = canvas.crop((0, 0, W, y))
canvas.save(OUT)
print(f"OK {OUT}  {canvas.width}x{canvas.height}")
