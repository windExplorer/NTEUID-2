from __future__ import annotations

import time

from .gacha_model import (
    NTEGachaItem,
    NTEGachaSection,
    NTEGachaSummary,
    NTEGachaOverview,
)
from ..utils.name_convert import name_by_id
from ..utils.sdk.taptap_model import GachaSummary as TaptapGachaSummary
from ..utils.sdk.tajiduo_model import TajiduoGachaSummary
from ..utils.sdk.xiaoheihe_model import LotteryAnalysis


def tap_to_nte(summary: TaptapGachaSummary) -> NTEGachaSummary:
    overview = (
        NTEGachaOverview(
            total_pull_count=summary.overview.total_pull_count,
            total_ssr_count=summary.overview.total_ssr_count,
        )
        if summary.overview is not None
        else None
    )

    sections = [
        NTEGachaSection(
            banner_name=sec.banner_name,
            banner_type=sec.banner_type,
            begin_time_ts=sec.begin_time_ts,
            end_time_ts=sec.end_time_ts,
            total_pull_count=sec.total_pull_count,
            ssr_count=sec.ssr_count,
            avg_pity=sec.avg_pity,
            items=[
                NTEGachaItem(
                    item_id=item.item_id,
                    item_name=item.item_name,
                    pity=item.item_count,
                    pull_time_ts=item.pull_time_ts,
                )
                for item in sec.items
            ],
        )
        for sec in summary.sections
    ]

    return NTEGachaSummary(
        overview=overview,
        sections=sections,
        last_updated_ts=summary.last_updated_ts,
    )


def xhh_to_nte(analysis: LotteryAnalysis) -> NTEGachaSummary:
    si = analysis.statistic_info
    total_ssr = sum(p.ssr for p in si.pool_stats)
    total_pull = si.total_limit_cost + si.total_permanent_cost + si.total_fork_cost

    overview = NTEGachaOverview(
        total_pull_count=total_pull,
        total_ssr_count=total_ssr,
    )

    pool_cost_map: dict[str, int] = {}
    for p in si.pool_stats:
        pool_cost_map[p.pool] = p.cost
        pool_cost_map[p.pool.strip()] = p.cost

    sections = [
        NTEGachaSection(
            banner_name=pool.pool_type,
            banner_type=pool.pool_type,
            total_pull_count=pool_cost_map.get(pool.pool_type, pool_cost_map.get(pool.pool_type.strip(), 0)),
            ssr_count=len(pool.records),
            avg_pity=int(
                float(pool_cost_map.get(pool.pool_type, pool_cost_map.get(pool.pool_type.strip(), 0)))
                / max(len(pool.records), 1)
            ),
            items=[
                NTEGachaItem(
                    item_id=r.item_id,
                    item_name=r.name,
                    pity=r.diff,
                    pull_time_ts=r.timestamp,
                )
                for r in pool.records
            ],
        )
        for pool in analysis.gacha_record
    ]

    return NTEGachaSummary(
        overview=overview,
        sections=sections,
        last_updated_ts=analysis.update_time,
        luck_title=si.temp_title,
    )


def tjd_to_nte(summary: TajiduoGachaSummary) -> NTEGachaSummary:
    """塔吉多官方抽卡分析 → NTE 通用 schema。

    item_name 走 char_meta/fork_meta 反查（接口本身不返）；timeStamp 毫秒转秒；
    avg_pity 字符串 '56.0' → 56；池 begin/end 接口不给，留 0。
    """
    total_pull = sum(p.drawCount for p in summary.gachaDetails)
    total_ssr = sum(p.rareCount for p in summary.gachaDetails)
    overview = NTEGachaOverview(total_pull_count=total_pull, total_ssr_count=total_ssr) if total_pull > 0 else None

    sections = [
        NTEGachaSection(
            banner_name=pool.tab,
            banner_type=pool.tab,
            total_pull_count=pool.drawCount,
            ssr_count=pool.rareCount,
            avg_pity=int(float(pool.average)) if pool.average else 0,
            items=[
                NTEGachaItem(
                    item_id=d.charid,
                    item_name=name_by_id(d.charid),
                    pity=d.rareCount,
                    pull_time_ts=d.timeStamp // 1000,
                )
                for d in pool.details
            ],
        )
        for pool in summary.gachaDetails
    ]

    return NTEGachaSummary(
        overview=overview,
        sections=sections,
        last_updated_ts=int(time.time()),
        luck_title=summary.luckTitle,
    )
