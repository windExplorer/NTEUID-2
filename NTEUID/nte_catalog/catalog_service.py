from __future__ import annotations

from pathlib import Path

from gsuid_core.bot import Bot
from gsuid_core.logger import logger
from gsuid_core.models import Event
from gsuid_core.utils.image.convert import convert_img

from ..utils.msgs import CatalogMsg, send_nte_notify
from ..utils.name_convert import alias_to_char_name, char_name_to_char_id
from ..utils.resource.RESOURCE_PATH import CATALOG_CHAR_PATH


async def run_char_catalog(bot: Bot, ev: Event, char_name: str) -> None:
    real_name = alias_to_char_name(char_name)
    if not real_name:
        return await send_nte_notify(bot, ev, CatalogMsg.CHAR_NOT_FOUND.format(char_name=char_name))

    char_id = char_name_to_char_id(real_name)
    if not char_id:
        return await send_nte_notify(bot, ev, CatalogMsg.CHAR_NOT_FOUND.format(char_name=char_name))

    paths = _char_catalog_paths(char_id)
    if not all(path.is_file() for path in paths):
        return await send_nte_notify(bot, ev, CatalogMsg.EMPTY.format(char_name=real_name))

    logger.info(f"[NTE图鉴] 发送 {real_name} 角色图鉴")
    await bot.send([await convert_img(path) for path in paths])


def _char_catalog_paths(char_id: str) -> list[Path]:
    return [
        CATALOG_CHAR_PATH / f"{char_id}_abilities.webp",
        CATALOG_CHAR_PATH / f"{char_id}_awaken.webp",
    ]
