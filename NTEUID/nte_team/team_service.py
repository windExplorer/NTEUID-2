from __future__ import annotations

from gsuid_core.bot import Bot
from gsuid_core.logger import logger
from gsuid_core.models import Event

from .team_card import draw_team_img
from ..utils.msgs import TeamMsg, send_nte_notify
from ..utils.sdk.tajiduo import tajiduo_web
from ..utils.database import NTEUser
from ..utils.name_convert import CHARS, name_of_with_uid
from ..utils.sdk.tajiduo_model import TajiduoError, TeamRecommendation


def _filter_recommendations(
    recommendations: list[TeamRecommendation],
    std_char_name: str,
    char_id: str,
) -> list[TeamRecommendation]:
    result: list[TeamRecommendation] = []
    for recommendation in recommendations:
        recommendation_name = CHARS.name_of(recommendation.name)
        if recommendation_name is None:
            recommendation_name = recommendation.name
        if recommendation.id == char_id or recommendation_name == std_char_name:
            result.append(recommendation)
    return result


async def run_team(bot: Bot, ev: Event, char_name: str) -> None:
    if not char_name:
        return await send_nte_notify(bot, ev, TeamMsg.usage_detail())

    # 动态别名：用请求者的 game uid 解析主角/鉴定师/异能者
    requester_uids = await NTEUser.uids_of_user(ev.user_id, ev.bot_id)
    requester_uid = next(iter(requester_uids), "") if requester_uids else ""
    resolved = await name_of_with_uid(char_name, requester_uid)
    std_char_name = CHARS.name_of(resolved or char_name)
    if not std_char_name:
        return await send_nte_notify(bot, ev, TeamMsg.CHAR_NOT_FOUND)
    char_id = CHARS.id_of(std_char_name)
    if not char_id:
        return await send_nte_notify(bot, ev, TeamMsg.CHAR_NOT_FOUND)

    try:
        recs = await tajiduo_web.get_team_recommendations()
    except TajiduoError as error:
        logger.warning(f"[NTE配队] 拉取失败: {error.message}")
        return await send_nte_notify(bot, ev, TeamMsg.LOAD_FAILED)

    if not recs:
        return await send_nte_notify(bot, ev, TeamMsg.EMPTY)

    matched = _filter_recommendations(recs, std_char_name, char_id)
    if not matched:
        return await send_nte_notify(bot, ev, TeamMsg.NO_RECOMMENDATION)

    await bot.send(await draw_team_img(matched, std_char_name))
