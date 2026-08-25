"""工作台路径解析。

单一真源：所有目录位置只在这里定义一次。
"""

from __future__ import annotations

from pathlib import Path

#: 本机配置目录名（Git 忽略；本机配置与共享代码分离）
LOCAL_DIR_NAME = ".ir-workbench"


def find_root(start: Path | None = None) -> Path:
    """从当前目录向上找工作台根（含 workbench/ 与 docs/GLOSSARY.md 的目录）。"""
    here = (start or Path.cwd()).resolve()
    for candidate in [here, *here.parents]:
        if (candidate / "workbench").is_dir() and (candidate / "docs" / "GLOSSARY.md").is_file():
            return candidate
    raise SystemExit(
        "找不到工作台根目录。请在 IR_workbench 文件夹（或其子目录）里运行。"
    )


class Paths:
    def __init__(self, root: Path) -> None:
        self.root = root

    # --- 共享数据层（跨域，不属于任何单一模块）---
    @property
    def data(self) -> Path:
        return self.root / "data"

    @property
    def workbooks(self) -> Path:
        return self.data / "workbooks"

    @property
    def canonical(self) -> Path:
        return self.data / "canonical"

    @property
    def intel(self) -> Path:
        return self.data / "intel"

    # --- 按域分区 ---
    def inputs(self, domain: str, period: str | None = None) -> Path:
        base = self.root / "inputs" / domain
        return base / period if period else base

    def outputs(self, domain: str, period: str | None = None) -> Path:
        base = self.root / "outputs" / domain
        return base / period if period else base

    def runs(self, domain: str, period: str | None = None) -> Path:
        base = self.root / "runs" / domain
        return base / period if period else base

    def module(self, domain: str) -> Path:
        """域的模块目录。

        域键用连字符（对外可读，如 ``industry-data``），目录与 Python 包用下划线
        （``modules/industry_data``）——同一个名字的两种写法，映射规则只有这一条。
        """
        return self.root / "modules" / domain.replace("-", "_")

    # --- 其他 ---
    @property
    def local(self) -> Path:
        return self.root / LOCAL_DIR_NAME

    @property
    def config_file(self) -> Path:
        return self.local / "config.json"

    @property
    def docs(self) -> Path:
        return self.root / "docs"

    @property
    def scratch(self) -> Path:
        return self.root / "scratch"

    @property
    def dashboard(self) -> Path:
        return self.root / "dashboard"

    #: **有内容**的目录。缺了说明安装不完整（zip 解压不全、clone 出错），必须人处理。
    @property
    def required_dirs(self) -> list[Path]:
        return [
            self.root / "docs",
            self.root / "docs" / "adr",
            self.root / "modules",
            self.root / "router",
            self.root / "conventions",
        ]

    #: **纯容器**目录。缺了不影响运行——用到时各处都会 `mkdir(parents=True)`。
    #:
    #: 之所以单独列出来：`scratch/` 被 .gitignore 整体忽略，所以任何新 clone 或新解压的
    #: 工作台都不会有它。早先把它算进「必需目录」，导致 doctor 报 fail —— CI 因此红，
    #: 接手人首次安装也会撞上同一件事。这类目录该由 doctor 顺手补齐，不该让人处理。
    @property
    def container_dirs(self) -> list[Path]:
        return [
            self.data,
            self.workbooks,
            self.canonical,
            self.intel,
            self.root / "inputs",
            self.root / "outputs",
            self.root / "runs",
            self.scratch,
        ]

    def ensure_containers(self) -> list[Path]:
        """补齐缺失的容器目录。返回**本次新建**的那些。"""
        created = []
        for path in self.container_dirs:
            if not path.is_dir():
                path.mkdir(parents=True, exist_ok=True)
                created.append(path)
        return created
