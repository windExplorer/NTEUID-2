"""可选评分后端：移植自 NTE-Drive-Calculator（https://github.com/hxwd94666/NTE-Drive-Calculator）。

提供两套指标（通过插件配置 `NTEScoreMode=drive` 启用）：
1. 单件装备「成色分」：照搬新仓库 ScoringEngine 的 drive/tape 评分公式，按角色 weights 给每件
   驱动盘打绝对质量分，并给出 D/C/B/A/S/SS/SSS/ACE 八档评级。
2. 直伤「毕业率」：用新仓库的粗直伤模型，算 玩家实际直伤 / 满配金盘理想直伤 的比值。

数据缺口说明：
- 新仓库的成色分需要每件装备的「品质(金/紫/蓝)」与「区格数(area)」，而本项目面板接口解析出的
  CharacterSuitItem 不含这两个字段。本模块在 CharacterSuitItem 上保留了可选的 `quality`/`area`
  字段（若接口返回则自动采用，否则默认 金 + 区格4），属兜底估算，后续接口补全后会自动更准。
- 词条名体系不同（本项目用 gsuid id 如 `atkup`，新仓库用可读名如 `攻击力%`），通过
  `_GSUID_TO_DRIVE` 桥接表归一。
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from ..utils.sdk.tajiduo_model import (
    CharQuality,
    CharacterDetail,
    CharacterSuitItem,
)

# 新仓库 config 目录：克隆仓库 NTE-Drive-Calculator 与本项目(NTEUID)同级（仓库根目录）。
# 兼容两种放置位置：仓库根目录 或 NTEUID/ 下，优先取实际存在的那个。
def _resolve_drive_config_dir() -> Path:
    here = Path(__file__).resolve()
    candidates = [
        here.parents[2] / "NTE-Drive-Calculator" / "config",  # 仓库根目录
        here.parents[1] / "NTE-Drive-Calculator" / "config",  # NTEUID/ 下
    ]
    for c in candidates:
        if (c / "roles.json").exists():
            return c
    return candidates[0]


_DRIVE_CONFIG_DIR = _resolve_drive_config_dir()

# 区格默认（驱动盘满级常见为 4）；品质默认金
DEFAULT_AREA = 4
QUALITY_COEF: dict[str, float] = {"Gold": 1.0, "Purple": 0.8, "Blue": 0.6}
QUALITY_MAP: dict[CharQuality, str] = {
    CharQuality.S: "Gold",
    CharQuality.A: "Purple",
    CharQuality.B: "Blue",
}
# 八档评级阶梯（比例阈值，从高到低）
GRADE_LADDER = [
    ("ACE", 0.8),
    ("SSS", 0.7),
    ("SS", 0.6),
    ("S", 0.5),
    ("A", 0.4),
    ("B", 0.3),
    ("C", 0.2),
    ("D", 0.0),
]
FULL_DRIVE_AREA = 20  # 毕业基准用的满区

# gsuid 词条 id -> 新仓库 canonical 名（与 stats.json / roles.json weights 对齐）
_GSUID_TO_DRIVE: dict[str, str] = {
    "atk": "攻击力",
    "atkup": "攻击力%",
    "atkadd": "攻击力",
    "atkbase": "攻击力",
    "defup": "防御力%",
    "defadd": "防御力",
    "defbase": "防御力",
    "hpmaxup": "生命值%",
    "hpmaxadd": "生命值",
    "hpmaxbase": "生命值",
    "critbase": "暴击率%",
    "critadd": "暴击率",
    "critdamagebase": "暴击伤害%",
    "critdamageadd": "暴击伤害",
    "chargegetefficiencybase": "充能效率%",
    "magbase": "环合强度",
    "magadd": "环合强度",
    "magup": "环合强度",
    "unbalintensitybase": "倾陷强度",
    "unbalintensityadd": "倾陷强度",
    "unbalintensityup": "倾陷强度",
    "healup": "治疗加成%",
    "healbeup": "治疗加成%",
    "defignore": "无视防御%",
    "damageupgeneralbase": "伤害增加%",
    "damageupgeneraladd": "伤害增加%",
    "damageupcosmosbase": "光属性异能伤害增强%",
    "damageupnaturebase": "灵属性异能伤害增强%",
    "damageupincantationbase": "咒属性异能伤害增强%",
    "damageupchaosbase": "暗属性异能伤害增强%",
    "damageuppsychebase": "魂属性异能伤害增强%",
    "damageuplakshanabase": "相属性异能伤害增强%",
    "damageuppsychicallybase": "心灵伤害增强%",
}

# 角色面板里「总攻击」对应的 canonical 名（用于毕业率粗算）
_CHAR_ATTACK_PROP = "atk"


@dataclass
class DriveEquipmentScore:
    """与 NTEUID 的 EquipmentScore 字段保持兼容，便于复用展示层。"""

    item_id: str
    raw_score: float
    score: float
    max_score: float
    grade: str | None
    unlocked_subs: int


@dataclass
class DriveCharacterScore:
    """drive 后端评分结果。"""

    score: int
    grade: str
    equipment: tuple
    graduation: float  # 毕业率 0~1
    per_item_drive: dict[str, float]  # item_id -> 成色分
    weights: dict[str, float] = field(default_factory=dict)  # 副词条权重（推荐词条）
    main_weights: dict[str, float] = field(default_factory=dict)  # 主词条权重（计入词条）
    alias_map: dict[str, str] = field(default_factory=dict)  # 词条别名映射

    # ---- 展示层判定接口（与 nteuid 后端 CharacterScore 对齐）----
    def _canon(self, prop) -> str:
        """把面板/装备词条统一桥接成新仓库 canonical 名（中文）。"""
        canon = _bridge_stat(getattr(prop, "id", "") or "")
        if canon:
            return canon
        return getattr(prop, "name", "") or ""

    def _weight_of(self, prop, table: dict[str, float]) -> float:
        if not table:
            return 0.0
        return _weight_for(self._canon(prop), table, self.alias_map)

    def is_role_prop_effective(self, prop) -> bool:
        """角色总面板里哪些词条算「有效词条」——主/副词条权重并集，用于高亮。"""
        return self._weight_of(prop, self.weights) > 0 or self._weight_of(prop, self.main_weights) > 0

    def is_main_prop_counted(self, prop) -> bool:
        """驱动盘主词条是否被角色方案计入（高亮）。"""
        return self._weight_of(prop, self.main_weights) > 0

    def is_sub_prop_recommended(self, prop) -> bool:
        """驱动盘副词条是否被角色方案推荐（高亮）。"""
        return self._weight_of(prop, self.weights) > 0


# --------------------------------------------------------------------------- #
# 配置加载
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=1)
def _load_drive_config() -> tuple[dict | None, dict | None]:
    roles_path = _DRIVE_CONFIG_DIR / "roles.json"
    stats_path = _DRIVE_CONFIG_DIR / "stats.json"
    if not roles_path.exists() or not stats_path.exists():
        return None, None
    try:
        roles = json.loads(roles_path.read_text(encoding="utf-8"))
        stats = json.loads(stats_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None, None
    return roles, stats


# --------------------------------------------------------------------------- #
# 词条桥接 / 数值解析
# --------------------------------------------------------------------------- #
def _bridge_stat(prop_id: str) -> str | None:
    return _GSUID_TO_DRIVE.get(prop_id.lower())


def _num(value: str) -> float:
    if not value:
        return 0.0
    v = str(value).strip()
    if v.endswith("%"):
        v = v[:-1]
    try:
        return float(v)
    except ValueError:
        return 0.0


def _item_substats(item: CharacterSuitItem) -> dict[str, float]:
    """驱动盘副词条 -> {canonical 名: 数值}。成色分只用到「名字」，数值仅作记录。"""
    out: dict[str, float] = {}
    for prop in item.properties:
        canon = _bridge_stat(prop.id)
        if canon and prop.value:
            out[canon] = _num(prop.value)
    return out


def _item_quality(item: CharacterSuitItem) -> str:
    q = getattr(item, "quality", None)
    if isinstance(q, CharQuality):
        return QUALITY_MAP.get(q, "Gold")
    if isinstance(q, str):
        return q if q in QUALITY_COEF else "Gold"
    return "Gold"


def _item_area(item: CharacterSuitItem) -> int:
    a = getattr(item, "area", 0)
    return a if isinstance(a, int) and a > 0 else DEFAULT_AREA


# --------------------------------------------------------------------------- #
# 权重 / 评分（移植自 ScoringEngine）
# --------------------------------------------------------------------------- #
def _weight_for(stat_name: str, weights: dict[str, float], alias_map: dict[str, str]) -> float:
    """容忍地查权重：原样 / 去% / 加% / 走别名表。"""
    candidates = [stat_name]
    if stat_name.endswith("%"):
        candidates.append(stat_name[:-1])
    else:
        candidates.append(stat_name + "%")
    alias = alias_map.get(stat_name, stat_name)
    if alias not in candidates:
        candidates.append(alias)
    for c in candidates:
        w = weights.get(c)
        if w:
            return float(w)
    return 0.0


def _max_theoretical_weight(weights: dict[str, float], main_only_keywords: list[str]) -> float:
    """理论最优 4 条副词条的权重和（排除主词条专用属性）。"""
    valid = [
        w
        for name, w in weights.items()
        if not any(kw in name for kw in main_only_keywords)
    ]
    valid.sort(reverse=True)
    return float(sum(valid[:4])) or 1.0


def _drive_score(
    substats: dict[str, float],
    weights: dict[str, float],
    max_weight: float,
    area: int,
    quality: str,
    alias_map: dict[str, str],
) -> float:
    if max_weight <= 0:
        return 0.0
    # 注意：新仓库只按「出现的词条名」累加权重，不乘词条数值
    actual = sum(_weight_for(n, weights, alias_map) for n in substats)
    if actual <= 0:
        return 0.0
    coef = QUALITY_COEF.get(quality, 1.0)
    return round((10.0 / max_weight) * actual * area * coef, 2)


def _grade_tag(score: float, area: int) -> str:
    denom = (area * 10.0) or 1.0
    ratio = score / denom
    for grade, thr in GRADE_LADDER:
        if ratio >= thr:
            return grade
    return "D"


def _top_weighted_gold(
    gold_base: dict[str, float],
    weights: dict[str, float],
    alias_map: dict[str, str],
    count: int = 4,
) -> list[str]:
    cands = [(st, _weight_for(st, weights, alias_map)) for st in gold_base]
    cands = [(st, w) for st, w in cands if w > 0]
    cands.sort(key=lambda x: -x[1])
    return [st for st, _ in cands[:count]]


# --------------------------------------------------------------------------- #
# 毕业率（粗直伤模型，移植自 damage_model.graduation_model）
# --------------------------------------------------------------------------- #
def _coarse_damage(stats: dict[str, float]) -> float:
    atk_base = stats.get("攻击力", 0.0)
    atk_pct = stats.get("攻击力%", 0.0)
    attack = atk_base * (1 + atk_pct / 100.0)
    ability = stats.get("异能伤害%", 0.0)
    bonus_inc = stats.get("伤害增加%", 0.0)
    bonus = 1 + (ability + bonus_inc) / 100.0
    crit_rate = min(stats.get("暴击率%", 0.0), 100.0) / 100.0
    crit_dmg = stats.get("暴击伤害%", 0.0) / 100.0
    crit = 1 + crit_rate * crit_dmg
    return attack * bonus * crit


def _panel_to_canonical(character: CharacterDetail) -> dict[str, float]:
    out: dict[str, float] = {}
    for prop in character.properties:
        if not prop.value:
            continue
        canon = _bridge_stat(prop.id)
        if not canon:
            continue
        out[canon] = out.get(canon, 0.0) + _num(prop.value)
    return out


def _graduation_rate(
    character: CharacterDetail,
    role_cfg: dict,
    stats: dict,
    alias_map: dict[str, str],
) -> float:
    weights = role_cfg.get("weights", {})
    gold_base = stats.get("gold_base_values", {})
    main_only = stats.get("main_only_keywords", [])

    player = _panel_to_canonical(character)
    player_dmg = _coarse_damage(player)

    # 理想板：玩家属性 + 满配金盘顶 4 权重词条 × 满区
    top4 = _top_weighted_gold(gold_base, weights, alias_map, 4)
    ideal = dict(player)
    for st in top4:
        ideal[st] = ideal.get(st, 0.0) + gold_base.get(st, 0.0) * FULL_DRIVE_AREA
    # 形态额外加成（默认按 1 个计入，近似）
    for st, val in role_cfg.get("extra_shape_buffs", {}).items():
        ideal[st] = ideal.get(st, 0.0) + val

    bench_dmg = _coarse_damage(ideal)
    return (player_dmg / bench_dmg) if bench_dmg > 0 else 0.0


# --------------------------------------------------------------------------- #
# 入口
# --------------------------------------------------------------------------- #
def score_character_drive(character: CharacterDetail) -> DriveCharacterScore | None:
    """drive 后端评分：返回单件成色分（含八档评级）与整角色毕业率。无方案时返回 None。"""
    roles, stats = _load_drive_config()
    if roles is None or stats is None:
        return None

    role_cfg = roles.get(character.name) or roles.get(character.id)
    if role_cfg is None:
        return None

    weights = role_cfg.get("weights", {})
    alias_map = stats.get("stat_alias_mapping", {})
    main_only = stats.get("main_only_keywords", [])
    max_weight = _max_theoretical_weight(weights, main_only)

    items: list[CharacterSuitItem] = [*character.suit.core, *character.suit.pie]
    equip_scores: list[DriveEquipmentScore] = []
    per_item_drive: dict[str, float] = {}
    total = 0.0
    for item in items:
        substats = _item_substats(item)
        area = _item_area(item)
        quality = _item_quality(item)
        s = _drive_score(substats, weights, max_weight, area, quality, alias_map)
        grade = _grade_tag(s, area) if s > 0 else None
        equip_scores.append(
            DriveEquipmentScore(
                item_id=item.id,
                raw_score=s,
                score=s,
                max_score=area * 10.0,
                grade=grade,
                unlocked_subs=item.lev // 5,
            )
        )
        per_item_drive[item.id] = s
        total += s

    graduation = _graduation_rate(character, role_cfg, stats, alias_map)
    score = math.ceil(total) if total else 0
    # 整角色评级：以「总分成色 / 满区假设」给出八档近似
    overall_grade = _grade_tag(total, DEFAULT_AREA * max(len(items), 1))

    return DriveCharacterScore(
        score=score,
        grade=overall_grade,
        equipment=tuple(equip_scores),
        graduation=graduation,
        per_item_drive=per_item_drive,
        weights=weights,
        main_weights=role_cfg.get("main_weights", {}),
        alias_map=alias_map,
    )
