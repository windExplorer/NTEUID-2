from gsuid_core.sv import SV
from gsuid_core.bot import Bot
from gsuid_core.models import Event

from .catalog_service import run_char_catalog
from ..utils.constants import COMMAND_NAME_PATTERN

sv_nte_catalog = SV("nte角色图鉴")


@sv_nte_catalog.on_regex(
    rf"^(?P<char_name>{COMMAND_NAME_PATTERN}?)(?:角色图鉴|图鉴|wiki|Wiki|WIKI)$",
    block=True,
)
async def nte_char_catalog(bot: Bot, ev: Event) -> None:
    await run_char_catalog(bot, ev, ev.regex_dict["char_name"])
