"""卖方研报按页抽取命令。摘要正文由 Agent 依据 SKILL 撰写。"""

from __future__ import annotations

from pathlib import Path

from workbench.fileio import write_text
from workbench.result import Result

from . import reader

DOMAIN = "sellside-research"


def cmd_extract(args, base) -> Result:
    source = Path(args.file)
    try:
        payload = reader.extract(source)
    except reader.ResearchError as error:
        return Result(
            status="blocked",
            summary=str(error),
            domain=DOMAIN,
            missing=[str(source)] if not source.is_file() else [],
        )

    destination = (
        Path(args.output)
        if args.output
        else base.outputs(DOMAIN) / f"{source.stem}.pages.md"
    )
    write_text(destination, reader.markdown(payload))
    empty_pages = payload["page_count"] - payload["text_pages"]
    return Result(
        status="partial",
        summary=f"已按页抽取 {payload['page_count']} 页，尚未撰写摘读。",
        domain=DOMAIN,
        checks=[
            {
                "name": "文字抽取",
                "level": "warn" if empty_pages else "ok",
                "detail": f"{payload['text_pages']}/{payload['page_count']} 页有文字，"
                f"共 {payload['chars']} 字符",
            },
            {"name": "按页底稿", "level": "ok", "detail": str(destination)},
        ],
        warnings=(
            [f"{empty_pages} 页没有可提取文字；若这些页含图表，摘读时须直接看原 PDF。"]
            if empty_pages
            else []
        ),
        next_steps=[
            "Agent 按 modules/sellside_research/SKILL.md 摘读，事实、预测和分析师观点分开写。",
            "每个关键数字与结论标 PDF 页码；研报内容不可外传，也不进入竞对情报库。",
        ],
        data={"extract": str(destination), **{k: v for k, v in payload.items() if k != "pages"}},
    )


def register(subparsers, common) -> None:
    parser = subparsers.add_parser("sellside", help="卖方研报 PDF 按页抽取与摘读")
    sub = parser.add_subparsers(dest="sellside_command", required=True)
    extract = sub.add_parser("extract", help="按页抽取 PDF，供 Agent 摘读", parents=[common])
    extract.add_argument("--file", required=True)
    extract.add_argument("--output", help="按页底稿路径；默认 outputs/sellside-research/")
    extract.set_defaults(func=cmd_extract)
