"""环境自检。

目标：让「能不能跑」这件事由系统回答，而不是靠接手人读 traceback。
每个失败项都必须给出人话的下一步。
"""

from __future__ import annotations

import importlib.util
import sys

from . import domain_state, domains
from .config import WORKBOOK_KEYS, Config
from .lifecycle import FROZEN_LOCAL_DIRS
from .paths import Paths
from .result import Result

MIN_PYTHON = (3, 14)


def _domain_checks(paths: Paths) -> dict[str, list[dict]]:
    """收集各域健康检查；缺失或导入失败本身就是显式故障。"""
    collected: dict[str, list[dict]] = {}
    for definition in domains.DOMAINS.values():
        if not paths.module(definition.key).is_dir():
            continue
        try:
            health = domain_state.load_health(definition)
        except domain_state.DomainLoadError as error:
            collected[definition.key] = [
                {
                    "name": "健康检查装载",
                    "level": "fail",
                    "detail": str(error),
                    "advice": f"这是 {definition.key} 的模块装载问题，需要维护人处理。",
                }
            ]
            continue
        try:
            rows = health.checks(paths)
        except Exception as error:  # noqa: BLE001 —— 单个域的检查崩了不该让 doctor 整体挂掉
            rows = [
                {
                    "name": "健康检查",
                    "level": "fail",
                    "detail": f"检查本身出错：{type(error).__name__}: {error}",
                    "advice": f"这是 {health.__name__} 的 bug，需要维护人看。",
                }
            ]
        if rows:
            collected[definition.key] = rows
    return collected

#: 已迁入域必需的依赖。缺了对应能力就跑不了，所以报 fail 而不是 warn。
#: 与 `pyproject.toml` 的 `dependencies` 一一对应——那边是安装清单，这边是运行时自检。
REQUIRED_DEPS: dict[str, str] = {
    "openpyxl": "读写 Excel（行业数据、航空月度、shareholder list）",
    "pdfplumber": "读 PDF（民航局月报）",
    "requests": "抓取官方数据与 RSS",
    "bs4": "解析公告页面与新闻精选导出",
    "markdown": "新闻精选导出 HTML",
    "pandas": "港股行情与成交额聚合",
    "akshare": "港股指数、行情与成交额",
    "yfinance": "美股成交额与港股回退行情",
}

#: 可选依赖。缺了不挡主路径，doctor 只提示。
PENDING_DEPS: dict[str, str] = {
    # news-digest 已迁入，但 PDF 导出另要 `playwright install chromium`，
    # 放主依赖会让首次安装很重；缺它只影响 PDF，HTML 照常出。
    "playwright": "导出 PDF（新闻精选，可选）",
}


def run(paths: Paths, *, verbose: bool = False) -> Result:
    checks: list[dict] = []
    missing: list[str] = []
    warnings: list[str] = []
    next_steps: list[str] = []

    # 1. Python 版本
    version = sys.version_info[:3]
    if version[:2] >= MIN_PYTHON:
        checks.append({"name": "Python 版本", "level": "ok", "detail": ".".join(map(str, version))})
    else:
        checks.append(
            {
                "name": "Python 版本",
                "level": "fail",
                "detail": f"当前 {'.'.join(map(str, version))}，需要 3.14+",
            }
        )
        missing.append("Python 3.14 或更高版本")
        next_steps.append("请维护人协助升级 Python 到 3.14+，然后重新做一次环境检查。")

    # 2. 目录骨架
    #    先补齐纯容器目录——它们缺了不影响运行，让人处理是白费一趟。
    #    `scratch/` 被 .gitignore 忽略，所以新 clone / 新解压必然缺它。
    created = paths.ensure_containers()
    if created:
        checks.append(
            {
                "name": "容器目录",
                "level": "ok",
                "detail": f"已补建 {len(created)} 个："
                + "、".join(str(p.relative_to(paths.root)) for p in created),
            }
        )

    absent = [p for p in paths.required_dirs if not p.is_dir()]
    if absent:
        checks.append(
            {
                "name": "目录骨架",
                "level": "fail",
                "detail": f"缺 {len(absent)} 个：" + "、".join(str(p.relative_to(paths.root)) for p in absent),
            }
        )
        missing.extend(str(p.relative_to(paths.root)) for p in absent)
        next_steps.append(
            "这些目录本该带内容，缺了说明安装不完整（zip 没解压全 / clone 出错）。"
            "请维护人重新安装一次。"
        )
    else:
        checks.append({"name": "目录骨架", "level": "ok", "detail": f"{len(paths.required_dirs)} 个目录齐全"})

    leftover_trees = [name for name in FROZEN_LOCAL_DIRS if (paths.root / name).is_dir()]
    if leftover_trees:
        checks.append(
            {
                "name": "搭建残留",
                "level": "warn",
                "detail": "根目录里还有：" + "、".join(leftover_trees),
            }
        )
        warnings.append("这些旧文件夹不是工作台入口，不要往里面放东西。")
        next_steps.append("对 Agent 说「清理根目录里的旧项目文件夹」；确认后再删。")
    else:
        checks.append({"name": "搭建残留", "level": "ok", "detail": "根目录没有旧仓残留"})

    # 3. 域运行时：目录、CLI 与 health 分开核对，禁止目录存在即报“已迁入”。
    runtime_states = {
        definition.key: domain_state.probe(paths, definition)
        for definition in domains.DOMAINS.values()
    }
    absent_domains = []
    load_errors = []
    for key, state in runtime_states.items():
        if not state.module_present:
            absent_domains.append(domains.get(key).zh)
        elif not state.cli_loaded:
            load_errors.append(f"{domains.get(key).zh}：{state.cli_error}")
        elif not state.health_loaded:
            load_errors.append(f"{domains.get(key).zh}：{state.health_error}")
    if load_errors:
        checks.append({"name": "域运行时", "level": "fail", "detail": "；".join(load_errors)})
        missing.extend(load_errors)
        next_steps.append("请维护人修复上述域的模块导入错误，再重新做环境检查。")
    elif absent_domains:
        checks.append(
            {
                "name": "域运行时",
                "level": "warn",
                "detail": (
                    f"{len(domains.DOMAINS) - len(absent_domains)}/{len(domains.DOMAINS)} 个域就绪；"
                    "尚未安装：" + "、".join(absent_domains)
                ),
            }
        )
        warnings.append("部分域模块尚未安装；Control Plane 可用，相关业务能力暂不可用。")
    else:
        checks.append(
            {
                "name": "域运行时",
                "level": "ok",
                "detail": f"{len(domains.DOMAINS)} 个域的目录、CLI 与 health 全部就绪",
            }
        )

    # 4. 工作簿配置（绝不代选）
    config = Config(paths)
    for key, desc in WORKBOOK_KEYS.items():
        chosen = config.workbook(key)
        if chosen and chosen.is_file():
            checks.append({"name": f"工作簿 · {key}", "level": "ok", "detail": chosen.name})
        elif chosen:
            checks.append({"name": f"工作簿 · {key}", "level": "fail", "detail": f"配置指向的文件不存在：{chosen}"})
            missing.append(f"{key} 工作簿（配置里的路径已失效）")
            next_steps.append(f"把新的 {desc.split('——')[0].strip()} 放进 data/workbooks/，再让 Agent 重新指定。")
        else:
            candidates = config.candidates(key)
            detail = f"未指定；data/workbooks/ 下有 {len(candidates)} 个候选" if candidates else "未指定，且没有候选文件"
            checks.append({"name": f"工作簿 · {key}", "level": "warn", "detail": detail})
            warnings.append(f"{key} 工作簿尚未指定。")
            if candidates:
                next_steps.append(
                    f"{key}：候选有 " + "、".join(c.name for c in candidates) + "。请**你**指定用哪一份，系统不会替你猜。"
                )
            else:
                next_steps.append(f"把 {desc.split('——')[0].strip()} 放进 data/workbooks/。")

    # 5. 中文参数编码（Windows 上会静默损坏，见 ADR 0007）
    probe = "上线验证"
    try:
        console_cp = getattr(sys.stdout, "encoding", None) or "?"
        probe.encode(console_cp)
        checks.append({"name": "中文输出编码", "level": "ok", "detail": console_cp})
    except (UnicodeEncodeError, LookupError):
        checks.append(
            {
                "name": "中文输出编码",
                "level": "warn",
                "detail": f"当前 {console_cp}，中文可能损坏",
            }
        )
        warnings.append(
            "调用方的编码不是 UTF-8。传中文参数（备注、标签）可能变乱码。"
        )
        next_steps.append(
            "在 PowerShell 里先执行一次："
            "`[Console]::OutputEncoding=[Text.Encoding]::UTF8; $OutputEncoding=[Text.Encoding]::UTF8`"
        )

    # 6. 各域自己的健康检查（doctor 不懂域内细节，只汇总）
    for domain_key, rows in _domain_checks(paths).items():
        zh = domains.get(domain_key).zh
        for row in rows:
            checks.append(
                {
                    "name": f"{zh} · {row['name']}",
                    "level": row["level"],
                    "detail": row.get("detail", ""),
                }
            )
            if row["level"] == "fail":
                missing.append(f"{zh} · {row['name']}：{row.get('detail', '')}")
            elif row["level"] == "warn":
                warnings.append(f"{zh} · {row['name']}：{row.get('detail', '')}")
            advice = row.get("advice")
            if advice and row["level"] in {"fail", "warn"}:
                next_steps.append(advice)

    # 7. 依赖：主路径缺了就是 fail，可选依赖缺了只提示
    absent_required = [name for name in REQUIRED_DEPS if importlib.util.find_spec(name) is None]
    if absent_required:
        checks.append(
            {
                "name": "必需依赖",
                "level": "fail",
                "detail": f"缺 {len(absent_required)} 个：" + "、".join(absent_required),
            }
        )
        for name in absent_required:
            missing.append(f"{name}（{REQUIRED_DEPS[name]}）")
        next_steps.append("对 Agent 说「安装工作台依赖」。")
    else:
        checks.append({"name": "必需依赖", "level": "ok", "detail": f"{len(REQUIRED_DEPS)} 个齐全"})

    absent_pending = [name for name in PENDING_DEPS if importlib.util.find_spec(name) is None]
    if absent_pending:
        checks.append(
            {
                "name": "可选依赖",
                "level": "ok",
                "detail": f"缺 {len(absent_pending)} 个（仅影响可选能力，属正常）",
            }
        )

    # 汇总
    if any(c["level"] == "fail" for c in checks):
        status, summary = "blocked", "环境检查未通过，有项目需要处理。"
    elif any(c["level"] == "warn" for c in checks):
        status, summary = "partial", "环境基本可用，但有几项需要补。"
    else:
        status, summary = "success", "环境检查全部通过。"

    return Result(
        status=status,
        summary=summary,
        checks=checks,
        missing=missing,
        warnings=warnings,
        next_steps=next_steps,
        data={"root": str(paths.root)} if verbose else {},
    )
