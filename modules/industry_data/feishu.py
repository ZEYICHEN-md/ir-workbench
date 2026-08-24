#!/usr/bin/env python3
"""
Build / apply Feishu dry-run plan from canonical travel.json.
Fill-empty only; list conflicts when Feishu ≠ canonical.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from workbench.paths import find_root

#: 工作台根与 scratch。原实现按脚本相对位置推算，迁入后统一走 workbench.paths，
#: 避免第二套根目录逻辑。
ROOT = find_root(Path(__file__).resolve().parent)
SCRATCH = ROOT / "scratch"


def _lark_bin() -> str:
    for name in ("lark-cli.cmd", "lark-cli.exe", "lark-cli"):
        found = shutil.which(name)
        if found:
            return found
    # npm global on Windows
    npm = Path.home() / "AppData" / "Roaming" / "npm" / "lark-cli.cmd"
    if npm.exists():
        return str(npm)
    raise FileNotFoundError("lark-cli not found on PATH")


def _run_lark(args: list[str]) -> subprocess.CompletedProcess:
    cmd = [_lark_bin(), *args]
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")

BASE_TOKEN = "R7VLbtKQSa5uuzsdHm1ceLdFnVP"
TABLES = {
    "hotel": "tblKE7TLMm6tFqcp",
    "traffic": "tblxWUBJfT9hKZ13",
    "outbound": "tbl3ZC7cdO9tiADS",
}

# Feishu field names
HOTEL_METRICS = ("入住率", "ADR", "RevPAR")
TRAFFIC_METRICS = ("民航", "国铁")
OUTBOUND_METRICS = ("民航客运量（仅国内航司）", "三大航")

EPS = 5e-4  # unused legacy


def _norm_time(label: str) -> str:
    s = str(label).strip()
    if "春节" in s or "日均" in s or "月" in s or s.upper().startswith("Q"):
        return s

    def strip_part(p: str) -> str:
        p = p.strip()
        if "/" not in p:
            return p
        a, b = p.split("/", 1)
        try:
            return f"{int(a)}/{int(b)}"
        except ValueError:
            return p

    if "-" in s:
        left, right = s.split("-", 1)
        return f"{strip_part(left)}-{strip_part(right)}"
    return s


def _close(a: Any, b: Any) -> bool:
    """Match if equal when shown as integer percent (Feishu % precision 0)."""
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    try:
        return round(float(a) * 100) == round(float(b) * 100)
    except (TypeError, ValueError):
        return False


def _cell(v: Any) -> Any:
    """Normalize feishu cell to scalar."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str) and v.strip() == "":
        return None
    if isinstance(v, list):
        if not v:
            return None
        return _cell(v[0])
    if isinstance(v, dict):
        for k in ("text", "value", "number"):
            if k in v:
                return _cell(v[k])
    return v


def lark_record_list(table_id: str) -> list[dict]:
    """Fetch all records; lark-cli --format json returns columnar arrays."""
    records: list[dict] = []
    offset = 0
    limit = 200
    while True:
        proc = _run_lark(
            [
                "base",
                "+record-list",
                "--base-token",
                BASE_TOKEN,
                "--table-id",
                table_id,
                "--limit",
                str(limit),
                "--offset",
                str(offset),
                "--format",
                "json",
                "--as",
                "user",
            ]
        )
        if proc.returncode != 0:
            raise RuntimeError(f"lark-cli failed: {proc.stderr or proc.stdout}")
        envelope = json.loads(proc.stdout)
        data = envelope.get("data") or envelope
        # nested data.data for this CLI version
        if isinstance(data, dict) and "data" in data and isinstance(data["data"], list):
            rows = data["data"]
            fields = data.get("fields") or []
            ids = data.get("record_id_list") or []
            has_more = bool(data.get("has_more"))
        elif isinstance(data, dict) and "items" in data:
            # alternate shape
            for it in data["items"]:
                rid = it.get("record_id") or it.get("id")
                fields_map = it.get("fields") or {}
                row = {"_record_id": rid}
                for k, v in fields_map.items():
                    row[k] = _cell(v)
                if row.get("时间") is not None:
                    row["_time_norm"] = _norm_time(str(row["时间"]))
                records.append(row)
            break
        else:
            raise RuntimeError(f"Unexpected record-list shape: {str(envelope)[:300]}")

        for i, vals in enumerate(rows):
            row: dict[str, Any] = {"_record_id": ids[i] if i < len(ids) else None}
            for j, name in enumerate(fields):
                row[name] = _cell(vals[j] if j < len(vals) else None)
            if row.get("时间") is not None and str(row["时间"]).strip() != "":
                row["_time_norm"] = _norm_time(str(row["时间"]))
                records.append(row)
            elif any(row.get(f) is not None for f in fields if f != "时间"):
                records.append(row)

        if not has_more:
            break
        offset += limit
    return records


def _index_by_time(records: list[dict]) -> dict[str, dict]:
    out = {}
    for r in records:
        t = r.get("_time_norm") or ( _norm_time(str(r["时间"])) if r.get("时间") else None)
        if t:
            out[t] = r
    return out


def _canonical_rows(data: dict) -> list[tuple[str, str, dict[str, float | None]]]:
    """Yield (table_key, time_label, metrics_dict)."""
    rows: list[tuple[str, str, dict]] = []
    monthly = data.get("monthly") or {}
    months = monthly.get("months") or []
    for i, m in enumerate(months):
        hotel = {
            "入住率": _at(monthly.get("hotelOccupancy"), i),
            "ADR": _at(monthly.get("hotelADR"), i),
            "RevPAR": _at(monthly.get("hotelRevPAR"), i),
        }
        if any(v is not None for v in hotel.values()):
            rows.append(("hotel", m, hotel))
        traffic = {
            "民航": _at(monthly.get("domAviationCAAC"), i),
            "国铁": _at(monthly.get("railway"), i),
        }
        if any(v is not None for v in traffic.values()):
            rows.append(("traffic", m, traffic))
        outbound = {
            "民航客运量（仅国内航司）": _at(monthly.get("intlAviationCAAC"), i),
            "三大航": _at(monthly.get("intlAviationBig3"), i),
        }
        if any(v is not None for v in outbound.values()):
            rows.append(("outbound", m, outbound))

    for qkey in ("q1", "q2", "q3", "q4"):
        q = (data.get("quarterly") or {}).get(qkey) or {}
        if not q or not any(v is not None for v in q.values()):
            continue
        qlabel = qkey.upper()
        rows.append(
            (
                "hotel",
                qlabel,
                {
                    "入住率": q.get("hotelOccupancy"),
                    "ADR": q.get("hotelADR"),
                    "RevPAR": q.get("hotelRevPAR"),
                },
            )
        )
        rows.append(
            (
                "traffic",
                qlabel,
                {"民航": q.get("domAviationCAAC"), "国铁": q.get("railway")},
            )
        )
        rows.append(
            (
                "outbound",
                qlabel,
                {
                    "民航客运量（仅国内航司）": q.get("intlAviationCAAC"),
                    "三大航": q.get("intlAviationBig3"),
                },
            )
        )

    weekly = data.get("weekly") or {}
    weeks = weekly.get("weeks") or []
    for i, w in enumerate(weeks):
        hotel = {
            "入住率": _at(weekly.get("hotelOccupancy"), i),
            "ADR": _at(weekly.get("hotelADR"), i),
            "RevPAR": _at(weekly.get("hotelRevPAR"), i),
        }
        if any(v is not None for v in hotel.values()):
            rows.append(("hotel", w, hotel))
    return rows


def _at(arr: list | None, i: int):
    if not arr or i >= len(arr):
        return None
    return arr[i]


def build_plan(data: dict) -> dict:
    caches = {k: _index_by_time(lark_record_list(tid)) for k, tid in TABLES.items()}
    plan = {
        "create": [],
        "fill_empty": [],
        "conflicts": [],
        "skip_unchanged": [],
        "base_token": BASE_TOKEN,
        "tables": TABLES,
    }

    for table_key, time_label, metrics in _canonical_rows(data):
        tnorm = _norm_time(time_label)
        existing = caches[table_key].get(tnorm)
        if existing is None:
            # also try raw label
            existing = caches[table_key].get(time_label)
        if existing is None:
            fields = {"时间": time_label}
            for k, v in metrics.items():
                if v is not None:
                    fields[k] = v
            if len(fields) > 1:
                plan["create"].append(
                    {"table": table_key, "table_id": TABLES[table_key], "fields": fields}
                )
            continue

        fill = {}
        conflict = []
        unchanged = True
        for k, want in metrics.items():
            if want is None:
                continue
            have = existing.get(k)
            if have is None or have == "":
                fill[k] = want
                unchanged = False
            elif not _close(have, want):
                conflict.append({"field": k, "feishu": have, "canonical": want})
                unchanged = False
        if conflict:
            plan["conflicts"].append(
                {
                    "table": table_key,
                    "time": time_label,
                    "record_id": existing.get("_record_id"),
                    "diffs": conflict,
                }
            )
        if fill:
            plan["fill_empty"].append(
                {
                    "table": table_key,
                    "table_id": TABLES[table_key],
                    "record_id": existing.get("_record_id"),
                    "time": time_label,
                    "fields": fill,
                }
            )
        if unchanged and not conflict:
            plan["skip_unchanged"].append({"table": table_key, "time": time_label})

    return plan


def write_plan(plan: dict) -> Path:
    SCRATCH.mkdir(exist_ok=True)
    path = SCRATCH / "feishu_travel_plan.json"
    path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    # human summary
    summary = SCRATCH / "feishu_travel_plan_summary.md"
    lines = [
        "# Feishu dry-run summary",
        "",
        f"- create: **{len(plan['create'])}**",
        f"- fill_empty: **{len(plan['fill_empty'])}**",
        f"- conflicts (not overwritten): **{len(plan['conflicts'])}**",
        f"- skip_unchanged: **{len(plan['skip_unchanged'])}**",
        "",
    ]
    if plan["conflicts"]:
        lines.append("## Conflicts")
        for c in plan["conflicts"][:50]:
            lines.append(f"- `{c['table']}` `{c['time']}`: {c['diffs']}")
        lines.append("")
    if plan["create"]:
        lines.append("## Creates (sample)")
        for c in plan["create"][:20]:
            lines.append(f"- `{c['table']}` {c['fields'].get('时间')}: { {k:v for k,v in c['fields'].items() if k!='时间'} }")
    summary.write_text("\n".join(lines), encoding="utf-8")
    return path


def _write_scratch_json(name: str, payload: Any) -> str:
    SCRATCH.mkdir(exist_ok=True)
    path = SCRATCH / name
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    # lark-cli requires relative path within cwd
    return str(path.relative_to(ROOT)).replace("\\", "/")


def apply_plan(plan_path: Path, yes: bool = False, overwrite_conflicts: bool = False) -> None:
    if not yes:
        raise SystemExit("Refusing to write without --yes")
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    table_ids = plan.get("tables") or TABLES

    # batch create per table
    by_table: dict[str, list] = {}
    for item in plan.get("create") or []:
        by_table.setdefault(item["table_id"], []).append(item["fields"])

    for table_id, rows in by_table.items():
        for i in range(0, len(rows), 200):
            chunk = rows[i : i + 200]
            field_names: list[str] = []
            for row in chunk:
                for key in row:
                    if key not in field_names:
                        field_names.append(key)
            matrix = [[row.get(name) for name in field_names] for row in chunk]
            payload = {"fields": field_names, "rows": matrix}
            rel = _write_scratch_json(f"_feishu_batch_create_{table_id}_{i}.json", payload)
            cmd = [
                _lark_bin(),
                "base",
                "+record-batch-create",
                "--base-token",
                BASE_TOKEN,
                "--table-id",
                table_id,
                "--json",
                f"@{rel}",
                "--as",
                "user",
            ]
            print("+", " ".join(cmd))
            subprocess.check_call(cmd, cwd=str(ROOT))

    updates = list(plan.get("fill_empty") or [])
    if overwrite_conflicts:
        for c in plan.get("conflicts") or []:
            fields = {d["field"]: d["canonical"] for d in c.get("diffs") or []}
            if not fields:
                continue
            updates.append(
                {
                    "table": c["table"],
                    "table_id": table_ids.get(c["table"]) or TABLES[c["table"]],
                    "record_id": c["record_id"],
                    "time": c["time"],
                    "fields": fields,
                }
            )

    for idx, item in enumerate(updates):
        rid = item["record_id"]
        fields = item["fields"]
        rel = _write_scratch_json(f"_feishu_upsert_{idx}.json", fields)
        cmd = [
            _lark_bin(),
            "base",
            "+record-upsert",
            "--base-token",
            BASE_TOKEN,
            "--table-id",
            item["table_id"],
            "--record-id",
            rid,
            "--json",
            f"@{rel}",
            "--as",
            "user",
        ]
        print("+ upsert", item.get("table"), item.get("time"), list(fields.keys()))
        subprocess.check_call(cmd, cwd=str(ROOT))

    print(
        "Apply done.",
        f"updates={len(updates)}",
        f"overwrite_conflicts={overwrite_conflicts}",
        f"conflicts_in_plan={len(plan.get('conflicts') or [])}",
    )


#: 入口在 `ir industry feishu plan|apply`（见 cli.py）。
#: 原来的 `__main__` 直读 `data_source/canonical/travel.json`，迁入后不再保留
#: 第二个入口——快照路径由 DomainPaths 提供。
