from __future__ import annotations

from gsuid_core.bot import Bot
from gsuid_core.logger import logger
from gsuid_core.models import Event

from .adapters import xhh_to_nte
from .gacha_card import draw_gacha_summary_img
from ..utils.msgs import GachaMsg, send_nte_notify
from ..utils.sdk.xiaoheihe import XiaoheiheClient
from ..utils.sdk.xiaoheihe_model import XiaoheiheError


async def send_xhh_summary_by_pkey(
    bot: Bot,
    ev: Event,
    *,
    pkey: str,
) -> None:
    """直查小黑盒 user_pkey → 渲染抽卡卡。不需要先在 NTEUID 内绑定。"""
    client = XiaoheiheClient(pkey=pkey)
    try:
        analysis = await client.lottery_analysis()
    except XiaoheiheError as err:
        logger.warning(f"[NTE抽卡] 小黑盒 user_key 直查失败 user_id={ev.user_id} err={err.message}")
        if "重新登录" in err.message or "relogin" in err.message:
            return await send_nte_notify(bot, ev, GachaMsg.XHH_PKEY_EXPIRED)
        return await send_nte_notify(bot, ev, GachaMsg.LOAD_FAILED)

    if not analysis.is_bind:
        return await send_nte_notify(bot, ev, GachaMsg.XHH_TARGET_NOT_BOUND)
    role_name = analysis.header_info.name
    if analysis.is_empty:
        return await send_nte_notify(bot, ev, GachaMsg.empty(role_name))

    summary = xhh_to_nte(analysis)
    role_id = analysis.header_info.uid
    img = await draw_gacha_summary_img(ev, summary, role_name=role_name, role_id=role_id)
    await bot.send(img)
