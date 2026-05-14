from gsuid_core.sv import SV
from gsuid_core.bot import Bot
from gsuid_core.models import Event
from gsuid_core.segment import MessageSegment

from .gacha_help import draw_gacha_help
from .gacha_service import run_my_gacha

sv_nte_my_gacha = SV("nte抽卡记录")
sv_nte_gacha_help = SV("nte抽卡帮助")


@sv_nte_my_gacha.on_command(("抽卡记录", "我的抽卡"), block=True)
async def nte_my_gacha_cmd(bot: Bot, ev: Event):
    await run_my_gacha(bot, ev, ev.text)


@sv_nte_gacha_help.on_fullmatch(("抽卡帮助", "抽卡说明"), block=True)
async def nte_gacha_help_cmd(bot: Bot, ev: Event):
    await bot.send(MessageSegment.node(await draw_gacha_help()))
