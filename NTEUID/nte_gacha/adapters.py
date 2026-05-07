from __future__ import annotations

from .gacha_model import (
    NTEGachaItem,
    NTEGachaSection,
    NTEGachaSummary,
    NTEGachaOverview,
)
from ..utils.sdk.taptap_model import GachaSummary as TaptapGachaSummary
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
