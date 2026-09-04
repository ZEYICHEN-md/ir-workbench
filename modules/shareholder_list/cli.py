"""shareholder-list 命令。挂在 `ir shareholder-list` 下。唯一入口，不另写 PowerShell / python -m。"""

from __future__ import annotations

import io
import json
from contextlib import redirect_stderr, redirect_stdout
from datetime import date
from pathlib import Path

from workbench.result import Result

from . import DOMAIN
from .build import VALID_AS_OF
from .discover import default_combined, default_peer, default_template
from .engine import default_output, main as engine_main, valid_as_date as engine_valid


def _parse_json_blobs(text: str) -> list[dict]:
    decoder = json.JSONDecoder()
    blobs: list[dict] = []
    idx = 0
    stripped = text.lstrip()
    while idx < len(stripped):
        while idx < len(stripped) and stripped[idx].isspace():
            idx += 1
        if idx >= len(stripped):
            break
        try:
            obj, end = decoder.raw_decode(stripped, idx)
        except json.JSONDecodeError:
            break
        if isinstance(obj, dict):
            blobs.append(obj)
        idx = end
    return blobs


def cmd_rebuild(args, base) -> Result:
    peer = Path(args.peer) if args.peer else default_peer()
    combined = Path(args.combined) if args.combined else default_combined()
    template = Path(args.template) if args.template else default_template()
    missing: list[str] = []
    if peer is None or not peer.is_file():
        missing.append("Peer Ownership-Holdings-*.xlsx（Downloads；不要 Public 版，不要 InvestorLists）")
    if combined is None or not combined.is_file():
        missing.append("Institution Combined Ownership-Public-*.xlsx（Downloads）")
    if template is None or not template.is_file():
        missing.append(f"母版骨架 {template or 'PRIOR_TEMPLATE'}")
    if missing:
        return Result(
            status="blocked",
            summary="缺底表或母版，没法生成 shareholder list。",
            domain=DOMAIN,
            missing=missing,
            next_steps=[
                "把两张 Capital IQ 底表放到「下载」文件夹。",
                "缺哪张就说哪张，不要用 InvestorLists 顶替。",
            ],
        )

    today = date.today()
    locked = engine_valid()
    refresh = bool(args.refresh_market)
    force = bool(args.force_refresh)
    if refresh and today != locked and not force:
        return Result(
            status="blocked",
            summary="今天不是当前有效日，刷新行情被拦住（这是锁定重建）。",
            domain=DOMAIN,
            period=locked.isoformat(),
            warnings=[f"VALID_AS_OF={VALID_AS_OF}；today={today.isoformat()}"],
            next_steps=[
                "只说「跑一遍」→ 不要加 --refresh-market。",
                "要出下一本：先明确有效日，改 build.py 常量后再带 --refresh-market。",
            ],
        )

    argv = ["--audit", "--peer", str(peer), "--combined", str(combined), "--template", str(template)]
    if args.output:
        argv.extend(["--output", str(Path(args.output))])
    if refresh:
        argv.append("--refresh-market")
    if force:
        argv.append("--force-refresh")

    stdout = io.StringIO()
    stderr = io.StringIO()
    try:
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = engine_main(argv)
    except SystemExit as error:
        message = str(error) if error.args else stderr.getvalue().strip()
        return Result(
            status="blocked",
            summary="生成器拒绝执行。",
            domain=DOMAIN,
            warnings=[message or stderr.getvalue().strip() or "SystemExit"],
            next_steps=["看缺的是底表、母版还是锁定日刷新。不要手改 xlsx。"],
        )
    except Exception as error:  # noqa: BLE001
        return Result(
            status="failed",
            summary=f"生成失败：{type(error).__name__}: {error}",
            domain=DOMAIN,
            next_steps=["不要手改生成的 xlsx。改 modules/shareholder_list 后再重建。"],
        )

    blobs = _parse_json_blobs(stdout.getvalue())
    validate_blob = next((b for b in blobs if "validate" in b), None)
    audit_blob = next((b for b in blobs if "n" in b and "output" in b), None)
    out_path = Path(args.output) if args.output else default_output(base.root)
    if audit_blob and audit_blob.get("output"):
        out_path = Path(audit_blob["output"])

    checks = [
        {
            "name": "进程",
            "level": "ok" if code == 0 else "fail",
            "detail": f"exit {code}",
        }
    ]
    if validate_blob:
        report = validate_blob.get("validate") or {}
        checks.append(
            {
                "name": "validate.ok",
                "level": "ok" if report.get("ok") else "fail",
                "detail": "failures 为空" if not report.get("failures") else "；".join(report.get("failures") or [])[:400],
            }
        )
    if audit_blob:
        n_findings = audit_blob.get("n")
        checks.append(
            {
                "name": "audit",
                "level": "ok" if n_findings == 0 else "fail",
                "detail": f"n={n_findings}；output={audit_blob.get('output')}",
            }
        )

    if code != 0:
        return Result(
            status="failed",
            summary="shareholder list 门禁未过。",
            domain=DOMAIN,
            period=locked.isoformat(),
            checks=checks,
            warnings=[line for line in stderr.getvalue().splitlines() if line][-8:],
            next_steps=["不要打开 Excel 手改。改生成器后再跑 `ir shareholder-list rebuild`。"],
            data={"output": str(out_path), "stderr": stderr.getvalue()[-2000:]},
        )

    path_note = "锁定重建" if today != locked else "有效日即今天"
    return Result(
        status="success",
        summary=f"已生成 shareholder list（{path_note}）：{out_path.name}",
        domain=DOMAIN,
        period=locked.isoformat(),
        checks=checks,
        next_steps=[
            "打开前先关已有 Excel。",
            "交差文件就是刚写的那一本；不对就改脚本再跑，不要手改格子。",
        ],
        data={
            "output": str(out_path),
            "validate": validate_blob,
            "audit": audit_blob,
            "stderr": stderr.getvalue(),
        },
    )


def register(subparsers, common) -> None:
    parser = subparsers.add_parser("shareholder-list", help="机构股东名册（Capital IQ → Investor List xlsx）")
    sub = parser.add_subparsers(dest="shareholder_list_command", required=True)
    rebuild = sub.add_parser("rebuild", help="复制母版并重建当前有效日那一本（默认锁定重建）", parents=[common])
    rebuild.add_argument("--peer", help="覆盖自动发现的 Peer Holdings 底表")
    rebuild.add_argument("--combined", help="覆盖自动发现的 Combined Ownership 底表")
    rebuild.add_argument("--template", help="覆盖 PRIOR_TEMPLATE 母版")
    rebuild.add_argument("--output", help="覆盖 outputs/shareholder-list/<有效日>/ 下的文件名")
    rebuild.add_argument(
        "--refresh-market",
        action="store_true",
        help="新切才用：拉取 Yahoo 市值。锁定重建不要加。",
    )
    rebuild.add_argument(
        "--force-refresh",
        action="store_true",
        help="覆盖冻结行情。用户没明确说不要用。",
    )
    rebuild.set_defaults(func=cmd_rebuild)
