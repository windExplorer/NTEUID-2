"""猫亭刮刮乐 — 指令注册。

指令列表（均带 nte 前缀）：
  nte添加刮刮乐ck <cookie>  — 私聊绑定 kf cookie，自动抓取数据
  nte更新刮刮乐                 — 刷新刮刮乐数据
  nte刮刮乐                     — 查看累计统计
  nte今日刮刮乐                 — 查看今日刮刮乐数据
"""
from __future__ import annotations

from pathlib import Path

from gsuid_core.sv import SV
from gsuid_core.aps import scheduler
from gsuid_core.bot import Bot
from gsuid_core.models import Event
from gsuid_core.segment import MessageSegment, Message

from .scratch_service import (
    bind_and_fetch,
    refresh_data,
    refresh_user_data,
    show_stats,
    show_today,
    delete_ck,
    auto_refresh_all,
)
from ..utils.database import NTEKfCookie, NTEUser
from .scratch_card import draw_scratch_stats, draw_scratch_today, draw_scratch_rank

sv_scratch_bind = SV("nte刮刮乐绑定")
sv_scratch = SV("nte刮刮乐")
# 管理员专用（pm=1=superuser），隐藏指令：不写入帮助文档
sv_scratch_admin = SV("nte刮刮乐管理", pm=1)

COOKIE_HELP = "请私聊发送：nte添加刮刮乐ck oauth=xxx; ..."

_COOKIE_GUIDE_NODE = MessageSegment.node([
    MessageSegment.text(
        "方法一（推荐 · 安卓专属）\n"
        "发送【nteck软件】下载 Cookie 提取工具\n"
        "安装后会自动打开登录页面\n"
        "登录完成后点右下角按钮即可复制完整 Cookie\n"
        "再回来发送：nte添加刮刮乐ck <粘贴>"
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
        "4. 回来发送：nte添加刮刮乐ck <粘贴>"
    ),
])


@sv_scratch_bind.on_regex(r"^添加刮刮乐ck\s*(?P<cookie>.+)$", block=True)
async def nte_scratch_bind(bot: Bot, ev: Event):
    cookie = ev.regex_dict["cookie"]
    if ev.group_id:
        return await bot.send("请私聊发送该指令~")

    # 从数据库(NTEUser)查该用户的异环角色，不走 API
    roles = await NTEUser.list_primary_roles(ev.user_id, ev.bot_id)
    if not roles:
        return await bot.send("你还没有登录异环账号哦！请先使用【nte登录】指令登录后再【nte添加刮刮乐ck】。")

    if len(roles) == 1:
        role_id, _ = roles[0]
    else:
        # 多个异环号：列出 roleId + 角色名，等用户发数字选择
        lines = ["你绑定了多个异环账号，请发送序号选择要绑定刮刮乐的角色："]
        for i, (rid, rname) in enumerate(roles, 1):
            lines.append(f"{i}. {rname or '未知角色'}（{rid}）")
        resp = await bot.receive_resp("\n".join(lines))
        if resp is None:
            return await bot.send("等待超时，已取消绑定。请重新发送【nte添加刮刮乐ck】。")
        choice = (resp.text or "").strip()
        if not choice.isdigit() or not (1 <= int(choice) <= len(roles)):
            return await bot.send(f"无效的序号「{choice}」，已取消绑定。请重新发送【nte添加刮刮乐ck】。")
        role_id, _ = roles[int(choice) - 1]

    msg = await bind_and_fetch(ev.user_id, ev.bot_id, cookie, role_id)
    await bot.send(msg)


@sv_scratch_bind.on_fullmatch(("添加刮刮乐ck"), block=True)
async def nte_scratch_bind_empty(bot: Bot, ev: Event):
    """只发了"添加刮刮乐ck"没带参数时显示合并转发帮助"""
    if ev.group_id:
        return await bot.send("请私聊发送该指令~")
    await bot.send([_COOKIE_GUIDE_NODE])


@sv_scratch.on_fullmatch(("更新刮刮乐", "刷新刮刮乐"))
async def nte_scratch_refresh(bot: Bot, ev: Event):
    msg = await refresh_data(ev.user_id, ev.bot_id)
    await bot.send(msg)


@sv_scratch.on_fullmatch(("刮刮乐统计", "刮刮乐图表", "刮刮乐"))
async def nte_scratch_stats(bot: Bot, ev: Event):
    res = await draw_scratch_stats(ev)
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
    import base64
    apk_dir = Path(__file__).parent
    apks = list(apk_dir.glob("*.apk"))
    if not apks:
        return await bot.send("ck 提取工具暂未上传，请联系管理员。")
    apk_bytes = apks[0].read_bytes()
    b64 = base64.b64encode(apk_bytes).decode()
    await bot.send(Message(type="file", data=f"CK获取工具.apk|{b64}"))


@sv_scratch.on_fullmatch(("删除刮刮乐ck", "清除刮刮乐ck", "解绑刮刮乐"))
async def nte_scratch_delete(bot: Bot, ev: Event):
    msg = await delete_ck(ev.user_id, ev.bot_id)
    await bot.send(msg)


@scheduler.scheduled_job("cron", hour=6, minute=0, id="nte_scratch_auto_refresh")
async def nte_scratch_auto_refresh():
    """每日 6:00 自动刷新所有用户的刮刮乐数据。"""
    await auto_refresh_all()


# ── 管理员隐藏指令（pm=1，仅 superuser/master 可用）──
# 注意：不能用「查看」作为前缀，会与 nte_login 的 on_command("查看", block=True) 冲突
@sv_scratch_admin.on_regex(r"^强制刷新刮刮乐\s*(?P<target>\S+)$")
async def nte_scratch_admin_refresh(bot: Bot, ev: Event):
    target_user = ev.regex_dict["target"]
    msg = await refresh_user_data(target_user)
    await bot.send(msg)


@sv_scratch_admin.on_regex(r"^刮刮乐面板\s*(?P<target>\S+)$")
async def nte_scratch_admin_view(bot: Bot, ev: Event):
    target_user = ev.regex_dict["target"]
    rows = await NTEKfCookie.list_by_user_id(target_user)
    if not rows:
        return await bot.send(f"未找到用户 {target_user} 的刮刮乐绑定记录。")
    sent = 0
    for row in rows:
        role_label = row.uid or "?"
        if not row.raw_data or row.raw_data == "{}":
            await bot.send(f"角色 {role_label}（bot {row.bot_id}）：暂无刮刮乐数据")
            continue
        img = await draw_scratch_stats(user_id=row.user_id, bot_id=row.bot_id)
        if isinstance(img, str):
            await bot.send(img)
        else:
            await bot.send(MessageSegment.image(img))
            sent += 1
    if sent == 0:
        await bot.send(f"用户 {target_user} 共 {len(rows)} 个绑定账号，但都暂无数据。")
