"""猫亭刮刮乐 — 指令注册。

指令列表：
  添加刮刮乐ck <cookie>  — 私聊绑定 kf cookie，自动抓取数据
  更新刮刮乐                 — 刷新刮刮乐数据
  刮刮乐                     — 查看累计统计
  今日刮刮乐                 — 查看今日刮刮乐数据
"""
from __future__ import annotations

from gsuid_core.sv import SV
from gsuid_core.bot import Bot
from gsuid_core.models import Event

from .scratch_service import (
    bind_and_fetch,
    refresh_data,
    show_stats,
    show_today,
)

sv_scratch_bind = SV("nte刮刮乐绑定")
sv_scratch = SV("nte刮刮乐")

COOKIE_HELP = (
    "⚠️ 请私聊机器人操作，保护你的 cookie 隐私！\n\n"
    "💡 如何获取刮刮乐 ck？\n"
    "1. 浏览器打开 https://kf.wanmei.com/selfItemFlowQuery?gameId=191\n"
    "2. F12 → 网络 → 刷新页面 → 找到任意请求\n"
    "3. 复制请求头中的 Cookie 值（完整的一段）\n"
    "4. 私聊机器人发送：添加刮刮乐ck oauth=xxx; ..."
)


@sv_scratch_bind.on_regex(r"^添加刮刮乐ck\s*(?P<cookie>.+)$", block=True)
async def nte_scratch_bind(bot: Bot, ev: Event, cookie: str):
    if ev.group_id:
        return await bot.send("⚠️ 添加刮刮乐 ck 涉及 cookie 隐私，请私聊机器人操作！")
    msg = await bind_and_fetch(ev.user_id, ev.bot_id, cookie)
    await bot.send(msg)


@sv_scratch_bind.on_fullmatch(("添加刮刮乐ck"), block=True)
async def nte_scratch_bind_empty(bot: Bot, ev: Event):
    """只发了"添加刮刮乐ck"没带参数时显示帮助"""
    if ev.group_id:
        return await bot.send("⚠️ 添加刮刮乐 ck 涉及 cookie 隐私，请私聊机器人操作！")
    await bot.send(COOKIE_HELP)


@sv_scratch.on_fullmatch(("更新刮刮乐", "刷新刮刮乐"))
async def nte_scratch_refresh(bot: Bot, ev: Event):
    msg = await refresh_data(ev.user_id, ev.bot_id)
    await bot.send(msg)


@sv_scratch.on_fullmatch(("刮刮乐统计", "刮刮乐图表", "刮刮乐"))
async def nte_scratch_stats(bot: Bot, ev: Event):
    msg = await show_stats(ev.user_id, ev.bot_id)
    await bot.send(msg)


@sv_scratch.on_fullmatch(("今日刮刮乐", "今天刮刮乐"))
async def nte_scratch_today(bot: Bot, ev: Event):
    msg = await show_today(ev.user_id, ev.bot_id)
    await bot.send(msg)
