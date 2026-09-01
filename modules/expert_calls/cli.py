"""CLI stages for the expert-calls migration."""

from __future__ import annotations

import json
from pathlib import Path

from workbench import manifest as manifest_mod
from workbench.result import Result

from . import pipeline, steps


def _run_id(args) -> str:
    manifest_path = getattr(args, "manifest", None)
    if manifest_path:
        path = Path(manifest_path)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            payload = {}
        run_id = payload.get("run_id")
        if isinstance(run_id, str) and run_id:
            return run_id
    return args.run_id or pipeline.new_run_id()


def cmd_extract(args, base) -> Result:
    run_id = _run_id(args)
    source = Path(args.pdf)
    target = Path(args.text_out) if args.text_out else base.scratch / "expert-calls" / run_id / f"{source.stem}.txt"
    if not source.is_file():
        return Result(status="blocked", summary="找不到 PDF。", domain=steps.DOMAIN, period=run_id, missing=[str(source)])
    try:
        written = pipeline.extract_pdf(source, target)
    except pipeline.EmptyOrScannedPDFError as error:
        steps.record(base, run_id, "extract", "blocked", note=str(error), inputs={"pdf": source})
        return Result(status="blocked", summary="PDF 无可提取文字，已停止。", domain=steps.DOMAIN, period=run_id, missing=[str(error)])
    except Exception as error:
        steps.record(base, run_id, "extract", "failed", note=str(error), inputs={"pdf": source})
        return Result(status="failed", summary="PDF 抽取失败。", domain=steps.DOMAIN, period=run_id, warnings=[str(error)])
    steps.record(base, run_id, "extract", "done", inputs={"pdf": source}, outputs={"text": written})
    return Result(status="success", summary="PDF 已按页抽取到 ignored scratch。", domain=steps.DOMAIN, period=run_id, data={"text": str(written)})


def cmd_validate(args, base) -> Result:
    run_id = _run_id(args)
    source = Path(args.manifest)
    try:
        payload = pipeline.validate_manifest(source)
    except (OSError, ValueError) as error:
        steps.record(base, run_id, "validate", "blocked", note=str(error))
        return Result(status="blocked", summary="Manifest 校验未通过。", domain=steps.DOMAIN, period=run_id, missing=[str(error)])
    included = sum(row["include"] for row in payload.get("interviews", payload.get("records", [])))
    steps.record(base, run_id, "validate", "done", inputs={"manifest": source}, result_data={"included": included})
    return Result(status="success", summary=f"Manifest 合规：{included} 条收录。", domain=steps.DOMAIN, period=run_id)
def cmd_render(args, base) -> Result:
    run_id = _run_id(args)
    source = Path(args.manifest)
    target = Path(args.out_dir) if args.out_dir else base.scratch / "expert-calls" / run_id / "callouts"
    try:
        written = pipeline.render_manifest(source, target)
    except (OSError, ValueError) as error:
        steps.record(base, run_id, "render", "blocked", note=str(error))
        return Result(status="blocked", summary="Callout 未渲染。", domain=steps.DOMAIN, period=run_id, missing=[str(error)])
    steps.record(base, run_id, "validate", "done", inputs={"manifest": source})
    steps.record(base, run_id, "render", "done", outputs={f"callout-{i}": path for i, path in enumerate(written, 1)})
    return Result(status="success", summary=f"渲染 {len(written)} 份 revision-1680 XML。", domain=steps.DOMAIN, period=run_id, data={"files": [str(path) for path in written]})


def cmd_publish(args, base) -> Result:
    run_id = _run_id(args)
    source = Path(args.manifest)
    result = pipeline.publish_manifest(source, base, run_id, confirm=args.confirm_publish)
    if not args.confirm_publish:
        steps.record(base, run_id, "publish", "pending", note="dry-run；等待明确确认")
        return result
    state = "done" if result.status == "success" else result.status
    steps.record(
        base, run_id, "publish", state,
        note=result.summary,
        result_data={"written_block_ids": result.data.get("written_block_ids", [])},
    )
    if result.status == "success":
        steps.record(base, run_id, "intel-draft", "done", outputs={"draft": Path(result.data["intel_draft"])})
    return result


def cmd_status(args, base) -> Result:
    if args.run_id:
        run_id = args.run_id
    else:
        latest = manifest_mod.latest(base, steps.DOMAIN)
        if latest is None:
            return Result(status="partial", summary="专家访谈流程尚未运行。", domain=steps.DOMAIN)
        run_id = latest.period
    info = steps.progress(base, run_id)
    return Result(
        status="partial" if info["next"] or info["stuck"] else "success",
        summary=f"{run_id}：{info['done']}/{info['total']} 步完成。",
        domain=steps.DOMAIN,
        period=run_id,
        checks=steps.render_progress(base, run_id),
        data=info,
    )
def _add_run_id(parser) -> None:
    parser.add_argument(
        "--run-id",
        help="运行 ID，格式 YYYYMMDD-HHMMSS；manifest 命令优先读取文件内 run_id",
    )


def register(subparsers, common) -> None:
    parser = subparsers.add_parser("expert-calls", help="专家访谈 PDF → callout → 飞书")
    sub = parser.add_subparsers(dest="expert_calls_command", required=True)

    extract = sub.add_parser("extract", help="按页抽取 PDF 到 ignored scratch", parents=[common])
    extract.add_argument("--pdf", required=True)
    extract.add_argument("--text-out", help="抽取文本路径；默认写 ignored scratch")
    _add_run_id(extract)
    extract.set_defaults(func=cmd_extract)

    validate = sub.add_parser("validate", help="代码校验收录 manifest", parents=[common])
    validate.add_argument("--manifest", required=True)
    _add_run_id(validate)
    validate.set_defaults(func=cmd_validate)

    render = sub.add_parser("render", help="渲染 revision-1680 callout", parents=[common])
    render.add_argument("--manifest", required=True)
    render.add_argument("--out-dir")
    _add_run_id(render)
    render.set_defaults(func=cmd_render)

    publish = sub.add_parser("publish", help="发布到飞书（默认 dry-run）", parents=[common])
    publish.add_argument("--manifest", required=True)
    publish.add_argument(
        "--confirm-publish", action="store_true",
        help="确认执行飞书写入；仅在用户明确要求后使用",
    )
    _add_run_id(publish)
    publish.set_defaults(func=cmd_publish)

    status = sub.add_parser("status", help="查看某次运行进度", parents=[common])
    _add_run_id(status)
    status.set_defaults(func=cmd_status)
