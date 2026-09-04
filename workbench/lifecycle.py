"""文件生命周期：原件怎么进来、过期什么能删。

规则真源是 ``conventions/file-lifecycle.md``。本模块是那份约定的可执行版本——
文档写了「scratch 14 天可删」却没有命令，约定会慢慢失传。
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from .paths import Paths
from .result import Result

#: 迁入完成后本机不应再放这些目录。若残留，卫生检查跳过、Git 忽略。
FROZEN_LOCAL_DIRS: tuple[str, ...] = (
    "0703_Travel_Pulse",
    "database_matain",
    "peers_rs_update",
    "peers_model_scripts",
    "update-shareholder-list",
)

#: ``ir hygiene`` 扫换行符时跳过。临时产物和冻结目录都不该被改写。
SKIP_HYGIENE_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        "__pycache__",
        "scratch",
        "_tmp",
        "dist",
        "build",
        ".venv",
        ".ir-workbench",
        "output",  # 根目录残留，不是 outputs/
        *FROZEN_LOCAL_DIRS,
    }
)

KEEP_NAMES = {".gitkeep", ".gitignore"}

#: 安全桶：``ir hygiene --prune --fix`` 可以删。其它位置只报告、不自动删。
SAFE_PRUNE_BUCKETS: tuple[tuple[str, int, str], ...] = (
    ("scratch", 14, "一次性产物，超 14 天可删"),
    ("_tmp", 0, "历史临时目录，整桶可清"),
    ("output", 0, "根目录残留；真源是 outputs/"),
)

#: 只报告、须人确认后才允许手工删（命令不会 --fix 这些）。
REPORT_ONLY_BUCKETS: tuple[tuple[str, int, str], ...] = (
    ("inputs", 90, "本期原件超 90 天；不自动删，问用户是否还要"),
)


@dataclass(frozen=True)
class PruneItem:
    relative: str
    size: int
    age_days: int
    bucket: str
    auto: bool

    def as_check(self) -> dict[str, str]:
        age = f"{self.age_days} 天" if self.age_days else "立即"
        kind = "可自动清" if self.auto else "只报告"
        return {
            "name": self.relative,
            "level": "warn",
            "detail": f"{self.bucket} · {kind} · {age} · {_size_label(self.size)}",
        }


def _size_label(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / (1024 * 1024):.1f} MB"


def _iter_files(bucket: Path) -> list[Path]:
    if not bucket.exists():
        return []
    found: list[Path] = []
    for path in bucket.rglob("*"):
        if not path.is_file():
            continue
        if path.name in KEEP_NAMES:
            continue
        found.append(path)
    return found


def _age_days(path: Path, now: float) -> int:
    mtime = path.stat().st_mtime
    return max(0, int((now - mtime) / 86400))


def scan(paths: Paths, *, now: float | None = None) -> list[PruneItem]:
    """列出过期文件。``auto=True`` 的才允许 ``--fix`` 删除。"""
    now = time.time() if now is None else now
    items: list[PruneItem] = []
    for relative, max_age, _reason in SAFE_PRUNE_BUCKETS:
        bucket = paths.root / relative
        for path in _iter_files(bucket):
            age = _age_days(path, now)
            if age >= max_age:
                items.append(
                    PruneItem(
                        relative=str(path.relative_to(paths.root)).replace("\\", "/"),
                        size=path.stat().st_size,
                        age_days=age,
                        bucket=relative,
                        auto=True,
                    )
                )
    for relative, max_age, _reason in REPORT_ONLY_BUCKETS:
        bucket = paths.root / relative
        for path in _iter_files(bucket):
            age = _age_days(path, now)
            if age >= max_age:
                items.append(
                    PruneItem(
                        relative=str(path.relative_to(paths.root)).replace("\\", "/"),
                        size=path.stat().st_size,
                        age_days=age,
                        bucket=relative,
                        auto=False,
                    )
                )
    items.sort(key=lambda item: (not item.auto, item.bucket, item.relative))
    return items


def apply(paths: Paths, items: list[PruneItem]) -> list[str]:
    """只删除 ``auto=True`` 的项。返回已删相对路径。"""
    deleted: list[str] = []
    root = paths.root.resolve()
    for item in items:
        if not item.auto:
            continue
        target = (root / item.relative).resolve()
        if not target.is_relative_to(root) or not target.is_file():
            continue
        target.unlink()
        deleted.append(item.relative)
    _remove_empty_dirs(paths, {"scratch", "_tmp", "output"})
    return deleted


def _remove_empty_dirs(paths: Paths, buckets: set[str]) -> None:
    for name in buckets:
        bucket = paths.root / name
        if not bucket.is_dir():
            continue
        for path in sorted(bucket.rglob("*"), key=lambda p: len(p.parts), reverse=True):
            if path.is_dir():
                try:
                    path.rmdir()
                except OSError:
                    pass
        if name in {"_tmp", "output"}:
            try:
                bucket.rmdir()
            except OSError:
                pass
    paths.ensure_containers()


def prune(paths: Paths, *, fix: bool = False, now: float | None = None) -> Result:
    items = scan(paths, now=now)
    auto = [item for item in items if item.auto]
    report_only = [item for item in items if not item.auto]
    checks = [item.as_check() for item in items[:30]]
    total = sum(item.size for item in auto)

    if not items:
        return Result(
            status="success",
            summary="没有过期可清文件。",
            checks=[{"name": "过期文件", "level": "ok", "detail": "安全桶与 inputs 均无超期"}],
        )

    if not fix:
        next_steps = []
        if auto:
            next_steps.append(
                "过期临时文件已列出。要删除请明确说「确认删除过期临时文件」。"
            )
        if report_only:
            next_steps.append(
                "inputs 里有超 90 天的原件：只报告，不自动删。还要的留下，不要的请指定。"
            )
        return Result(
            status="partial",
            summary=(
                f"发现 {len(auto)} 个可自动清的过期文件（{_size_label(total)}）"
                + (f"，另有 {len(report_only)} 个原件只报告。" if report_only else "。")
                + "未删除。"
            ),
            checks=checks,
            warnings=[item.relative for item in report_only[:10]],
            next_steps=next_steps,
            data={
                "auto": [item.relative for item in auto],
                "report_only": [item.relative for item in report_only],
                "bytes": total,
            },
        )

    deleted = apply(paths, auto)
    leftover = [item.relative for item in report_only]
    return Result(
        status="success" if not leftover else "partial",
        summary=f"已删除 {len(deleted)} 个过期临时文件。"
        + (f" {len(leftover)} 个原件未动。" if leftover else ""),
        checks=[{"name": name, "level": "ok", "detail": "已删除"} for name in deleted[:20]],
        warnings=leftover[:10],
        data={"deleted": deleted, "report_only": leftover},
    )
