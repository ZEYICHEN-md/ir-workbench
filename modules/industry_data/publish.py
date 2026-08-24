"""上线 datamax.fun。

发布链：工作台 `dashboard/travel/` 四文件 → 发布仓本地副本 → push → EdgeOne 自动部署。

这是**对外发布**，门禁最硬：没有明确确认一律停在 dry-run，且先把「线上会变成什么样」
逐行摆出来。今天踩过的坑（CRLF 让整份文件显示为改写、把真变化埋掉）在这里做成了硬检查。
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from workbench.config import Config
from workbench.result import Result

from .paths import DOMAIN, DomainPaths

#: 发布仓根目录下的四个文件。顺序固定，便于比对输出稳定。
PUBLISH_FILES = ("index.html", "data.js", "i18n.js", "insights.js")

#: 单个文件被改动的行数占比超过这个值就视为「整份重写」，拒绝发布。
#: 由来：CRLF 回归会让每一行都算改动，从而把真正的 3 处数据变化埋掉（ADR 0006）。
WHOLE_FILE_REWRITE_RATIO = 0.8


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _repo(base) -> tuple[Path | None, Result | None]:
    configured = Config(base).load()["publish"].get("dashboard_repo")
    if not configured:
        return None, Result(
            status="blocked",
            summary="没有配置看板发布仓的本地副本。",
            domain=DOMAIN,
            next_steps=[
                "发布仓是独立 clone（不是工作台子目录），默认在 D:\\Users\\<你>\\Desktop\\travel-dashboard。",
                "让 Agent 执行 `ir config publish-repo <路径>` 指定它。",
            ],
        )
    repo = Path(configured)
    if not (repo / ".git").is_dir():
        return None, Result(
            status="blocked",
            summary=f"配置的发布仓不是一个 git 仓：{repo}",
            domain=DOMAIN,
            next_steps=["确认路径，或重新 clone 发布仓后再 `ir config publish-repo` 指定。"],
        )
    return repo, None


def _diff_stats(repo: Path, name: str) -> tuple[int, int]:
    """返回 (改动行数, 文件总行数)。"""
    numstat = _git(repo, "diff", "--numstat", "--", name).stdout.strip()
    changed = 0
    if numstat:
        parts = numstat.split("\t")
        if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
            changed = int(parts[0]) + int(parts[1])
    total = 0
    target = repo / name
    if target.is_file():
        total = len(target.read_text(encoding="utf-8", errors="replace").splitlines())
    return changed, total


def run(paths: DomainPaths, base, *, yes: bool = False) -> Result:
    repo, blocked = _repo(base)
    if blocked:
        return blocked

    # 1. 源文件齐不齐
    missing = [name for name in PUBLISH_FILES if not (paths.dashboard_dir / name).is_file()]
    if missing:
        return Result(
            status="blocked",
            summary="工作台里的看板文件不全，未发布。",
            domain=DOMAIN,
            missing=[f"dashboard/travel/{name}" for name in missing],
            next_steps=["先跑 `ir industry generate-dashboard`。"],
        )

    # 2. 源文件换行符（LF）—— 今天踩过的坑，做成硬检查
    crlf = [
        name
        for name in PUBLISH_FILES
        if b"\r\n" in (paths.dashboard_dir / name).read_bytes()
    ]
    if crlf:
        return Result(
            status="blocked",
            summary="看板文件含 CRLF 换行，未发布。",
            domain=DOMAIN,
            missing=crlf,
            next_steps=[
                "CRLF 会让 git 把整份文件当成改写，从而把真正的数据变化埋掉（ADR 0006）。",
                "重新跑 `ir industry generate-dashboard` 生成；仍有 CRLF 说明 fileio 被绕过了。",
            ],
        )

    # 3. 发布仓有没有别人的未提交改动
    dirty = [
        line[3:].strip()
        for line in _git(repo, "status", "--porcelain").stdout.splitlines()
        if line[3:].strip() not in PUBLISH_FILES
    ]
    if dirty:
        return Result(
            status="blocked",
            summary="发布仓里有与本次发布无关的未提交改动，未发布。",
            domain=DOMAIN,
            missing=dirty,
            next_steps=[
                "先把这些改动处理掉（提交或还原），避免把不相关的东西一起推上线。",
            ],
        )

    # 4. 复制并算 diff
    for name in PUBLISH_FILES:
        shutil.copyfile(paths.dashboard_dir / name, repo / name)

    stats = {name: _diff_stats(repo, name) for name in PUBLISH_FILES}
    changed_files = [name for name, (changed, _total) in stats.items() if changed]

    if not changed_files:
        _git(repo, "checkout", "--", *PUBLISH_FILES)
        return Result(
            status="success",
            summary="线上已是最新，无需发布。",
            domain=DOMAIN,
            checks=[{"name": name, "level": "ok", "detail": "无变化"} for name in PUBLISH_FILES],
        )

    # 5. 整份重写守卫
    rewritten = [
        f"{name}：改动 {changed} 行 / 共 {total} 行"
        for name, (changed, total) in stats.items()
        if total and changed / total > WHOLE_FILE_REWRITE_RATIO
    ]
    if rewritten:
        _git(repo, "checkout", "--", *PUBLISH_FILES)
        return Result(
            status="blocked",
            summary="diff 看起来是整份重写，已还原，未发布。",
            domain=DOMAIN,
            missing=rewritten,
            next_steps=[
                "整份重写通常是换行符或格式变了，不是内容变了——这种 diff 没法核对，等于放弃验证。",
                "先查清原因（换行符、JSON 序列化写法、键顺序），再发布。",
            ],
        )

    checks = [
        {
            "name": name,
            "level": "ok" if changed else "ok",
            "detail": f"改动 {changed} 行 / 共 {total} 行" if changed else "无变化",
        }
        for name, (changed, total) in stats.items()
    ]

    # 6. 没有明确确认就停在这里
    if not yes:
        diff_text = _git(repo, "diff", "--", "data.js", "insights.js").stdout
        preview = diff_text.splitlines()
        if len(preview) > 60:
            preview = preview[:60] + [f"…（还有 {len(diff_text.splitlines()) - 60} 行）"]
        _git(repo, "checkout", "--", *PUBLISH_FILES)
        return Result(
            status="partial",
            summary=f"已算出线上会变什么（{len(changed_files)} 个文件），**未发布**。",
            domain=DOMAIN,
            checks=checks,
            next_steps=[
                "逐行核对下面的 diff，确认只有预期的变化。",
                "确认后回一句「上线」，Agent 才会提交并推送。",
                "",
                *preview,
            ],
            data={"changed_files": changed_files, "stats": stats},
        )

    # 7. 提交并推送
    add = _git(repo, "add", *PUBLISH_FILES)
    if add.returncode:
        return Result(status="failed", summary=f"git add 失败：{add.stderr.strip()}", domain=DOMAIN)
    commit = _git(repo, "commit", "-m", "Update travel dashboard from IR workbench")
    if commit.returncode:
        return Result(
            status="failed",
            summary=f"git commit 失败：{(commit.stderr or commit.stdout).strip()}",
            domain=DOMAIN,
        )
    push = _git(repo, "push", "origin", "main")
    if push.returncode:
        return Result(
            status="failed",
            summary=f"git push 失败：{(push.stderr or push.stdout).strip()}",
            domain=DOMAIN,
            next_steps=["本地已 commit，网络或权限恢复后重推即可，不必重新生成。"],
        )

    head = _git(repo, "log", "-1", "--format=%h %s").stdout.strip()
    return Result(
        status="success",
        summary="已推送到发布仓，EdgeOne 会自动部署。",
        domain=DOMAIN,
        checks=[*checks, {"name": "发布仓提交", "level": "ok", "detail": head}],
        next_steps=[
            "等 1～几分钟，打开 https://datamax.fun 硬刷新（Ctrl+F5）核对。",
            "EdgeOne 控制台「构建部署」应出现本次 push 触发的成功记录。",
            "不对就在发布仓 `git revert HEAD` 后重推，线上回到上一版。",
        ],
    )
