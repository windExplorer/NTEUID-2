import sys, types, asyncio
from pathlib import Path

ROOT = Path(r"e:\WP-V2\Mine\NTEUID-2")
NTEUID = ROOT / "NTEUID"

# ---- 0) 把本地桩包 stubs/ 放到最前，让 import gsuid_core.* 命中桩而非真实框架 ----
sys.path.insert(0, str(ROOT / "stubs"))

# ---- 1) 预置父包桩（带 __path__，使其 __init__ 不再被执行，避开插件注册链）----
def _pkg(name: str, path: Path):
    m = types.ModuleType(name)
    m.__path__ = [str(path)]
    sys.modules[name] = m
    return m

_pkg("NTEUID", NTEUID)
_pkg("NTEUID.utils", NTEUID / "utils")
_pkg("NTEUID.utils.sdk", NTEUID / "utils" / "sdk")
_pkg("NTEUID.utils.resource", NTEUID / "utils" / "resource")
_pkg("NTEUID.nte_role", NTEUID / "nte_role")

# ---- 2) 安全导入评分与出图模块（真实执行，仅依赖上面的 gsuid_core 桩 + 本地资源）----
from NTEUID.utils.sdk.tajiduo_model import (  # noqa: E402
    CharacterDetail,
    CharacterSuit,
    CharacterSuitItem,
    CharacterProperty,
    CharElement,
    CharGroup,
    CharQuality,
)
from NTEUID.nte_role.score import _score_character_nteuid  # noqa: E402
from NTEUID.nte_role.score_drive import score_character_drive  # noqa: E402
from NTEUID.nte_role import character_card  # noqa: E402
from NTEUID.nte_role.character_card import draw_character_card_with_original  # noqa: E402
from PIL import Image  # noqa: E402

# 伤害区块依赖额外本地数据，离线可能缺；异常时跳过该区块，不影响整张卡片
_orig_compute = character_card._compute_damage
def _safe_compute(character):
    try:
        return _orig_compute(character)
    except Exception as _e:
        character_card.logger.debug(f"[本地测试] 跳过伤害区块: {_e!r}")
        return None
character_card._compute_damage = _safe_compute

from NTEUID.nte_role import score as _score_mod  # noqa: E402

import json
from datetime import datetime

# 从真实面板 JSON 加载（免 token）：test/1004.json —— 安魂曲养成数据
_JSON_PATH = ROOT / "test" / "1004.json"
with _JSON_PATH.open(encoding="utf-8") as _f:
    _raw = json.load(_f)
char = CharacterDetail.model_validate(_raw)

# ---- 收集输出到内存，最后同时打印并写入 test_result 目录 ----
_lines: list[str] = []

def out(line: str = "") -> None:
    print(line)
    _lines.append(line)

out(f"角色面板：id={char.id} name={char.name} 品质={char.quality} "
    f"核心盘={len(char.suit.core)} 驱动盘={len(char.suit.pie)}")
out(f"数据源：{_JSON_PATH.name}    生成时间：{datetime.now():%Y-%m-%d %H:%M:%S}")
out()

out("=== 本项目养成度评分 (nteuid) ===")
r1 = _score_character_nteuid(char)
out(f"总评 score = {r1.score}  grade = {r1.grade}  "
    f"raw = {round(r1.raw_score, 3)}  max = {r1.plan.max_score}")
for eq in r1.equipment:
    out(f"  {eq.item_id}: raw={eq.raw_score:.3f} score={eq.score:.2f} "
        f"grade={eq.grade} unlocked_subs={eq.unlocked_subs}")

out()
out("=== 异环工坊评分 (drive) ===")
r2 = score_character_drive(char)
if r2 is None:
    out("返回 None（角色可能不在新仓库 roles.json 中，或驱动盘数据缺失）")
else:
    out(f"总评 score = {r2.score}  grade = {r2.grade}")
    for eq in getattr(r2, "equipment", ()) or ():
        out(f"  {eq.item_id}: score={getattr(eq, 'score', None)} "
            f"grade={getattr(eq, 'grade', None)}")

# ---- 落盘到 test_result/<id>_<name>.txt ----
_RESULT_DIR = ROOT / "test_result"
_RESULT_DIR.mkdir(exist_ok=True)
_result_path = _RESULT_DIR / f"{char.id}_{char.name}.txt"
_result_path.write_text("\n".join(_lines), encoding="utf-8")
out()
out(f"报告已保存：{_result_path}")

# ---- 渲染评分卡片图片（免 token，纯本地）----
# avatar：优先用本地头像，缺失则用占位图
_avatar_path = NTEUID / "resource" / "char" / "avatar" / f"{char.id}.png"
if _avatar_path.exists():
    _avatar = Image.open(_avatar_path).convert("RGBA")
else:
    _avatar = Image.new("RGBA", (200, 200), (180, 180, 180, 255))


async def _render_once(mode: str, suffix: str) -> None:
    """强制评分后端为 mode，渲染并保存一张卡片图片。"""
    _score_mod._score_mode = lambda: mode
    out()
    out(f"=== 渲染评分卡片图片（{mode}）===")
    try:
        _card_img, _original_path = await draw_character_card_with_original(
            char, role_name=char.name, uid=char.id, avatar=_avatar
        )
        _img_path = _RESULT_DIR / f"{char.id}_{char.name}_{suffix}.png"
        if isinstance(_card_img, Image.Image):
            _card_img.save(_img_path)
            out(f"卡片图片已保存：{_img_path}  ({_card_img.width}x{_card_img.height})")
        else:
            out(f"出图返回类型异常：{type(_card_img)}（未保存）")
    except Exception as _err:
        import traceback
        out(f"渲染卡片（{mode}）失败：")
        out(traceback.format_exc())


out()
out("=== 渲染评分卡片图片 ===")
asyncio.run(_render_once("nteuid", "nteuid"))
asyncio.run(_render_once("异环工坊", "drive"))
