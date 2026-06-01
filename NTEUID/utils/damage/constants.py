from __future__ import annotations

from ..sdk.tajiduo_model import CharElement

# —— 防御区等级常数（轨外之境真实公式：大世界敌人项=100，轨外之境=90，角色项恒 100）——
ENEMY_DEF_LEVEL_CONST = 90
CHAR_DEF_LEVEL_CONST = 100

# —— 写死的假设值（资源无对应数据，要改改这里一处即可，不进用户配置）——
DEFAULT_ENEMY_LEVEL = 80  # 伤害假设的敌人等级（轨外之境基线）
DEFAULT_ENEMY_RESIST = 0.2  # 敌人全属性抗性基线（真实敌人表实测：普遍 0.2，硬敌 0.28，弱点 0.16；无一为 0）

# —— 角色元素 → 面板属性 id 后缀（取自真实面板 properties 的 id）——
# 注意：魂(PSYCHE) 在面板里写作 "syche" 而非 "psyche"，按真实数据来。
_ELEMENT_SUFFIX: dict[CharElement, str] = {
    CharElement.PSYCHE: "syche",
    CharElement.COSMOS: "cosmos",
    CharElement.NATURE: "nature",
    CharElement.INCANTATION: "incantation",
    CharElement.CHAOS: "chaos",
    CharElement.LAKSHANA: "lakshana",
}

# 面板里固定的属性 id
PROP_ATK = "atk"
PROP_DEF = "def"
PROP_HPMAX = "hpmax"
PROP_CRIT = "crit"
PROP_CRIT_DMG = "critdamage"
PROP_DMG_GENERAL = "damageupgeneral"


def element_dmg_prop(element: CharElement) -> str:
    """该元素「异能伤害增强」在面板里的属性 id，如 咒 → damageupincantation。"""
    return f"damageup{_ELEMENT_SUFFIX[element]}"
