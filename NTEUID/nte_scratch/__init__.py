"""猫亭刮刮乐 — 指令注册。

指令列表：
  添加刮刮乐ck <cookie>  — 私聊绑定 kf cookie，自动抓取数据
  更新刮刮乐                 — 刷新刮刮乐数据
  刮刮乐                     — 查看累计统计
  今日刮刮乐                 — 查看今日刮刮乐数据
"""
from __future__ import annotations

from pathlib import Path

from gsuid_core.sv import SV
from gsuid_core.aps import scheduler
from gsuid_core.bot import Bot
from gsuid_core.models import Event
from gsuid_core.segment import MessageSegment

from .scratch_service import (
    bind_and_fetch,
    refresh_data,
    show_stats,
    show_today,
    delete_ck,
    auto_refresh_all,
)
from .scratch_card import draw_scratch_stats, draw_scratch_today, draw_scratch_rank

sv_scratch_bind = SV("nte刮刮乐绑定")
sv_scratch = SV("nte刮刮乐")

COOKIE_HELP = "请私聊发送：添加刮刮乐ck oauth=xxx; ..."

_COOKIE_GUIDE_NODE = MessageSegment.node([
    MessageSegment.text(
        "方法一（推荐 · 安卓专属）\n"
        "发送【nteck软件】下载 Cookie 提取工具\n"
        "安装后会自动打开登录页面\n"
        "登录完成后点右下角按钮即可复制完整 Cookie\n"
        "再回来发送：添加刮刮乐ck <粘贴>"
    ),
    MessageSegment.text(
        "方法二（安卓/IOS通用 · 手动下载）\n"
        "浏览器打开下方链接下载 APK：\n"
        "https://github.com/windExplorer/cookies-extractor/releases\n"
        "下载安装后操作同方法一"
    ),
    MessageSegment.text(
        "方法三（手动获取 · 安卓/IOS/PC）\n"
        "1. 浏览器打开 https://kf.wanmei.com/selfItemFlowQuery?gameId=191\n"
        "2. 登录后在网页请求中找到任意一条请求\n"
        "3. 复制请求头中 Cookie 的完整值\n"
        "4. 回来发送：添加刮刮乐ck <粘贴>"
    ),
])


@sv_scratch_bind.on_regex(r"^添加刮刮乐ck\s*(?P<cookie>.+)$", block=True)
async def nte_scratch_bind(bot: Bot, ev: Event):
    cookie = ev.regex_dict["cookie"]
    if ev.group_id:
        return await bot.send("⚠️ 添加刮刮乐 ck 涉及 cookie 隐私，请私聊机器人操作！")
    msg = await bind_and_fetch(ev.user_id, ev.bot_id, cookie)
    await bot.send(msg)


@sv_scratch_bind.on_fullmatch(("添加刮刮乐ck"), block=True)
async def nte_scratch_bind_empty(bot: Bot, ev: Event):
    """只发了"添加刮刮乐ck"没带参数时显示合并转发帮助"""
    if ev.group_id:
        return await bot.send("⚠️ 添加刮刮乐 ck 涉及 cookie 隐私，请私聊机器人操作！")
    await bot.send([_COOKIE_GUIDE_NODE])


@sv_scratch.on_fullmatch(("更新刮刮乐", "刷新刮刮乐"))
async def nte_scratch_refresh(bot: Bot, ev: Event):
    msg = await refresh_data(ev.user_id, ev.bot_id)
    await bot.send(msg)


@sv_scratch.on_fullmatch(("刮刮乐统计", "刮刮乐图表", "刮刮乐"))
async def nte_scratch_stats(bot: Bot, ev: Event):
    res = await draw_scratch_stats(ev.user_id, ev.bot_id)
    if isinstance(res, str):
        await bot.send(res)
    else:
        await bot.send(MessageSegment.image(res))


@sv_scratch.on_fullmatch(("今日刮刮乐", "今天刮刮乐"))
async def nte_scratch_today(bot: Bot, ev: Event):
    res = await draw_scratch_today(ev.user_id, ev.bot_id)
    if isinstance(res, str):
        await bot.send(res)
    else:
        await bot.send(MessageSegment.image(res))


@sv_scratch.on_fullmatch(("刮刮乐打榜", "刮刮乐排行全服"))
async def nte_scratch_rank(bot: Bot, ev: Event):
    res = await draw_scratch_rank()
    if isinstance(res, str):
        await bot.send(res)
    else:
        await bot.send(MessageSegment.image(res))


@sv_scratch.on_fullmatch(("ck软件", "获取ck软件"))
async def nte_scratch_apk(bot: Bot, ev: Event):
    apk_dir = Path(__file__).parent
    apks = list(apk_dir.glob("*.apk"))
    if not apks:
        return await bot.send("ck 提取工具暂未上传，请联系管理员。")
    await bot.send(Message.file(apks[0], "CK获取工具.apk"))
async def nte_scratch_delete(bot: Bot, ev: Event):
    msg = await delete_ck(ev.user_id, ev.bot_id)
    await bot.send(msg)


@scheduler.scheduled_job("cron", hour=6, minute=0, id="nte_scratch_auto_refresh")
async def nte_scratch_auto_refresh():
    """每日 6:00 自动刷新所有用户的刮刮乐数据。"""
    await auto_refresh_all()
