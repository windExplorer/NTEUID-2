"""午夜猫刊亭统计 - 服务端抓取与本地统计（全量 / 增量更新）。

- 读取 cat/cookie.txt 作为 kf.wanmei.com 会话 cookie
- 读取 cat/role.txt 第一行为异环角色 id（gameId=191），接口必需
- 从 2026-07-02 00:00 (+08:00) 起，按 7 天一档切片请求接口
- 每档结果存 cat/data/slice_<start>_<end>.json（分页）
- 所有档汇总存 cat/data/summary.json（最终整合）
- 增量：已存在的 slice 文件跳过，不重复请求（不做当天，END=今天 00:00）
"""
from __future__ import annotations

import urllib.request
import urllib.parse
import ssl
import re
import json
import os
from datetime import datetime, timedelta, timezone

CAT = os.path.dirname(os.path.abspath(__file__))
COOKIE_FILE = os.path.join(CAT, "cookie.txt")
ROLE_FILE = os.path.join(CAT, "role.txt")
DATA_DIR = os.path.join(CAT, "data")

BASE = "https://kf.wanmei.com"
URL_SEARCH = f"{BASE}/selfItemFlowQuery/search"
URL_PAGE = f"{BASE}/selfItemFlowQuery?gameId=191"

TZ_BEIJING = timezone(timedelta(hours=8))
START = datetime(2026, 7, 2, 0, 0, 0, tzinfo=TZ_BEIJING)
SLICE_DAYS = 7
PAGE_SIZE = 1000

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
    "Referer": URL_PAGE,
    "X-Requested-With": "XMLHttpRequest",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
}
CTX = ssl.create_default_context()

INFO_RE = re.compile(r"共计消耗(\d+)方斯.*?获得奖券奖励(\d+)方斯")


def fmt(dt: datetime) -> str:
    return dt.astimezone(TZ_BEIJING).strftime("%Y-%m-%d %H:%M:%S")


def load_cookie() -> str:
    with open(COOKIE_FILE, encoding="utf-8") as f:
        return f.read().strip()


def load_role_id() -> str:
    if not os.path.exists(ROLE_FILE):
        raise SystemExit("缺少 role.txt：请把异环角色 id（gameId=191）写在第一行")
    with open(ROLE_FILE, encoding="utf-8") as f:
        rid = f.read().strip().splitlines()[0].strip()
    if not rid:
        raise SystemExit("role.txt 为空：请填入异环角色 id")
    return rid


def end_of_range() -> datetime:
    """取今天 00:00 (+08:00) 作为终点，不抓取当天（避免重复/不完整）。"""
    now = datetime.now(TZ_BEIJING)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def build_slices(start: datetime, end: datetime):
    slices = []
    cursor = start
    while cursor < end:
        slice_end = min(end, cursor + timedelta(days=SLICE_DAYS) - timedelta(seconds=1))
        slices.append((cursor, slice_end))
        cursor = slice_end + timedelta(seconds=1)
    return slices


def post_search(role_id: str, start: datetime, end: datetime, page: int) -> bytes:
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
        "startTime": fmt(start),
        "endTime": fmt(end),
        "pageNo": str(page),
        "pageSize": str(PAGE_SIZE),
    }
    body = urllib.parse.urlencode(params).encode("utf-8")
    req = urllib.request.Request(URL_SEARCH, data=body, headers=HEADERS, method="POST")
    with urllib.request.urlopen(req, context=CTX, timeout=30) as r:
        return r.read()


def parse_payload(raw: bytes) -> dict:
    text = raw.decode("utf-8", "replace").replace("<pre>", "").replace("</pre>", "").strip()
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


def slice_key(start: datetime, end: datetime) -> str:
    return f"{start.strftime('%Y%m%d%H%M%S')}_{end.strftime('%Y%m%d%H%M%S')}"


def fetch_slice(role_id: str, start: datetime, end: datetime) -> dict:
    """抓取一档（含接口内分页），返回该档统计 + 各页原始响应。"""
    pages = []
    page = 1
    total = {"spent": 0, "income": 0}
    while True:
        raw = post_search(role_id, start, end, page)
        parsed = parse_payload(raw)
        pages.append(parsed["raw"])
        # info 已是该时间区间的汇总，取首页即可；分页仅保存原始响应
        if page == 1:
            total = {"spent": parsed["spent"], "income": parsed["income"]}
        data_obj = json.loads(parsed["raw"]).get("data") or {}
        result_list = data_obj.get("result")
        if not (isinstance(result_list, list) and len(result_list) >= PAGE_SIZE):
            break
        page += 1
        if page > 50:
            break
    profit = total["income"] - total["spent"]
    return_rate = (total["income"] / total["spent"] * 100) if total["spent"] else None
    return {
        "start": fmt(start),
        "end": fmt(end),
        "spent": total["spent"],
        "income": total["income"],
        "profit": profit,
        "return_rate": return_rate,
        "pages": pages,
    }


def main():
    import argparse
    ap = argparse.ArgumentParser(description="午夜猫刊亭刮刮乐统计抓取")
    ap.add_argument("--cookie", default=COOKIE_FILE, help="kf 会话 cookie 文件（默认 cat/cookie.txt）")
    ap.add_argument("--role", default=ROLE_FILE, help="异环角色 id 文件（默认 cat/role.txt）")
    ap.add_argument("--data", default=DATA_DIR, help="数据输出目录（默认 cat/data）")
    args = ap.parse_args()

    with open(args.cookie, encoding="utf-8") as f:
        cookie = f.read().strip()
    if not os.path.exists(args.role):
        raise SystemExit(f"缺少角色文件: {args.role}")
    with open(args.role, encoding="utf-8") as f:
        role_id = f.read().strip().splitlines()[0].strip()
    if not role_id:
        raise SystemExit(f"角色文件为空: {args.role}")
    data_dir = args.data
    HEADERS["Cookie"] = cookie
    os.makedirs(data_dir, exist_ok=True)

    end = end_of_range()
    slices = build_slices(START, end)
    print(f"范围: {fmt(START)} ~ {fmt(end)}，共 {len(slices)} 档")

    results = []
    for i, (s, e) in enumerate(slices, 1):
        key = slice_key(s, e)
        out_path = os.path.join(data_dir, f"slice_{key}.json")
        if os.path.exists(out_path):
            print(f"[{i}/{len(slices)}] 跳过已存在 {key}")
            with open(out_path, encoding="utf-8") as f:
                results.append(json.load(f))
            continue
        print(f"[{i}/{len(slices)}] 请求 {key} ...")
        try:
            rec = fetch_slice(role_id, s, e)
        except Exception as ex:
            print(f"  失败: {ex}")
            raise
        rec["key"] = key
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(rec, f, ensure_ascii=False, indent=2)
        results.append(rec)

    # 最终整合
    total_spent = sum(r["spent"] for r in results)
    total_income = sum(r["income"] for r in results)
    total_profit = total_income - total_spent
    total_rate = (total_income / total_spent * 100) if total_spent else None
    summary = {
        "generated_at": fmt(datetime.now(TZ_BEIJING)),
        "range_start": fmt(START),
        "range_end": fmt(end),
        "total_spent": total_spent,
        "total_income": total_income,
        "total_profit": total_profit,
        "total_return_rate": total_rate,
        "slice_count": len(results),
        "slices": [
            {k: v for k, v in r.items() if k != "pages"} for r in results
        ],
    }
    summary_path = os.path.join(data_dir, "summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\n整合结果已写入 {summary_path}")
    print(f"消费={total_spent} 收入={total_income} 盈亏={total_profit} 回报率={total_rate:.2f}%" if total_rate is not None else f"消费={total_spent} 收入={total_income}")


if __name__ == "__main__":
    main()
