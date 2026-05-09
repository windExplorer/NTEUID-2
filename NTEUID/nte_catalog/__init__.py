from gsuid_core.sv import SV
from gsuid_core.bot import Bot
from gsuid_core.models import Event

from .catalog_service import run_catalog
from ..utils.constants import COMMAND_NAME_PATTERN

sv_nte_catalog = SV("nte图鉴")


@sv_nte_catalog.on_regex(
    rf"^(?P<name>{COMMAND_NAME_PATTERN}?)(?:角色图鉴|武器图鉴|图鉴|wiki|Wiki|WIKI)$",
    block=True,
)
async def nte_catalog_cmd(bot: Bot, ev: Event) -> None:
    await run_catalog(bot, ev, ev.regex_dict["name"])
