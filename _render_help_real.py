"""用 gsuid_core 原生 get_new_help 渲染 NTEUID 帮助图（与线上一致）。

需把克隆的 gsuid_core 源码目录加入 sys.path。脚本只依赖：
  - 真实 gsuid_core（gsuid_core/ 子目录，已 gitignore）
  - PIL / numpy / msgspec / boltons（gsuid_core 运行所需）
"""
import asyncio
import json
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(r"x:\_WorkSpace\GitHub_Pro\NTEUID-2")
GS = ROOT / "gsuid_core"  # 此目录下含 gsuid_core/ 真实包
sys.path.insert(0, str(GS))

# ---- 读取 NTEUID 数据 ----
help_path = ROOT / "NTEUID" / "nte_help" / "help.json"
icon_path = ROOT / "ICON.png"
icon_path_dir = ROOT / "NTEUID" / "nte_help" / "icon_path"
data = json.loads(help_path.read_text(encoding="utf-8"))

ver = ""
for line in (ROOT / "NTEUID" / "version.py").read_text(encoding="utf-8").splitlines():
    if "NTEUID_version" in line:
        ver = line.split("=", 1)[1].strip().strip('"').strip("'")
        break

from gsuid_core.help.draw_new_plugin_help import get_new_help

async def main():
    img = await get_new_help(
        plugin_name="NTEUID",
        plugin_info={f"v{ver}": ""},
        plugin_icon=Image.open(icon_path).convert("RGBA"),
        plugin_help=data,
        plugin_prefix="",
        help_mode="dark",
        banner_sub_text="一切正常，就是异常。",
        icon_path=icon_path_dir,
        enable_cache=False,
        column=4,
        pm=1,  # 1 = 含「主人功能」栏目（贴合主人视角）
    )
    return img


def _save(res, out: Path):
    if isinstance(res, bytes):
        out.write_bytes(res)
    elif isinstance(res, str):
        import base64

        body = res.split("base64://", 1)[-1]
        out.write_bytes(base64.b64decode(body))
    elif hasattr(res, "save"):
        res.save(out)
    else:
        raise TypeError(f"未知返回类型: {type(res)}")


if __name__ == "__main__":
    res = asyncio.run(main())
    out = ROOT / "test_result" / "help_drive.png"
    out.parent.mkdir(exist_ok=True)
    _save(res, out)
    print(f"OK 类型={type(res)} 保存={out}")
