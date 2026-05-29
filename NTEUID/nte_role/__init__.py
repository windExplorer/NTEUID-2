from gsuid_core.sv import SV
from gsuid_core.aps import scheduler
from gsuid_core.bot import Bot
from gsuid_core.models import Event

from .rank_service import run_bot_rank, run_character_rank
from .role_service import (
    run_explore,
    run_realtime,
    run_vehicles,
    run_role_home,
    run_realestate,
    run_achievement,
    run_character_detail,
    run_refresh_role_panel,
)
from .stamina_push import (
    check_stamina_push,
    run_subscribe_stamina,
    run_unsubscribe_stamina,
    run_unsubscribe_all_stamina,
    run_delete_all_stamina_subscriptions,
)
from ..utils.constants import COMMAND_NAME_PATTERN
from ..nte_config.nte_config import NTEConfig

sv_nte_role_home = SV("nte角色面板")
sv_nte_role_refresh = SV("nte刷新面板")
sv_nte_role_detail = SV("nte角色详情")
sv_nte_role_rank = SV("nte角色评分排名")
sv_nte_achievement = SV("nte成就进度")
sv_nte_realestate = SV("nte房产")
sv_nte_vehicle = SV("nte载具")
sv_nte_explore = SV("nte探索详情")
sv_nte_realtime = SV("nte实时信息")
sv_nte_stamina_sub = SV("nte体力订阅")
sv_nte_stamina_admin = SV("nte体力订阅管理", pm=1)


_STAMINA_CHECK_MIN = min(60, max(5, int(NTEConfig.get_config("NTEStaminaCheckMinutes").data)))


@sv_nte_role_home.on_fullmatch(("查询", "卡片", "角色", "信息"), block=True)
async def nte_role_home(bot: Bot, ev: Event):
    await run_role_home(bot, ev)


@sv_nte_role_refresh.on_fullmatch(
    (
        "刷新面板",
        "刷新面版",
        "更新面板",
        "更新面版",
        "强制刷新",
        "面板刷新",
        "面板更新",
        "面板",
        "面版",
    ),
    block=True,
)
async def nte_role_refresh(bot: Bot, ev: Event):
    await run_refresh_role_panel(bot, ev)


@sv_nte_role_detail.on_regex(
    rf"^(?P<char_name>{COMMAND_NAME_PATTERN})(面板|信息|详情|面包|🍞)$",
    block=True,
)
async def nte_role_detail(bot: Bot, ev: Event):
    await run_character_detail(bot, ev, ev.regex_dict["char_name"])


@sv_nte_role_rank.on_regex(
    # scope: bot = 全服，群/空 = 本群；排名/排行/排行榜、可选「评分」都触发；一个 handler 内分发避免歧义
    rf"^(?P<char_name>{COMMAND_NAME_PATTERN}?)(?P<scope>bot|群)?(?:评分)?(?:排名|排行榜|排行)$",
    block=True,
)
async def nte_role_rank(bot: Bot, ev: Event):
    char_name = ev.regex_dict["char_name"]
    if ev.regex_dict.get("scope") == "bot":
        await run_bot_rank(bot, ev, char_name)
    else:
        await run_character_rank(bot, ev, char_name)


@sv_nte_achievement.on_fullmatch(("成就进度", "成就"))
async def nte_achievement(bot: Bot, ev: Event):
    await run_achievement(bot, ev)


@sv_nte_realestate.on_fullmatch(("我的房产", "房产"))
async def nte_realestate(bot: Bot, ev: Event):
    await run_realestate(bot, ev)


@sv_nte_vehicle.on_fullmatch(("我的载具", "载具"))
async def nte_vehicle(bot: Bot, ev: Event):
    await run_vehicles(bot, ev)


@sv_nte_explore.on_fullmatch(("探索详情", "探索度", "探索"))
async def nte_explore(bot: Bot, ev: Event):
    await run_explore(bot, ev)


@sv_nte_realtime.on_fullmatch(("体力", "活力", "mr"))
async def nte_realtime(bot: Bot, ev: Event):
    await run_realtime(bot, ev)


@sv_nte_stamina_sub.on_regex(r"^(订阅体力推送|订阅体力|体力订阅)\s*(?P<threshold>\d*)$")
async def nte_sub_stamina(bot: Bot, ev: Event):
    await run_subscribe_stamina(bot, ev, ev.regex_dict.get("threshold", ""))


@sv_nte_stamina_sub.on_fullmatch(("取消订阅体力", "退订体力", "取消体力订阅"))
async def nte_unsub_stamina(bot: Bot, ev: Event):
    await run_unsubscribe_stamina(bot, ev)


@sv_nte_stamina_sub.on_fullmatch(("取消全部订阅体力", "退订全部体力", "取消全部体力订阅"))
async def nte_unsub_all_stamina(bot: Bot, ev: Event):
    await run_unsubscribe_all_stamina(bot, ev)


@sv_nte_stamina_admin.on_fullmatch(("删除所有体力订阅", "清空体力订阅"))
async def nte_delete_all_stamina_subscriptions(bot: Bot, ev: Event):
    await run_delete_all_stamina_subscriptions(bot, ev)


@scheduler.scheduled_job("interval", minutes=_STAMINA_CHECK_MIN, id="nte_stamina_push")
async def nte_stamina_push_job():
    await check_stamina_push()
