from __future__ import annotations

import json
import math
from typing import Any, cast
from functools import lru_cache
from dataclasses import dataclass

from ..utils.sdk.tajiduo_model import CharacterDetail, CharacterProperty, CharacterSuitItem
from ..utils.resource.RESOURCE_PATH import SCORING_PATH


@dataclass(frozen=True, slots=True, kw_only=True)
class AttributeInfo:
    attr_id: str
    name: str
    score: float


@dataclass(frozen=True, slots=True, kw_only=True)
class AttributeTable:
    entries: dict[str, AttributeInfo]

    def score_of(self, attr_id: str) -> float:
        attr = self.entries.get(attr_id.lower())
        return attr.score if attr is not None else 0.0

    def names_for(self, attr_ids: frozenset[str]) -> frozenset[str]:
        return frozenset(
            attr.name for attr_id in attr_ids if (attr := self.entries.get(attr_id)) is not None and attr.name
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class GradeTier:
    grade: str
    min_ratio: float


@dataclass(frozen=True, slots=True, kw_only=True)
class GradeTable:
    tiers: tuple[GradeTier, ...]

    def grade_of(self, ratio: float) -> str:
        for tier in self.tiers:
            if ratio >= tier.min_ratio:
                return tier.grade
        return self.tiers[-1].grade


@dataclass(frozen=True, slots=True, kw_only=True)
class ScorePlan:
    char_id: str
    refer_score: int
    core_main_attrs: frozenset[str]
    recommend_attrs: frozenset[str]
    effective_attr_names: frozenset[str]
    max_core: float
    max_pies: dict[str, float]
    max_score: int

    @property
    def effective_attrs(self) -> frozenset[str]:
        return self.core_main_attrs | self.recommend_attrs

    def max_for(self, item: CharacterSuitItem) -> float:
        if not item.id.startswith("cell"):
            return self.max_core
        grid = str(int(item.id.split("_", 1)[0][4:]))
        return self.max_pies.get(grid, 0.0)


@dataclass(frozen=True, slots=True, kw_only=True)
class EquipmentScore:
    item_id: str
    raw_score: float
    score: float
    max_score: float
    grade: str | None
    unlocked_subs: int


@dataclass(frozen=True, slots=True, kw_only=True)
class CharacterScore:
    plan: ScorePlan
    raw_score: float
    score_raw: float
    score: int
    grade: str
    equipment: tuple[EquipmentScore, ...]

    def is_role_prop_effective(self, prop: CharacterProperty) -> bool:
        return prop.id.lower() in self.plan.effective_attrs or prop.name in self.plan.effective_attr_names

    def is_main_prop_counted(self, prop: CharacterProperty) -> bool:
        return prop.value.strip().endswith("%") and prop.id.lower() in self.plan.core_main_attrs

    def is_sub_prop_recommended(self, prop: CharacterProperty) -> bool:
        return prop.id.lower() in self.plan.recommend_attrs

    def is_sub_prop_counted(self, index: int, item: CharacterSuitItem, prop: CharacterProperty) -> bool:
        return index < item.lev // 5 and self.is_sub_prop_recommended(prop)


@lru_cache(maxsize=1)
def load_attributes() -> AttributeTable:
    with (SCORING_PATH / "attributes.json").open("r", encoding="utf-8") as file:
        raw = cast(dict[str, dict[str, Any]], json.load(file))
    return AttributeTable(
        entries={
            attr_id.lower(): AttributeInfo(
                attr_id=attr_id.lower(),
                name=str(info.get("name", "")),
                score=float(info.get("score", 0.0)),
            )
            for attr_id, info in raw.items()
        }
    )


@lru_cache(maxsize=1)
def load_grades() -> GradeTable:
    with (SCORING_PATH / "grades.json").open("r", encoding="utf-8") as file:
        raw = cast(dict[str, Any], json.load(file))
    tiers = tuple(
        GradeTier(grade=str(item["grade"]), min_ratio=float(item["min_ratio"]))
        for item in cast(list[dict[str, Any]], raw.get("tiers", []))
    )
    if not tiers:
        raise ValueError("grades.json has no tiers")
    return GradeTable(tiers=tuple(sorted(tiers, key=lambda item: item.min_ratio, reverse=True)))


@lru_cache(maxsize=64)
def load_score_plan(char_id: str) -> ScorePlan | None:
    path = SCORING_PATH / "chars" / f"{char_id}.json"
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as file:
        raw = cast(dict[str, Any], json.load(file))

    refer_score = int(raw["refer_score"])
    max_data = cast(dict[str, Any], raw["max"])
    max_score = int(max_data["score"])
    if refer_score <= 0 or max_score <= 0:
        raise ValueError(f"invalid scoring plan: char_id={char_id}")

    max_pies = cast(dict[str, Any], max_data.get("pie") or {})
    core_main_attrs = frozenset(str(attr).lower() for attr in raw.get("core_main_attr_list", []))
    recommend_attrs = frozenset(str(attr).lower() for attr in raw.get("recommend_attr_list", []))
    attrs = load_attributes()
    return ScorePlan(
        char_id=char_id,
        refer_score=refer_score,
        core_main_attrs=core_main_attrs,
        recommend_attrs=recommend_attrs,
        effective_attr_names=attrs.names_for(core_main_attrs | recommend_attrs),
        max_core=float(max_data["core"]),
        max_pies={str(grid): float(value) for grid, value in max_pies.items()},
        max_score=max_score,
    )


def parse_score_value(value: str) -> tuple[float, bool]:
    raw = value.strip()
    if raw.endswith("%"):
        return float(raw[:-1]), True
    return float(raw), False


def score_equipment(
    item: CharacterSuitItem,
    plan: ScorePlan,
    attrs: AttributeTable,
    grades: GradeTable,
) -> EquipmentScore:
    raw_score = 0.0
    for prop in item.main_properties:
        if prop.value.strip() and prop.value.strip().endswith("%") and prop.id.lower() in plan.core_main_attrs:
            raw_score += _prop_score(prop, attrs)
    for index, prop in enumerate(item.properties):
        if prop.value.strip() and index < item.lev // 5 and prop.id.lower() in plan.recommend_attrs:
            raw_score += _prop_score(prop, attrs)

    max_score = plan.max_for(item)
    return EquipmentScore(
        item_id=item.id,
        raw_score=raw_score,
        score=raw_score * 100 / plan.refer_score,
        max_score=max_score,
        grade=grades.grade_of(raw_score / max_score) if max_score > 0 else None,
        unlocked_subs=item.lev // 5,
    )


def _score_character_nteuid(character: CharacterDetail) -> CharacterScore | None:
    plan = load_score_plan(character.id)
    if plan is None:
        return None
    items = (*character.suit.core, *character.suit.pie) if character.suit.id else ()
    if not items:
        return None

    attrs = load_attributes()
    grades = load_grades()
    equipment = tuple(score_equipment(item, plan, attrs, grades) for item in items)
    raw_score = sum(item.raw_score for item in equipment)
    score_raw = raw_score * 100 / plan.refer_score
    score = math.ceil(score_raw)
    return CharacterScore(
        plan=plan,
        raw_score=raw_score,
        score_raw=score_raw,
        score=score,
        grade=grades.grade_of(score / plan.max_score),
        equipment=equipment,
    )


def _score_mode() -> str:
    try:
        from ..nte_config.nte_config import NTEConfig

        return (NTEConfig.get_config("NTEScoreMode").data or "nteuid").strip().lower()
    except Exception:
        return "nteuid"


def score_character(character: CharacterDetail):
    """角色评分统一入口：按插件配置 NTEScoreMode 分派后端。

    - nteuid（默认）：本项目养成度评分，返回 CharacterScore
    - 异环工坊：新仓库(NTE-Drive-Calculator)成色分+毕业率，返回 DriveCharacterScore
    """
    if _score_mode() == "异环工坊":
        from NTEUID.extra.drive.score_drive import score_character_drive

        try:
            return score_character_drive(character)
        except Exception:
            return None
    return _score_character_nteuid(character)


def _prop_score(prop: CharacterProperty, attrs: AttributeTable) -> float:
    weight = attrs.score_of(prop.id)
    if weight <= 0:
        return 0.0
    value, is_percent = parse_score_value(prop.value)
    return (value / 100 if is_percent else value) / weight
