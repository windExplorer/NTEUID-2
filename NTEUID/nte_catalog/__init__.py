from gsuid_core.sv import SV
from gsuid_core.bot import Bot
from gsuid_core.models import Event

from .catalog_service import run_catalog, run_catalog_list
from ..utils.constants import COMMAND_NAME_PATTERN

sv_nte_catalog = SV("nte图鉴")
sv_nte_catalog_list = SV("nte图鉴列表")


@sv_nte_catalog.on_regex(
    rf"^(?P<name>{COMMAND_NAME_PATTERN}?)(?:角色图鉴|武器图鉴|图鉴|wiki|Wiki|WIKI)$",
    block=True,
)
async def nte_catalog_cmd(bot: Bot, ev: Event) -> None:
    await run_catalog(bot, ev, ev.regex_dict["name"])


@sv_nte_catalog_list.on_regex(r"^(?P<kind>角色|武器|图鉴)列表$", block=True)
async def nte_catalog_list_cmd(bot: Bot, ev: Event) -> None:
    await run_catalog_list(bot, ev, ev.regex_dict["kind"])
