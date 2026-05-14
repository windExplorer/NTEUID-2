from __future__ import annotations

from gsuid_core.bot import Bot
from gsuid_core.models import Event

from .adapters import tjd_to_nte
from .gacha_card import draw_gacha_summary_img
from ..utils.msgs import GachaMsg, CommonMsg, send_nte_notify
from .tap_service import send_tap_summary, _normalize_tap_id
from .xhh_service import send_xhh_summary_by_pkey
from ..utils.session import SessionCall
from ..utils.sdk.xiaoheihe import extract_heybox_id_from_pkey


async def run_my_gacha(bot: Bot, ev: Event, query: str = "") -> None:
    query = query.strip()
    if query:
        return await _run_direct_query(bot, ev, query)
    await _run_tajiduo(bot, ev)


async def _run_direct_query(bot: Bot, ev: Event, query: str) -> None:
    tap_id = _normalize_tap_id(query)
    if tap_id is not None:
        await send_tap_summary(bot, ev, tap_id=tap_id)
        return
    if extract_heybox_id_from_pkey(query):
        await send_xhh_summary_by_pkey(bot, ev, pkey=query)
        return
    await send_nte_notify(bot, ev, GachaMsg.INVALID_QUERY)


async def _run_tajiduo(bot: Bot, ev: Event) -> None:
    async with SessionCall(
        bot,
        ev,
        tag="抽卡记录",
        not_logged_in_msg=CommonMsg.not_logged_in(),
        login_expired_msg=CommonMsg.login_expired(),
        load_failed_msg=GachaMsg.LOAD_FAILED,
    ) as session:
        if session is None:
            return
        user, client = session
        summary = tjd_to_nte(await client.get_gacha_summary())
        if summary.is_empty:
            return await send_nte_notify(bot, ev, GachaMsg.empty(user.role_name))
        img = await draw_gacha_summary_img(ev, summary, role_name=user.role_name, role_id=user.uid)
        await bot.send(img)
