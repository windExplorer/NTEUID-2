from gsuid_core.sv import SV
from gsuid_core.bot import Bot
from gsuid_core.models import Event

from .alias_service import run_alias_list, run_alias_action
from ..utils.constants import COMMAND_NAME_PATTERN

sv_nte_alias = SV("nte别名", pm=0, priority=0)
sv_nte_alias_list = SV("nte别名列表")


@sv_nte_alias.on_regex(
    rf"^(?P<action>添加|删除)(角色|武器)?(?P<name>{COMMAND_NAME_PATTERN})别名(?P<new_alias>{COMMAND_NAME_PATTERN})$",
    block=True,
)
async def nte_alias_action(bot: Bot, ev: Event):
    await run_alias_action(
        bot,
        ev,
        ev.regex_dict["action"],
        ev.regex_dict["name"],
        ev.regex_dict["new_alias"],
    )


@sv_nte_alias_list.on_regex(
    rf"^(?P<name>{COMMAND_NAME_PATTERN})别名(列表)?$",
    block=True,
)
async def nte_alias_list(bot: Bot, ev: Event):
    await run_alias_list(bot, ev, ev.regex_dict["name"])
