"""域运行时可用性探测。

模块目录、CLI 装载、健康检查装载和业务验收是四个不同事实；不要再压成一个
``migrated`` 布尔值。业务验收状态由 domains.py 声明，本模块只探测可运行性。
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from types import ModuleType

from .domains import Domain
from .paths import Paths


class DomainLoadError(ImportError):
    """域组件不存在、导入失败或未实现约定接口。"""


@dataclass(frozen=True)
class RuntimeState:
    module_present: bool
    cli_loaded: bool
    health_loaded: bool
    cli_error: str | None = None
    health_error: str | None = None


def _load(definition: Domain, component: str, contract: str) -> ModuleType:
    name = f"modules.{definition.key.replace('-', '_')}.{component}"
    try:
        module = importlib.import_module(name)
    except Exception as error:  # noqa: BLE001 - 状态页必须把域导入故障显式返回
        raise DomainLoadError(f"{name} 导入失败：{type(error).__name__}: {error}") from error
    if not callable(getattr(module, contract, None)):
        raise DomainLoadError(f"{name} 缺少可调用的 {contract}()")
    return module


def load_cli(definition: Domain) -> ModuleType:
    return _load(definition, "cli", "register")


def load_health(definition: Domain) -> ModuleType:
    return _load(definition, "health", "checks")


def probe(paths: Paths, definition: Domain) -> RuntimeState:
    present = paths.module(definition.key).is_dir()
    if not present:
        return RuntimeState(False, False, False, "模块目录不存在", "模块目录不存在")
    errors: dict[str, str | None] = {"cli": None, "health": None}
    loaded: dict[str, bool] = {}
    for component, loader in (("cli", load_cli), ("health", load_health)):
        try:
            loader(definition)
            loaded[component] = True
        except DomainLoadError as error:
            loaded[component] = False
            errors[component] = str(error)
    return RuntimeState(True, loaded["cli"], loaded["health"], errors["cli"], errors["health"])
