from __future__ import annotations

from typing import Literal

from gsuid_core.bot import Bot
from gsuid_core.logger import logger
from gsuid_core.models import Event

from .adapters import tap_to_nte
from .gacha_card import draw_gacha_summary_img
from ..utils.msgs import GachaMsg, send_nte_notify
from ..utils.sdk.base import SdkError
from ..utils.sdk.taptap import taptap

TapSummaryResult = Literal["sent", "not_bound", "failed", "empty"]


async def send_tap_summary(
    bot: Bot,
    ev: Event,
    *,
    tap_id: int,
) -> TapSummaryResult:
    """直查 TapTap user_id → 渲染抽卡卡。不需要先在 NTEUID 内绑定。"""
    try:
        binding = await taptap.check_binding(tap_id)
    except SdkError as err:
        logger.warning(f"[NTE抽卡] TapTap 查询失败 user_id={ev.user_id} tap_id={tap_id} err={err.message}")
        await send_nte_notify(bot, ev, GachaMsg.LOAD_FAILED)
        return "failed"
    if not binding.is_bind:
        await send_nte_notify(bot, ev, GachaMsg.TAPTAP_NOT_BOUND)
        return "not_bound"

    try:
        tap_summary = await taptap.gacha_summary(tap_id)
    except SdkError as err:
        logger.warning(f"[NTE抽卡] TapTap 抽卡总览失败 user_id={ev.user_id} tap_id={tap_id} err={err.message}")
        await send_nte_notify(bot, ev, GachaMsg.LOAD_FAILED)
        return "failed"
    summary = tap_to_nte(tap_summary)
    if summary.is_empty:
        await send_nte_notify(bot, ev, GachaMsg.empty(binding.name))
        return "empty"

    img = await draw_gacha_summary_img(ev, summary, role_name=binding.name, role_id=binding.role_id)
    await bot.send(img)
    return "sent"


def _normalize_tap_id(arg: str) -> int | None:
    arg = arg.strip()
    return int(arg) if arg.isdigit() else None
