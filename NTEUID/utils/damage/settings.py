from __future__ import annotations

from .models import EnemyProfile
from .constants import DEFAULT_ENEMY_LEVEL, DEFAULT_ENEMY_RESIST

# 敌人等级 / 抗性写死在 constants（真实敌人表实测值）。


def base_enemy(*, def_reduction: float = 0.0, res_reduction: float = 0.0) -> EnemyProfile:
    """默认敌人（轨外之境 80 级、全抗 0.2 真实基线）；解析到的减防 / 减抗再填进来。"""
    return EnemyProfile(
        level=DEFAULT_ENEMY_LEVEL,
        resist=DEFAULT_ENEMY_RESIST,
        def_reduction=def_reduction,
        res_reduction=res_reduction,
    )
