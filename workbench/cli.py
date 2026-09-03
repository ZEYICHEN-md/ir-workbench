"""工作台 CLI —— Agent 的手，不是人的入口。

人的入口是 router/ROUTER.md（自然语言）。业务接手人不应看到这些命令。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import doctor as doctor_mod
from . import domains as domains_mod
from . import status as status_mod
from .config import WORKBOOK_KEYS, Config
from .fileio import write_text
from .paths import Paths, find_root
from .result import Result

VERSION = "0.1.0"


def _force_utf8_output() -> None:
    """把 stdout/stderr 固定为 UTF-8。

    Windows 上输出被重定向或管道捕获时，Python 会退回控制台代码页（中文机器上是 GBK），
    这时输出里的 `✓` 会直接抛 UnicodeEncodeError 把命令弄崩——而 Agent 捕获输出是常态。
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def _emit(result: Result, args) -> int:
    """输出结果。`--out` 让 CLI 自己写文件，绕开 shell 重定向的编码问题。"""
    out = getattr(args, "out", None)
    if out:
        write_text(Path(out), result.to_json() + "\n")
    print(result.to_json() if getattr(args, "json", False) else result.render())
    return result.exit_code


def _cmd_doctor(args, paths: Paths) -> int:
    return _emit(doctor_mod.run(paths, verbose=args.verbose), args)


def _cmd_status(args, paths: Paths) -> int:
    return _emit(status_mod.run(paths, domain=args.domain), args)


def _cmd_domains(args, paths: Paths) -> int:
    rows = []
    for definition in domains_mod.DOMAINS.values():
        rows.append(
            {
                "key": definition.key,
                "name": definition.zh,
                "facing": "对外" if definition.facing == "external" else "内部",
                "cadence": definition.cadence,
                "period_example": definition.period_example,
                "summary": definition.summary,
                "origin": definition.origin,
                "migrated": paths.module(definition.key).is_dir(),
            }
        )
    result = Result(
        status="success",
        summary=f"工作台共 {len(rows)} 个域（对外 {len(domains_mod.EXTERNAL_DOMAINS)}，内部 {len(domains_mod.INTERNAL_DOMAINS)}）。",
        checks=[
            {
                "name": f"{r['name']}（{r['facing']}·{r['cadence']}）",
                "level": "ok" if r["migrated"] else "warn",
                "detail": r["summary"] if r["migrated"] else f"未迁入 · 来源 {r['origin']}",
            }
            for r in rows
        ],
        data={"domains": rows},
    )
    return _emit(result, args)


def _cmd_hygiene(args, paths: Paths) -> int:
    from . import hygiene

    return _emit(hygiene.run(paths, fix=args.fix), args)


def _cmd_config_show(args, paths: Paths) -> int:
    config = Config(paths)
    checks = []
    for key, desc in WORKBOOK_KEYS.items():
        chosen = config.workbook(key)
        checks.append(
            {
                "name": key,
                "level": "ok" if chosen and chosen.is_file() else "warn",
                "detail": str(chosen) if chosen else f"未指定 —— {desc}",
            }
        )
    result = Result(
        status="success" if config.exists else "partial",
        summary="本机配置" + ("" if config.exists else "尚未创建"),
        checks=checks,
        data=config.load(),
    )
    return _emit(result, args)


def _cmd_config_candidates(args, paths: Paths) -> int:
    config = Config(paths)
    checks = []
    for key in WORKBOOK_KEYS:
        for candidate in config.candidates(key):
            checks.append({"name": key, "level": "ok", "detail": candidate.name})
    result = Result(
        status="success",
        summary="候选工作簿。请**用户**指定用哪一份——系统不按文件名猜最新。",
        checks=checks or [{"name": "候选", "level": "warn", "detail": "data/workbooks/ 下没有候选文件"}],
    )
    return _emit(result, args)


def _cmd_config_set(args, paths: Paths) -> int:
    config = Config(paths)
    resolved = config.set_workbook(args.key, Path(args.path))
    result = Result(
        status="success",
        summary=f"已锁定 {args.key} 工作簿",
        checks=[{"name": args.key, "level": "ok", "detail": str(resolved)}],
    )
    return _emit(result, args)


def _register_domain_commands(sub) -> None:
    """挂载已迁入的域命令。未迁入的域自然不出现，不留空壳入口。"""
    import importlib

    # 已迁入的域各自注册；未迁入的自然不出现，不留空壳入口。
    # 导入失败（缺可选依赖等）只跳过该域，不影响其余命令可用。
    for module_name in (
        "modules.industry_data.cli",
        "modules.aviation_monthly.cli",
        "modules.news_digest.cli",
        "modules.competitor_intel.cli",
        "modules.expert_calls.cli",
        "modules.hk_market.cli",
        "modules.sellside_research.cli",
        "modules.peers_appendix.cli",
    ):
        try:
            module = importlib.import_module(module_name)
        except ImportError:
            continue
        module.register(sub, COMMON)


def _common_flags() -> argparse.ArgumentParser:
    """所有子命令共享的开关。

    用 parents 挂上去，这样 `ir --json domains` 与 `ir domains --json` 都能认——
    Agent 更自然地会写后者，不该因为参数位置而报错。
    """
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument("--json", action="store_true", help="机器可读输出")
    parent.add_argument(
        "--out",
        metavar="文件",
        help="把结果 JSON 写到文件（UTF-8 + LF）。"
        "比 shell 重定向可靠——PowerShell 的 `>` 默认写 UTF-16 且会二次损坏中文。",
    )
    return parent


COMMON = _common_flags()


def _cmd_config_publish_repo(args, paths: Paths) -> int:
    resolved = Config(paths).set_publish_repo(Path(args.path))
    result = Result(
        status="success",
        summary="已指定看板发布仓",
        checks=[{"name": "dashboard_repo", "level": "ok", "detail": str(resolved)}],
    )
    return _emit(result, args)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ir", description="IR 工作台 Control Plane", parents=[COMMON]
    )
    parser.add_argument("--version", action="version", version=f"ir {VERSION}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_doctor = sub.add_parser("doctor", help="环境自检", parents=[COMMON])
    p_doctor.add_argument("--verbose", action="store_true")
    p_doctor.set_defaults(func=_cmd_doctor)

    p_status = sub.add_parser("status", help="按域报告当前状态", parents=[COMMON])
    p_status.add_argument("--domain", help="只看某一个域")
    p_status.set_defaults(func=_cmd_status)

    p_domains = sub.add_parser("domains", help="列出全部域及迁移状态", parents=[COMMON])
    p_domains.set_defaults(func=_cmd_domains)

    p_hyg = sub.add_parser("hygiene", help="仓库卫生：换行符归一为 LF", parents=[COMMON])
    p_hyg.add_argument("--fix", action="store_true", help="实际改写（默认只报告）")
    p_hyg.set_defaults(func=_cmd_hygiene)

    _register_domain_commands(sub)

    p_config = sub.add_parser("config", help="本机配置")
    config_sub = p_config.add_subparsers(dest="config_command", required=True)
    c_show = config_sub.add_parser("show", help="显示当前配置", parents=[COMMON])
    c_show.set_defaults(func=_cmd_config_show)
    c_cand = config_sub.add_parser("candidates", help="列出候选工作簿（不代选）", parents=[COMMON])
    c_cand.set_defaults(func=_cmd_config_candidates)
    c_set = config_sub.add_parser("set", help="指定工作簿", parents=[COMMON])
    c_set.add_argument("key", choices=sorted(WORKBOOK_KEYS))
    c_set.add_argument("path")
    c_set.set_defaults(func=_cmd_config_set)
    c_pub = config_sub.add_parser(
        "publish-repo", help="指定看板发布仓的本地副本（独立 clone）", parents=[COMMON]
    )
    c_pub.add_argument("path")
    c_pub.set_defaults(func=_cmd_config_publish_repo)

    return parser


def main(argv: list[str] | None = None) -> int:
    _force_utf8_output()
    parser = build_parser()
    args = parser.parse_args(argv)
    paths = Paths(find_root())
    outcome = args.func(args, paths)
    # 域命令直接返回 Result；Control Plane 命令自己已经输出并返回退出码
    if isinstance(outcome, Result):
        return _emit(outcome, args)
    return outcome


if __name__ == "__main__":
    sys.exit(main())
