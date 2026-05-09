from __future__ import annotations

from gsuid_core.bot import Bot
from gsuid_core.models import Event

from ..utils.msgs import AliasMsg, send_nte_notify
from ..utils.name_convert import alias_to_entity


async def run_alias_action(
    bot: Bot,
    ev: Event,
    action: str,
    name: str,
    new_alias: str,
) -> None:
    if not name or not new_alias:
        return await send_nte_notify(bot, ev, AliasMsg.EMPTY_NAME_OR_ALIAS)

    hit = alias_to_entity(name)
    if hit is None:
        return await send_nte_notify(bot, ev, AliasMsg.NOT_FOUND.format(name=name))
    reg, std_name, entity_id = hit

    if action == "添加":
        # 别名跨池唯一：撞上角色或武器现有别名都阻断
        existing = alias_to_entity(new_alias)
        if existing is not None:
            ex_reg, ex_name, _ = existing
            return await send_nte_notify(
                bot,
                ev,
                AliasMsg.ALIAS_IN_USE.format(alias=new_alias, kind=ex_reg.label, name=ex_name),
            )
        reg.add_alias(entity_id, new_alias)
        return await send_nte_notify(
            bot,
            ev,
            AliasMsg.ADD_SUCCESS.format(kind=reg.label, name=std_name, alias=new_alias),
        )

    if action == "删除":
        if not reg.remove_alias(entity_id, new_alias):
            return await send_nte_notify(bot, ev, AliasMsg.ALIAS_NOT_REMOVABLE.format(alias=new_alias))
        return await send_nte_notify(
            bot,
            ev,
            AliasMsg.DEL_SUCCESS.format(kind=reg.label, name=std_name, alias=new_alias),
        )

    return await send_nte_notify(bot, ev, AliasMsg.INVALID_ACTION)


async def run_alias_list(bot: Bot, ev: Event, name: str) -> None:
    if not name:
        return await send_nte_notify(bot, ev, AliasMsg.usage_list())

    hit = alias_to_entity(name)
    if hit is None:
        return await send_nte_notify(bot, ev, AliasMsg.NOT_FOUND.format(name=name))
    reg, std_name, _ = hit

    aliases = reg.aliases_of(std_name)
    if not aliases:
        return await send_nte_notify(bot, ev, AliasMsg.NOT_FOUND.format(name=name))

    await send_nte_notify(
        bot,
        ev,
        f"{reg.label}【{std_name}】别名列表：\n" + "\n".join(aliases),
    )
