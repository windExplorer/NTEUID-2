from __future__ import annotations

from gsuid_core.bot import Bot
from gsuid_core.models import Event

from ..utils.at import AtTarget, resolve_at_target
from .role_card import draw_role_card_img
from .role_sort import diff_characters, sort_characters
from .role_cache import load_role_characters_cache, save_role_characters_cache
from ..utils.msgs import RoleMsg, send_nte_notify
from .explore_card import draw_explore_img
from .refresh_card import draw_refresh_img
from .vehicle_card import draw_vehicle_img
from .realtime_card import draw_realtime_img
from ..utils.session import SessionCall
from .character_card import draw_character_card_img
from ..utils.database import NTEUser
from .realestate_card import draw_realestate_img
from .achievement_card import draw_achievement_img
from ..utils.name_convert import CHARS
from ..utils.sdk.tajiduo_model import CharacterDetail


def _session_call(bot: Bot, ev: Event, target: AtTarget, *, tag: str, load_failed_msg: str) -> SessionCall:
    return SessionCall(
        bot,
        ev,
        tag=tag,
        target_user_id=target.user_id,
        not_logged_in_msg=RoleMsg.not_logged_in(target.is_other),
        login_expired_msg=RoleMsg.login_expired(target.is_other),
        load_failed_msg=load_failed_msg,
    )


async def run_role_home(bot: Bot, ev: Event) -> None:
    target = await resolve_at_target(bot, ev)
    if target is None:
        return
    async with _session_call(bot, ev, target, tag="角色面板", load_failed_msg=RoleMsg.LOAD_FAILED) as session:
        if session is None:
            return
        user, client = session
        home = await client.get_role_home(user.uid)
        characters = await load_role_characters_cache(user.uid)
        await bot.send(await draw_role_card_img(ev, home, characters, user.role_name))


async def run_character_detail(bot: Bot, ev: Event, char_name: str) -> None:
    if not char_name:
        return await send_nte_notify(bot, ev, RoleMsg.usage_detail())

    std_char_name = CHARS.name_of(char_name)
    if not std_char_name:
        return await send_nte_notify(bot, ev, RoleMsg.CHAR_NOT_FOUND)
    char_id = CHARS.id_of(std_char_name)
    if not char_id:
        return await send_nte_notify(bot, ev, RoleMsg.CHAR_NOT_FOUND)

    target = await resolve_at_target(bot, ev)
    if target is None:
        return

    user = await NTEUser.get_active(target.user_id, ev.bot_id)
    if user is None:
        has_history = await NTEUser.has_logged_in_history(target.user_id, ev.bot_id)
        return await send_nte_notify(bot, ev, RoleMsg.not_logged_in(target.is_other, has_history=has_history))

    characters = await load_role_characters_cache(user.uid)
    if not characters:
        return await send_nte_notify(bot, ev, RoleMsg.OTHER_LOCAL_EMPTY if target.is_other else RoleMsg.LOCAL_EMPTY)

    char = next((character for character in characters if character.id == char_id), None)
    if char is None:
        return await send_nte_notify(bot, ev, RoleMsg.CHAR_NOT_FOUND)

    await bot.send(await draw_character_card_img(ev, char, user.role_name, user.uid))


async def run_refresh_role_panel(bot: Bot, ev: Event) -> None:
    target = await resolve_at_target(bot, ev)
    if target is None:
        return
    async with _session_call(bot, ev, target, tag="刷新面板", load_failed_msg=RoleMsg.REFRESH_FAILED) as session:
        if session is None:
            return
        user, client = session
        home = await client.get_role_home(user.uid)
        raw_characters = await client.get_role_characters_data(user.uid)
        parsed_characters = [CharacterDetail.model_validate(item) for item in raw_characters]
        old_characters = await load_role_characters_cache(user.uid)
        changed_ids = diff_characters(parsed_characters, old_characters)
        await save_role_characters_cache(user.uid, raw_characters)
        sorted_characters = sort_characters(parsed_characters, changed_ids=changed_ids)
        await bot.send(await draw_refresh_img(ev, user.role_name, user.uid, home, sorted_characters, len(changed_ids)))


async def run_achievement(bot: Bot, ev: Event) -> None:
    target = await resolve_at_target(bot, ev)
    if target is None:
        return
    async with _session_call(bot, ev, target, tag="成就进度", load_failed_msg=RoleMsg.LOAD_FAILED) as session:
        if session is None:
            return
        user, client = session
        achievement = await client.get_role_achievement_progress(user.uid)
        if not achievement.detail:
            return await send_nte_notify(bot, ev, RoleMsg.EMPTY)
        await bot.send(await draw_achievement_img(ev, achievement, user.role_name, user.uid))


async def run_realestate(bot: Bot, ev: Event) -> None:
    target = await resolve_at_target(bot, ev)
    if target is None:
        return
    async with _session_call(bot, ev, target, tag="房产", load_failed_msg=RoleMsg.LOAD_FAILED) as session:
        if session is None:
            return
        user, client = session
        houses = await client.get_role_realestate(user.uid)
        if not houses:
            return await send_nte_notify(bot, ev, RoleMsg.EMPTY)
        await bot.send(await draw_realestate_img(ev, houses, user.role_name, user.uid))


async def run_realtime(bot: Bot, ev: Event) -> None:
    target = await resolve_at_target(bot, ev)
    if target is None:
        return
    async with _session_call(bot, ev, target, tag="实时信息", load_failed_msg=RoleMsg.LOAD_FAILED) as session:
        if session is None:
            return
        user, client = session
        home = await client.get_role_home(user.uid)
        await bot.send(await draw_realtime_img(ev, user, home))


async def run_explore(bot: Bot, ev: Event) -> None:
    target = await resolve_at_target(bot, ev)
    if target is None:
        return
    async with _session_call(bot, ev, target, tag="探索详情", load_failed_msg=RoleMsg.LOAD_FAILED) as session:
        if session is None:
            return
        user, client = session
        areas = await client.get_role_area_progress(user.uid)
        if not areas:
            return await send_nte_notify(bot, ev, RoleMsg.EMPTY)
        await bot.send(await draw_explore_img(ev, areas, user.role_name, user.uid))


async def run_vehicles(bot: Bot, ev: Event) -> None:
    target = await resolve_at_target(bot, ev)
    if target is None:
        return
    async with _session_call(bot, ev, target, tag="载具", load_failed_msg=RoleMsg.LOAD_FAILED) as session:
        if session is None:
            return
        user, client = session
        vehicles = await client.get_role_vehicles(user.uid)
        if not vehicles.detail:
            return await send_nte_notify(bot, ev, RoleMsg.EMPTY)
        await bot.send(await draw_vehicle_img(ev, vehicles, user.role_name, user.uid))
