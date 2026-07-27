"""猫亭刮刮乐 - 数据抓取与统计服务。

接口文档：
  POST https://kf.wanmei.com/selfItemFlowQuery/search
  - typeId=29, gameId=191, itemType=13, itemSubType=1, item5=110
  - 需 roleId(游戏角色id) + Cookie(kf.wanmei.com 会话)
"""
from __future__ import annotations

import re
import json
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from gsuid_core.logger import logger

from ..utils.database import NTEKfCookie

TZ_BEIJING = timezone(timedelta(hours=8))
BASE = "https://kf.wanmei.com"
URL_SEARCH = f"{BASE}/selfItemFlowQuery/search"
URL_PAGE = f"{BASE}/selfItemFlowQuery?gameId=191"
SLICE_DAYS = 7
PAGE_SIZE = 1000
PAGE_LIMIT = 50  # 防无限翻页

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
    "Referer": URL_PAGE,
    "X-Requested-With": "XMLHttpRequest",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
}

INFO_RE = re.compile(r"共计消耗(\d+)方斯.*?获得奖券奖励(\d+)方斯")


def _fmt(dt: datetime) -> str:
    return dt.astimezone(TZ_BEIJING).strftime("%Y-%m-%d %H:%M:%S")


def _fmt_date(d: datetime) -> str:
    return d.astimezone(TZ_BEIJING).strftime("%Y-%m-%d")


# ── 网络请求 ──


def _parse_cookie(cookie: str) -> dict[str, str]:
    """将 cookie 字符串解析为 {key: value} 字典。"""
    result: dict[str, str] = {}
    for item in cookie.split(";"):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            result[k.strip()] = v.strip()
    return result


async def _post_search(
    client: httpx.AsyncClient, cookie: str, role_id: str, start: datetime, end: datetime, page: int = 1
) -> dict[str, Any]:
    """调用 kf 查询接口，返回解析后的 {spent, income, raw}"""
    params = {
        "typeId": "29",
        "gameId": "191",
        "server": "",
        "roleId": role_id,
        "itemType": "13",
        "item1": "",
        "itemSubType": "1",
        "item4": "",
        "item5": "110",
        "item8": "",
        "item11": "",
        "item12": "",
        "startTime": _fmt(start),
        "endTime": _fmt(end),
        "pageNo": str(page),
        "pageSize": str(PAGE_SIZE),
    }
    # 逐个设置 cookie 避免 httpx 解析长 cookie 字符串出问题
    cookie_dict = _parse_cookie(cookie)
    resp = await client.post(
        URL_SEARCH, data=params, headers=HEADERS, cookies=cookie_dict, timeout=30
    )
    text = resp.text.replace("<pre>", "").replace("</pre>", "").strip()
    payload = json.loads(text)
    code = str(payload.get("code"))
    msg = payload.get("message") or ""
    if code == "1":
        if "没有查询到" in msg or "没有搜索到" in msg or "暂无" in msg:
            return {"spent": 0, "income": 0, "raw": text}
        raise RuntimeError(f"接口返回错误: {msg}")
    data = payload.get("data") or {}
    result = data.get("result") or []
    if isinstance(result, list) and len(result) == 0:
        return {"spent": 0, "income": 0, "raw": text}
    info = data.get("info") or ""
    m = INFO_RE.search(info)
    if not m:
        raise RuntimeError(f"无法解析 info: {info!r}")
    return {"spent": int(m.group(1)), "income": int(m.group(2)), "raw": text}


async def _fetch_slice(
    client: httpx.AsyncClient, cookie: str, role_id: str, start: datetime, end: datetime
) -> dict[str, Any]:
    """抓取一档（含接口内分页）。"""
    total = {"spent": 0, "income": 0}
    pages: list[str] = []
    for page in range(1, PAGE_LIMIT + 1):
        parsed = await _post_search(client, cookie, role_id, start, end, page)
        pages.append(parsed["raw"])
        if page == 1:
            total = {"spent": parsed["spent"], "income": parsed["income"]}
        data_obj = json.loads(parsed["raw"]).get("data") or {}
        result_list = data_obj.get("result")
        if not (isinstance(result_list, list) and len(result_list) >= PAGE_SIZE):
            break
    profit = total["income"] - total["spent"]
    return_rate = (total["income"] / total["spent"] * 100) if total["spent"] else None
    return {
        "start": _fmt(start),
        "end": _fmt(end),
        "spent": total["spent"],
        "income": total["income"],
        "profit": profit,
        "return_rate": return_rate,
        "pages": pages,
    }


def _build_slices(start: datetime, end: datetime) -> list[tuple[datetime, datetime]]:
    slices: list[tuple[datetime, datetime]] = []
    cursor = start
    while cursor < end:
        slice_end = min(end, cursor + timedelta(days=SLICE_DAYS) - timedelta(seconds=1))
        slices.append((cursor, slice_end))
        cursor = slice_end + timedelta(seconds=1)
    return slices


def _collect_records(slice_data: dict) -> list[dict]:
    """从 slice 的 pages 字段提取所有明细记录。"""
    records: list[dict] = []
    for page in slice_data.get("pages", []):
        if isinstance(page, str):
            page = json.loads(page)
        result = (page.get("data") or {}).get("result") or []
        if isinstance(result, list):
            records.extend(result)
    return records


# ── 公开接口 ──


async def fetch_scratch_data(cookie: str, role_id: str) -> dict[str, Any]:
    """抓取全部刮刮乐数据（从 2026-07-02 起），返回汇总结果。"""
    start = datetime(2026, 7, 2, 0, 0, 0, tzinfo=TZ_BEIJING)
    end = datetime.now(TZ_BEIJING)
    slices = _build_slices(start, end)
    results: list[dict] = []
    async with httpx.AsyncClient(verify=False) as client:
        for s, e in slices:
            logger.info(f"[刮刮乐] 抓取 {_fmt(s)} ~ {_fmt(e)}")
            rec = await _fetch_slice(client, cookie, role_id, s, e)
            rec["key"] = f"{s.strftime('%Y%m%d%H%M%S')}_{e.strftime('%Y%m%d%H%M%S')}"
            results.append(rec)
    total_spent = sum(r["spent"] for r in results)
    total_income = sum(r["income"] for r in results)
    total_profit = total_income - total_spent
    total_rate = (total_income / total_spent * 100) if total_spent else None
    summary = {
        "generated_at": _fmt(datetime.now(TZ_BEIJING)),
        "range_start": _fmt(start),
        "range_end": _fmt(end),
        "total_spent": total_spent,
        "total_income": total_income,
        "total_profit": total_profit,
        "total_return_rate": total_rate,
        "slice_count": len(results),
        "slices": [{k: v for k, v in r.items() if k != "pages"} for r in results],
        "pages": [p for r in results for p in r.get("pages", [])],
    }
    return summary


async def fetch_today_data(cookie: str, role_id: str) -> dict[str, Any] | None:
    """抓取当日刮刮乐数据（结束时间必须严格早于当前时间）。"""
    now = datetime.now(TZ_BEIJING)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = now - timedelta(minutes=1)  # 提前1分钟，API 要求 < 当前时间
    async with httpx.AsyncClient(verify=False) as client:
        rec = await _fetch_slice(client, cookie, role_id, start, end)
    if rec["spent"] == 0 and rec["income"] == 0:
        return None
    records = _collect_records(rec)
    return {**rec, "records": records}


def aggregate_records(summary: dict) -> dict:
    """从 summary 的 pages 中提取总记录统计。"""
    all_records: list[dict] = []
    for p in summary.get("pages", []):
        if isinstance(p, str):
            p = json.loads(p)
        result = (p.get("data") or {}).get("result") or []
        if isinstance(result, list):
            all_records.extend(result)
    award_counts: dict[str, int] = {}
    total_award_fangsi = 0
    for r in all_records:
        aw = r.get("award") or ""
        award_counts[aw] = award_counts.get(aw, 0) + 1
        m = re.search(r"方斯\*(\d+)", aw)
        if m:
            total_award_fangsi += int(m.group(1))
    return {
        "total_records": len(all_records),
        "award_counts": dict(sorted(award_counts.items(), key=lambda x: -x[1])),
        "total_award_fangsi": total_award_fangsi,
    }


async def bind_and_fetch(
    user_id: str,
    bot_id: str,
    cookie: str,
    role_id: str,
) -> str:
    """绑定 kf cookie 并自动抓取刮刮乐数据。返回用户提示文案。

    role_id(即游戏角色 roleId) 由指令层从 NTEUser 表查出（单账号直接用，
    多账号由用户发数字选择后传入）。
    """
    if not role_id:
        return "未找到你的游戏角色 ID，请先登录获取角色信息。"

    # 抓取数据
    try:
        summary = await fetch_scratch_data(cookie, role_id)
    except Exception as e:
        logger.exception(f"[刮刮乐] 抓取失败: {e}")
        return f"刮刮乐数据抓取失败：{e}。请检查 cookie 是否有效。"

    # 入库
    s = summary
    await NTEKfCookie.upsert(
        user_id, bot_id,
        cookie=cookie,
        uid=role_id,
        total_spent=s["total_spent"],
        total_income=s["total_income"],
        profit=s["total_profit"],
        return_rate=s["total_return_rate"],
        raw_data=json.dumps(s, ensure_ascii=False),
        slice_count=s["slice_count"],
        last_updated=_fmt(datetime.now(TZ_BEIJING)),
    )
    return (
        f"✅ 刮刮乐 cookie 绑定成功，数据已获取！\n"
        f"📊 累计数据：{s['total_spent']:,} 消费 → {s['total_income']:,} 收入\n"
        f"    盈亏：{s['total_profit']:+,}    回报率：{s['total_return_rate']:.2f}%"
        if s["total_return_rate"] is not None
        else f"✅ 刮刮乐 cookie 绑定成功，数据已获取！\n累计数据：{s['total_spent']:,} 消费 → {s['total_income']:,} 收入"
    )


async def refresh_data(user_id: str, bot_id: str) -> str:
    """刷新刮刮乐数据。返回提示文案。"""
    row = await NTEKfCookie.get_by_user(user_id, bot_id)
    if row is None:
        return "你还没有绑定刮刮乐 ck！请【私聊】机器人发送：nte添加刮刮乐ck oauth=xxx; ..."

    if not row.cookie or not row.uid:
        return "刮刮乐数据不完整，请重新绑定 cookie。"

    try:
        summary = await fetch_scratch_data(row.cookie, row.uid)
    except Exception as e:
        logger.exception(f"[刮刮乐] 刷新失败: {e}")
        return f"刮刮乐数据刷新失败：{e}"

    s = summary
    await NTEKfCookie.upsert(
        user_id, bot_id,
        cookie=row.cookie,
        uid=row.uid,
        total_spent=s["total_spent"],
        total_income=s["total_income"],
        profit=s["total_profit"],
        return_rate=s["total_return_rate"],
        raw_data=json.dumps(s, ensure_ascii=False),
        slice_count=s["slice_count"],
        last_updated=_fmt(datetime.now(TZ_BEIJING)),
    )
    return (
        f"✅ 刮刮乐数据已刷新！\n"
        f"📊 累计数据：{s['total_spent']:,} 消费 → {s['total_income']:,} 收入\n"
        f"    盈亏：{s['total_profit']:+,}    回报率：{s['total_return_rate']:.2f}%"
        if s["total_return_rate"] is not None
        else f"✅ 刮刮乐数据已刷新！\n累计数据：{s['total_spent']:,} 消费 → {s['total_income']:,} 收入"
    )


async def refresh_user_data(user_id: str) -> str:
    """管理员指令：强制刷新指定用户的刮刮乐数据。

    一个用户可能绑定多个账号（多行记录），因此遍历该 user_id 下的全部记录，
    逐行用各自存储的 cookie + roleId 重抓并覆盖，避免漏掉其它账号。
    """
    rows = await NTEKfCookie.list_by_user_id(user_id)
    if not rows:
        return f"未找到用户 {user_id} 的刮刮乐绑定记录。"

    lines = [f"用户 {user_id} 共 {len(rows)} 个绑定账号："]
    for row in rows:
        role_label = row.uid or "?"
        if not row.cookie or not row.uid:
            lines.append(f"• 角色 {role_label}（bot {row.bot_id}）：cookie 或角色 ID 缺失，跳过")
            continue
        try:
            summary = await fetch_scratch_data(row.cookie, row.uid)
        except Exception as e:
            logger.exception(f"[刮刮乐] 管理员刷新用户 {user_id} 角色 {row.uid} 失败: {e}")
            lines.append(f"• 角色 {role_label}：刷新失败 {e}")
            continue

        s = summary
        await NTEKfCookie.upsert(
            row.user_id, row.bot_id,
            cookie=row.cookie,
            uid=row.uid,
            total_spent=s["total_spent"],
            total_income=s["total_income"],
            profit=s["total_profit"],
            return_rate=s["total_return_rate"],
            raw_data=json.dumps(s, ensure_ascii=False),
            slice_count=s["slice_count"],
            last_updated=_fmt(datetime.now(TZ_BEIJING)),
        )
        rr = f"{s['total_return_rate']:.2f}%" if s["total_return_rate"] is not None else "N/A"
        lines.append(
            f"• 角色 {role_label}：{s['total_spent']:,} 消费 → {s['total_income']:,} 收入，回报率 {rr}"
        )
    return "\n".join(lines)


async def show_stats(user_id: str, bot_id: str) -> str:
    """返回刮刮乐统计文案。"""
    row = await NTEKfCookie.get_by_user(user_id, bot_id)
    if row is None or not row.raw_data or row.raw_data == "{}":
        return "你还没有绑定刮刮乐 ck！请【私聊】机器人发送：nte添加刮刮乐ck oauth=xxx; ..."

    s = json.loads(row.raw_data)
    agg = aggregate_records(s)
    lines = [
        "📊 刮刮乐累计统计",
        f"　总消费：{s['total_spent']:,} 方斯",
        f"　总收入：{s['total_income']:,} 方斯",
        f"　总盈亏：{s['total_profit']:+,} 方斯",
    ]
    if s["total_return_rate"] is not None:
        lines.append(f"　回报率：{s['total_return_rate']:.2f}%")
    lines.append(f"　总刮数：{agg['total_records']} 次")
    lines.append(f"　数据切片：{s['slice_count']} 段")
    lines.append(f"　最后更新：{row.last_updated}")
    if agg["award_counts"]:
        lines.append("")
        lines.append("🎁 奖励分布（前10）：")
        for aw, cnt in list(agg["award_counts"].items())[:10]:
            label = aw if aw else "（未中奖）"
            lines.append(f"  {label} × {cnt}")
    return "\n".join(lines)


async def delete_ck(user_id: str, bot_id: str) -> str:
    """删除绑定的刮刮乐 ck。"""
    ok = await NTEKfCookie.delete_by_user(user_id, bot_id)
    if ok:
        return "✅ 已删除刮刮乐 ck 及绑定的数据。"
    return "你还没有绑定刮刮乐 ck。"


async def auto_refresh_all() -> str:
    """定时任务：自动刷新所有已绑定用户的刮刮乐数据。"""
    rows = await NTEKfCookie.list_all()
    if not rows:
        return "暂无已绑定的刮刮乐 ck。"
    count = 0
    for row in rows:
        try:
            summary = await fetch_scratch_data(row.cookie, row.uid)
        except Exception:
            continue
        s = summary
        await NTEKfCookie.upsert(
            row.user_id, row.bot_id,
            cookie=row.cookie,
            uid=row.uid,
            total_spent=s["total_spent"],
            total_income=s["total_income"],
            profit=s["total_profit"],
            return_rate=s["total_return_rate"],
            raw_data=json.dumps(s, ensure_ascii=False),
            slice_count=s["slice_count"],
            last_updated=_fmt(datetime.now(TZ_BEIJING)),
        )
        count += 1
    return f"✅ 刮刮乐自动更新完成，共刷新 {count} 人。"


async def show_today(user_id: str, bot_id: str) -> str:
    """返回今日刮刮乐数据。"""
    row = await NTEKfCookie.get_by_user(user_id, bot_id)
    if row is None:
        return "你还没有绑定刮刮乐 ck，请先【nte添加刮刮乐ck <cookie>】"

    if not row.cookie or not row.uid:
        return "刮刮乐数据不完整，请重新绑定 cookie。"

    try:
        today = await fetch_today_data(row.cookie, row.uid)
    except Exception as e:
        logger.exception(f"[刮刮乐] 今日查询失败: {e}")
        return "今日刮刮乐数据查询失败，请稍后重试或联系管理员。"

    if today is None:
        today_str = datetime.now(TZ_BEIJING).strftime("%Y-%m-%d")
        return f"📅 {today_str} 暂无刮刮乐记录"

    records = today.get("records", [])
    award_lines: list[str] = []
    for r in records:
        aw = r.get("award") or "（未中奖）"
        award_lines.append(f"  {aw}")
    lines = [
        f"📅 今日刮刮乐 ({_fmt_date(datetime.now(TZ_BEIJING))})",
        f"　消费：{today['spent']:,} 方斯",
        f"　收入：{today['income']:,} 方斯",
        f"　盈亏：{today['profit']:+,} 方斯",
    ]
    if today["return_rate"] is not None:
        lines.append(f"　回报率：{today['return_rate']:.2f}%")
    lines.append(f"　次数：{len(records)} 次")
    if award_lines:
        lines.append("　明细：")
        lines.extend(award_lines[:20])  # 最多显示20条
        if len(award_lines) > 20:
            lines.append(f"  ... 共 {len(award_lines)} 条")
    return "\n".join(lines)
