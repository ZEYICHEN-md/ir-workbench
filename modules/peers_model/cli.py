"""Peers Model 统一命令入口。"""
from __future__ import annotations

from . import selftest, workflow


def cmd_inspect(args, paths):
    return workflow.inspect(paths, args.company)


def cmd_prepare(args, paths):
    return workflow.prepare(paths, args.company, args.period, args.pdf)


def cmd_plan(args, paths):
    return workflow.plan(paths, args.company, args.period, args.facts)


def cmd_apply(args, paths):
    return workflow.apply(paths, args.company, args.period, args.facts, confirmed=args.confirmed)


def cmd_selftest(args, paths):
    return selftest.run(paths, args.company, args.period)


def _common_model_args(parser) -> None:
    parser.add_argument("--company", required=True, help="BKNG/EXPE/ABNB/MEITUAN/TCEL")
    parser.add_argument("--period", required=True, help="如 26Q3、26H1、FY2026")


def register(subparsers, common) -> None:
    parser = subparsers.add_parser("peers-model", help="Peers 财务 Model 与 Charts 机械更新")
    sub = parser.add_subparsers(dest="peers_model_command", required=True)

    inspect_p = sub.add_parser("inspect", help="只读核对模型结构", parents=[common])
    inspect_p.add_argument("--company", required=True)
    inspect_p.set_defaults(func=cmd_inspect)

    prepare_p = sub.add_parser("prepare", help="抽取 PDF 并生成逐行 facts 模板", parents=[common])
    _common_model_args(prepare_p)
    prepare_p.add_argument("--pdf", action="append", required=True, help="可重复提供多份 PDF")
    prepare_p.set_defaults(func=cmd_prepare)

    plan_p = sub.add_parser("plan", help="独立重读 PDF 并生成零写入计划", parents=[common])
    _common_model_args(plan_p)
    plan_p.add_argument("--facts", required=True)
    plan_p.set_defaults(func=cmd_plan)

    apply_p = sub.add_parser("apply", help="写入新的 Model 副本并回读审计", parents=[common])
    _common_model_args(apply_p)
    apply_p.add_argument("--facts", required=True)
    apply_p.add_argument("--confirmed", action="store_true", help="确认执行副本写入")
    apply_p.set_defaults(func=cmd_apply)

    selftest_p = sub.add_parser(
        "selftest", help="用已有期间做 holdout 回放，不覆盖权威 Model", parents=[common]
    )
    selftest_p.add_argument("--company", default="ALL", help="BKNG/EXPE/ABNB/MEITUAN/TCEL/ALL")
    selftest_p.add_argument("--period", required=True)
    selftest_p.set_defaults(func=cmd_selftest)
