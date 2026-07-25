"""从某个 slice_*.json 的 pages 字段里解析出 data.result 明细，格式化输出到同目录 _records.json。

用法: python extract_records.py [slice文件路径]
不传参数则默认处理 data/ 下第一个 slice_*.json
"""
import json
import os
import re
import sys
from collections import Counter

CAT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(CAT, "data")


def collect_records(slice_data: dict):
    records = []
    for page in slice_data.get("pages", []):
        if isinstance(page, str):
            page = json.loads(page)
        data = page.get("data") or {}
        res = data.get("result") or []
        if isinstance(res, list):
            records.extend(res)
    return records


def main():
    if len(sys.argv) > 1:
        src = sys.argv[1]
    else:
        slices = sorted(f for f in os.listdir(DATA_DIR) if f.startswith("slice_") and f.endswith(".json"))
        if not slices:
            raise SystemExit("data/ 下没有 slice_*.json")
        src = os.path.join(DATA_DIR, slices[0])

    with open(src, encoding="utf-8") as f:
        slice_data = json.load(f)

    records = collect_records(slice_data)

    awards = Counter()
    total_award_fangsi = 0
    for r in records:
        aw = r.get("award") or ""
        awards[aw] += 1
        m = re.search(r"方斯\*(\d+)", aw)
        if m:
            total_award_fangsi += int(m.group(1))

    out = {
        "slice_key": slice_data.get("key"),
        "range": {"start": slice_data.get("start"), "end": slice_data.get("end")},
        "total_records": len(records),
        "distinct_scratchCardId": sorted({r.get("scratchCardId") for r in records if r.get("scratchCardId")}),
        "award_counts": dict(awards),
        "total_award_fangsi": total_award_fangsi,
        "records": records,
    }
    out_path = src[: -len(".json")] + "_records.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"源: {src}")
    print(f"记录数: {len(records)}")
    print(f"奖券/道具分布: {dict(awards)}")
    print(f"返还方斯合计: {total_award_fangsi}")
    print(f"已写出: {out_path}")


if __name__ == "__main__":
    main()
