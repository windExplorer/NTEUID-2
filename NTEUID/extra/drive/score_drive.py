"""可选评分后端：移植自 NTE-Drive-Calculator（https://github.com/hxwd94666/NTE-Drive-Calculator）。

提供两套指标（通过插件配置 `NTEScoreMode=drive` 启用）：
1. 单件装备「成色分」：照搬新仓库 ScoringEngine 的 drive/tape 评分公式，按角色 weights 给每件
   驱动盘打绝对质量分，并给出 D/C/B/A/S/SS/SSS/ACE 八档评级。
2. 直伤「毕业率」：用新仓库的粗直伤模型，算 玩家实际直伤 / 满配金盘理想直伤 的比值。

数据缺口说明：
- 新仓库的成色分需要每件装备的「品质(金/紫/蓝)」与「区格数(area)」，而本项目面板接口解析出的
  CharacterSuitItem 不含这两个字段。本模块在 CharacterSuitItem 上保留了可选的 `quality`/`area`
  字段（若接口返回则自动采用，否则默认 金 + 区格4），属兜底估算，后续接口补全后会自动更准。
- 角色权重数据源已是 **SQLite**（`data/game_static.sqlite3`）：`character_weight_recommendation_property`
  （含 `weight`/`main_weight`）、`logical_character_shape_bonus*`、`character_graduation_template`
  （含 `benchmark_damage` 毕业基准）。不再读取旧的 `config/roles.json`。
- 词条名体系不同（本项目用 gsuid id 如 `atkup`，新仓库用可读名如 `攻击力%`），通过
  `_GSUID_TO_DRIVE` 桥接表归一；数据库里的 PascalCase gsuid（如 `CritBase`）也经 `_gsuid_to_cn` 翻成中文。
"""

from __future__ import annotations

import json
import math
import sqlite3
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from ...utils.sdk.tajiduo_model import (
    CharQuality,
    CharacterDetail,
    CharacterSuitItem,
)

# drive 附加目录：NTEUID/extra/drive（内置分发，不依赖外部克隆仓库）
_DRIVE_ROOT = Path(__file__).resolve().parents[2] / "extra" / "drive"
_DRIVE_CONFIG_DIR = _DRIVE_ROOT / "config"          # 仅 stats.json（词条目录/别名/主词条关键词）
_DRIVE_DATA_DIR = _DRIVE_ROOT / "data"              # game_static.sqlite3（权重/形态/毕业基准）
_DRIVE_DB_PATH = _DRIVE_DATA_DIR / "game_static.sqlite3"

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
# 覆盖两类来源：
#   a) SDK 面板接口返回的原始词条 id（`crit`, `damageupchaos`, `mag` 等无后缀格式）
#   b) 权重数据库 / 内部使用的 PascalCase gsuid（`CritBase`, `AtkUp` 等，统一 lower() 查表）
_GSUID_TO_DRIVE: dict[str, str] = {
    # ---- 面板基础属性 ----
    "hpmax": "生命值",
    "atk": "攻击力",
    "def": "防御力",
    # ---- 攻击力 ----
    "atkup": "攻击力%",
    "atkadd": "攻击力",
    "atkbase": "攻击力",
    # ---- 防御力 ----
    "defup": "防御力%",
    "defadd": "防御力",
    "defbase": "防御力",
    # ---- 生命值 ----
    "hpmaxup": "生命值%",
    "hpmaxadd": "生命值",
    "hpmaxbase": "生命值",
    # ---- 暴击 ----
    "crit": "暴击率%",
    "critbase": "暴击率%",
    "critadd": "暴击率",
    "critdamage": "暴击伤害%",
    "critdamagebase": "暴击伤害%",
    "critdamageadd": "暴击伤害",
    # ---- 充能 ----
    "chargegetefficiency": "充能效率%",
    "chargegetefficiencybase": "充能效率%",
    # ---- 环合 / 倾陷 ----
    "mag": "环合强度",
    "magbase": "环合强度",
    "magadd": "环合强度",
    "magup": "环合强度",
    "unbalintensity": "倾陷强度",
    "unbalintensitybase": "倾陷强度",
    "unbalintensityadd": "倾陷强度",
    "unbalintensityup": "倾陷强度",
    # ---- 治疗 / 防御穿透 ----
    "healup": "治疗加成%",
    "healbeup": "治疗加成%",
    "defignore": "无视防御%",
    # ---- 伤害增加 ----
    "damageupgeneral": "伤害增加%",
    "damageupgeneralbase": "伤害增加%",
    "damageupgeneraladd": "伤害增加%",
    # ---- 分属性异能伤害增强 (SDK 简写 + 数据库 PascalCase base) ----
    "damageupcosmos": "光属性异能伤害增强%",
    "damageupcosmosbase": "光属性异能伤害增强%",
    "damageupnature": "灵属性异能伤害增强%",
    "damageupnaturebase": "灵属性异能伤害增强%",
    "damageupincantation": "咒属性异能伤害增强%",
    "damageupincantationbase": "咒属性异能伤害增强%",
    "damageupchaos": "暗属性异能伤害增强%",
    "damageupchaosbase": "暗属性异能伤害增强%",
    "damageuppsyche": "魂属性异能伤害增强%",
    "damageuppsychebase": "魂属性异能伤害增强%",
    "damageuplakshana": "相属性异能伤害增强%",
    "damageuplakshanabase": "相属性异能伤害增强%",
    "damageuppsychically": "心灵伤害增强%",
    "damageuppsychicallybase": "心灵伤害增强%",
}

# 数据库 `character_weight_recommendation_property.property_id` 用 PascalCase gsuid
# （如 CritBase / AtkUp），面板 `prop.id` 用小写 gsuid（critbase / atkup）。两者统一翻成
# 中文 canonical 名，与 stats.json、`_weight_for` 对齐。
_GSUID_TO_CN: dict[str, str] = {k.lower(): v for k, v in _GSUID_TO_DRIVE.items()}


def _gsuid_to_cn(gsuid: str) -> str | None:
    return _GSUID_TO_CN.get(str(gsuid).lower())

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
# 配置加载（数据源：game_static.sqlite3）
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=1)
def _load_drive_config() -> tuple[dict | None, dict | None]:
    """从 SQLite 装配 drive 评分配置，返回 `(role_by_id, stats)`。

    `role_by_id` 以角色 id（字符串）为键，值为该角色的配置：
    `{weights, main_weights, extra_shape_label, extra_shape_buffs, benchmark_damage}`。
    权重来自 `character_weight_recommendation_property`（gsuid -> 中文 canonical 归一）；
    形态加成来自 `logical_character_shape_bonus*`；毕业基准来自
    `character_graduation_template.benchmark_damage`。
    """
    stats = _load_stats()
    if stats is None:
        return None, None
    if not _DRIVE_DB_PATH.exists():
        return None, stats

    try:
        con = sqlite3.connect(str(_DRIVE_DB_PATH))
        con.row_factory = None
        cur = con.cursor()

        # 1) 角色权重（副词条 weights / 主词条 main_weights）
        weights_by_char: dict[int, dict] = {}
        cur.execute(
            "SELECT character_id, property_id, weight, main_weight "
            "FROM character_weight_recommendation_property"
        )
        for cid, pid, w, mw in cur.fetchall():
            cn = _gsuid_to_cn(pid) or str(pid)
            d = weights_by_char.setdefault(cid, {"weights": {}, "main_weights": {}})
            if w:
                d["weights"][cn] = float(w)
            if mw:
                d["main_weights"][cn] = float(mw)

        # 2) 形态加成（extra_shape）
        shape_by_char: dict[int, dict] = {}
        cur.execute(
            "SELECT representative_character_id, shape_label, shape_grid_count "
            "FROM logical_character_shape_bonus"
        )
        for cid, label, grid in cur.fetchall():
            shape_by_char.setdefault(cid, {})["label"] = label
            shape_by_char[cid]["grid"] = grid
        cur.execute(
            "SELECT logical_character_key, property_id, display_value "
            "FROM logical_character_shape_bonus_property"
        )
        for key, pid, val in cur.fetchall():
            try:
                cid = int(str(key).split(":")[-1])
            except (ValueError, TypeError):
                continue
            cn = _gsuid_to_cn(pid) or str(pid)
            shape_by_char.setdefault(cid, {}).setdefault("buffs", {})[cn] = float(val)

        # 3) 毕业基准（官方默认板直伤）
        bench_by_char: dict[int, float] = {}
        cur.execute(
            "SELECT character_id, benchmark_damage "
            "FROM character_graduation_template WHERE source_kind='official_default'"
        )
        for cid, bench in cur.fetchall():
            if bench is not None:
                bench_by_char[cid] = float(bench)
        con.close()
    except sqlite3.Error:
        return None, stats

    # 装配：角色 id -> 配置
    role_by_id: dict[str, dict] = {}
    all_cids = set(weights_by_char) | set(bench_by_char) | set(shape_by_char)
    for cid in all_cids:
        w = weights_by_char.get(cid, {})
        sh = shape_by_char.get(cid, {})
        role_by_id[str(cid)] = {
            "weights": w.get("weights", {}),
            "main_weights": w.get("main_weights", {}),
            "extra_shape_label": sh.get("label"),
            "extra_shape_buffs": sh.get("buffs", {}),
            "benchmark_damage": bench_by_char.get(cid),
        }
    return role_by_id, stats


def _load_stats() -> dict | None:
    """词条目录 / 别名 / 主词条关键词等仍来自 stats.json。"""
    stats_path = _DRIVE_CONFIG_DIR / "stats.json"
    if not stats_path.exists():
        return None
    try:
        return json.loads(stats_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


@lru_cache(maxsize=1)
def _load_roles_json() -> dict | None:
    """兜底：从 roles.json 按角色显示名查找方案（数据源 SQLite 未覆盖时）。"""
    roles_path = _DRIVE_CONFIG_DIR / "roles.json"
    if not roles_path.exists():
        return None
    try:
        return json.loads(roles_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


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
    # 增伤区：聚合所有分属性异能伤害增强%（灵/咒/暗/魂/相/光/心灵）与已归一化的 异能伤害%。
    # 面板 canonical 用的是分属性名（如「灵属性异能伤害增强%」），需在此汇总，否则会漏算增伤区。
    ability = stats.get("异能伤害%", 0.0)
    for key, val in stats.items():
        if key.endswith("异能伤害增强%"):
            ability += val
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


def _normalize_for_damage(stats: dict[str, float]) -> dict[str, float]:
    """聚合分属性异能伤害增强% 为 异能伤害%，得到粗直伤模型所需的归一化属性集。"""
    out: dict[str, float] = {}
    for k, v in stats.items():
        if k.endswith("异能伤害增强%"):
            out["异能伤害%"] = out.get("异能伤害%", 0.0) + v
        else:
            out[k] = out.get(k, 0.0) + v
    return out


# 单位边际收益默认步长（来自评分算法文档；百分比属性单位=百分点）
_DAMAGE_STEP: dict[str, float] = {
    "攻击力": 1.0,
    "攻击力%": 1.25,
    "异能伤害%": 1.25,
    "伤害增加%": 1.0,
    "暴击率%": 1.0,
    "暴击伤害%": 2.0,
}


def calc_direct_marginal_benefits(
    stats: dict[str, float],
    benefit_one: dict[str, float] | None = None,
    crit_rate_cap: float = 1.0,
) -> tuple[float, list[tuple[str, float, float, float]]]:
    """直伤评分模型的单位边际收益。

    对每个属性单独 +1 单位（默认步长见 `_DAMAGE_STEP`）后重算粗直伤，得到该项带来的相对提升：
       边际收益% = (新直伤 / 基准直伤 − 1) × 100
    返回 `(基准直伤, 已按收益降序排列的 [(属性名, 当前值, 单位, 收益%)])`。
    """
    base = _normalize_for_damage(stats)
    base_dmg = _coarse_damage(base)
    steps = benefit_one or _DAMAGE_STEP
    results: list[tuple[str, float, float, float]] = []
    for name, unit in steps.items():
        perturbed = dict(base)
        perturbed[name] = base.get(name, 0.0) + unit
        new_dmg = _coarse_damage_base(perturbed, crit_rate_cap)
        benefit = (new_dmg / base_dmg - 1.0) * 100.0 if base_dmg > 0 else 0.0
        results.append((name, base.get(name, 0.0), unit, benefit))
    results.sort(key=lambda x: -x[3])
    return base_dmg, results


def _coarse_damage_base(stats: dict[str, float], crit_rate_cap: float = 1.0) -> float:
    """与 `_coarse_damage` 相同，但暴击率封顶可配（边际收益扰动时用）。"""
    atk_base = stats.get("攻击力", 0.0)
    atk_pct = stats.get("攻击力%", 0.0)
    attack = atk_base * (1 + atk_pct / 100.0)
    ability = stats.get("异能伤害%", 0.0)
    for key, val in stats.items():
        if key.endswith("异能伤害增强%"):
            ability += val
    bonus = 1 + (ability + stats.get("伤害增加%", 0.0)) / 100.0
    crit_rate = min(stats.get("暴击率%", 0.0), crit_rate_cap * 100.0) / 100.0
    crit_dmg = stats.get("暴击伤害%", 0.0) / 100.0
    return attack * bonus * (1 + crit_rate * crit_dmg)


def _graduation_rate(
    character: CharacterDetail,
    role_cfg: dict,
    stats: dict,
    alias_map: dict[str, str],
) -> float:
    player = _panel_to_canonical(character)
    player_dmg = _coarse_damage(player)

    # 优先用数据库里的官方毕业基准（character_graduation_template.benchmark_damage）
    bench = role_cfg.get("benchmark_damage")
    if bench:
        return (player_dmg / float(bench)) if bench > 0 else 0.0

    # 兜底：无基准时用「玩家属性 + 满配金盘顶 4 权重词条 × 满区」构造理想板
    weights = role_cfg.get("weights", {})
    gold_base = stats.get("gold_base_values", {})
    main_only = stats.get("main_only_keywords", [])
    top4 = _top_weighted_gold(gold_base, weights, alias_map, 4)
    ideal = dict(player)
    for st in top4:
        ideal[st] = ideal.get(st, 0.0) + gold_base.get(st, 0.0) * FULL_DRIVE_AREA
    for st, val in role_cfg.get("extra_shape_buffs", {}).items():
        ideal[st] = ideal.get(st, 0.0) + val
    bench_dmg = _coarse_damage(ideal)
    return (player_dmg / bench_dmg) if bench_dmg > 0 else 0.0


# --------------------------------------------------------------------------- #
# 入口
# --------------------------------------------------------------------------- #
def score_character_drive(character: CharacterDetail) -> DriveCharacterScore | None:
    """drive 后端评分：返回单件成色分（含八档评级）与整角色毕业率。无方案时返回 None。"""
    role_by_id, stats = _load_drive_config()
    if stats is None or role_by_id is None:
        return None
    roles = _load_roles_json()

    # 优先按角色 id 对齐；显示名仅作兜底（部分数据源缺 id 时）。
    role_cfg = role_by_id.get(str(character.id)) or (roles or {}).get(character.name)
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
