"""环境自检。

目标：让「能不能跑」这件事由系统回答，而不是靠接手人读 traceback。
每个失败项都必须给出人话的下一步。
"""

from __future__ import annotations

import importlib.util
import sys

from . import domains
from .config import WORKBOOK_KEYS, Config
from .paths import Paths
from .result import Result

MIN_PYTHON = (3, 14)


def _domain_checks(paths: Paths) -> dict[str, list[dict]]:
    """收集已迁入各域的健康检查。

    约定：`modules/<包>/health.py` 暴露 `checks(base) -> list[dict]`。
    没有这个文件的域跳过——不强制每个域都实现。
    """
    import importlib

    collected: dict[str, list[dict]] = {}
    for key in domains.DOMAINS:
        if not paths.module(key).is_dir():
            continue
        module_name = f"modules.{key.replace('-', '_')}.health"
        try:
            health = importlib.import_module(module_name)
        except ImportError:
            continue
        try:
            rows = health.checks(paths)
        except Exception as error:  # noqa: BLE001 —— 单个域的检查崩了不该让 doctor 整体挂掉
            rows = [
                {
                    "name": "健康检查",
                    "level": "fail",
                    "detail": f"检查本身出错：{type(error).__name__}: {error}",
                    "advice": f"这是 {module_name} 的 bug，需要维护人看。",
                }
            ]
        if rows:
            collected[key] = rows
    return collected

#: 可选依赖：缺了只影响部分能力，不阻塞工作台
OPTIONAL_DEPS: dict[str, str] = {
    "openpyxl": "读写 Excel（行业数据、航空月度）",
    "docx": "读写 Word（Peers 业绩总结、Appendix）",
    "pdfplumber": "读 PDF（卖方研报、财报原件）",
    "requests": "抓取官方数据与新闻",
    "playwright": "导出 PDF（新闻精选交付件）",
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
        next_steps.append("对 Agent 说「修复工作台目录结构」。")
    else:
        checks.append({"name": "目录骨架", "level": "ok", "detail": f"{len(paths.required_dirs)} 个目录齐全"})

    # 3. 模块目录
    absent_modules = [d for d in domains.DOMAINS if not paths.module(d).is_dir()]
    if absent_modules:
        checks.append(
            {
                "name": "模块",
                "level": "warn",
                "detail": f"{len(domains.DOMAINS) - len(absent_modules)}/{len(domains.DOMAINS)} 已就位，"
                + "尚未迁入：" + "、".join(domains.get(d).zh for d in absent_modules),
            }
        )
        warnings.append("部分模块还没迁进工作台，相关能力暂不可用（迁移进行中，属正常）。")
    else:
        checks.append({"name": "模块", "level": "ok", "detail": f"{len(domains.DOMAINS)} 个模块全部就位"})

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

    # 7. 可选依赖
    absent_deps = [name for name in OPTIONAL_DEPS if importlib.util.find_spec(name) is None]
    if absent_deps:
        checks.append(
            {
                "name": "可选依赖",
                "level": "warn",
                "detail": f"缺 {len(absent_deps)} 个：" + "、".join(absent_deps),
            }
        )
        for name in absent_deps:
            warnings.append(f"缺 {name}，影响：{OPTIONAL_DEPS[name]}")
        next_steps.append("对 Agent 说「安装工作台依赖」。")
    else:
        checks.append({"name": "可选依赖", "level": "ok", "detail": f"{len(OPTIONAL_DEPS)} 个全部可用"})

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
