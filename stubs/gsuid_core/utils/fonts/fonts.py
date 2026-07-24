from pathlib import Path

from PIL import ImageFont

# stubs/gsuid_core/utils/fonts/fonts.py -> parents[4] 即项目根
_FONT_DIR = Path(__file__).resolve().parents[4] / "NTEUID" / "utils" / "fonts"

# 优先用系统中文字体，保证卡片中文可读；回退到项目自带字体，再回退到默认点阵。
_SYSTEM_FONTS = [
    Path(r"C:/Windows/Fonts/msyh.ttc"),
    Path(r"C:/Windows/Fonts/msyh.ttf"),
    _FONT_DIR / "nte_fonts.ttf",
]


def core_font(size: int, *args, **kwargs) -> ImageFont.ImageFont:
    for f in _SYSTEM_FONTS:
        if f.exists():
            try:
                return ImageFont.truetype(str(f), size)
            except Exception:
                continue
    return ImageFont.load_default()
