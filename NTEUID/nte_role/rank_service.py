from __future__ import annotations

import json

from gsuid_core.bot import Bot
from gsuid_core.models import Event

from .rank_card import RankEntry, draw_rank_img
from ..utils.msgs import RankMsg, CharacterMsg, send_nte_notify
from ..utils.database import NTEUser, NTECharData, NTEGroupMember
from ..utils.name_convert import CHARS
from ..utils.sdk.tajiduo_model import CharacterDetail

MAX_ENTRIES = 20


async def _send_rank(
    bot: Bot,
    ev: Event,
    char_name: str,
    *,
    scope_label: str,
    uids: list[str] | None,
    group_identity: dict[str, tuple[str, str]] | None = None,
) -> None:
    """uids 给定 = 本群排名；为 None = bot排名。
    身份查询全部按集合大小封顶：本群直接用群表身份；全服只查"自己的 uid"(定位自己) +
    展示 ≤21 行的身份——绝不对全表 ranked 做 IN 反查（会撞 SQLite 变量上限且没必要）。
    """
    std_char_name = CHARS.name_of(char_name)
    char_id = CHARS.id_of(std_char_name) if std_char_name else None
    if not std_char_name or not char_id:
        return await send_nte_notify(bot, ev, CharacterMsg.NOT_FOUND)

    ranked = await NTECharData.rank_for_char(char_id, uids)  # [(uid, score, grade)] desc
    if not ranked:
        return await send_nte_notify(bot, ev, RankMsg.NO_SCORE)

    if group_identity is not None:
        self_uids = {uid for uid, (owner, _) in group_identity.items() if owner == ev.user_id}
    else:
        self_uids = await NTEUser.uids_of_user(ev.user_id, ev.bot_id)
    self_index = next((i for i, (uid, _, _) in enumerate(ranked) if uid in self_uids), None)

    show = ranked[:MAX_ENTRIES]
    need = [uid for uid, _, _ in show]
    overflow = ranked[self_index] if self_index is not None and self_index >= MAX_ENTRIES else None
    if overflow is not None:
        need.append(overflow[0])

    # 群排名身份来自群表；全服排名只查展示行（≤21）身份
    identity = group_identity if group_identity is not None else await NTEUser.identity_by_uids(need)
    details = await NTECharData.details_for(need, char_id)

    def build(row: tuple[str, int, str]) -> RankEntry:
        uid, score, grade = row
        user_id, role_name = identity.get(uid, ("", ""))  # 无身份(孤儿)：user_id 空→头像回退角色头像、名字留空
        char = CharacterDetail.model_validate(json.loads(details[uid]))
        suit = char.suit
        return RankEntry(
            user_id, role_name, uid, char.awaken_lev, suit.id, suit.name, suit.suit_activate_num, score, grade
        )

    shown = [build(row) for row in show]
    self_overflow = (self_index + 1, build(overflow)) if overflow is not None and self_index is not None else None
    await bot.send(await draw_rank_img(ev, std_char_name, char_id, shown, len(ranked), scope_label, self_overflow))


async def run_character_rank(bot: Bot, ev: Event, char_name: str) -> None:
    """本群评分排名：先取本群登记过的号，再按号查分。"""
    if not char_name:
        return await send_nte_notify(bot, ev, RankMsg.usage())
    if not ev.group_id:
        return await send_nte_notify(bot, ev, RankMsg.GROUP_ONLY)
    members = await NTEGroupMember.list_members(ev.group_id, ev.bot_id)
    if not members:
        return await send_nte_notify(bot, ev, RankMsg.NO_MEMBER)
    identity = {m.uid: (m.user_id, m.role_name) for m in members}
    await _send_rank(bot, ev, char_name, scope_label="本群", uids=list(identity), group_identity=identity)


async def run_bot_rank(bot: Bot, ev: Event, char_name: str) -> None:
    """bot评分排名：直接扫全表，不按群。"""
    if not char_name:
        return await send_nte_notify(bot, ev, RankMsg.usage_bot())
    await _send_rank(bot, ev, char_name, scope_label="bot", uids=None)
