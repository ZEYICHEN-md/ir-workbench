"""跑一卷或第一期四题。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from workbench.fileio import write_text
from workbench.paths import Paths
from workbench.result import Result

from . import PAPER_IDS, WORKFLOW_REV
from .candidate import SkillCandidate
from .examiner import attachments_for, choose_say, should_stop, wait_satisfied
from .harness import (
    ExamState,
    Turn,
    apply_clock,
    compact_transcript,
    four_state_in,
    make_sandbox,
    restore_env,
)
from .judge import judge
from .loader import PaperError, list_papers, load_paper


def _record_examiner(state: ExamState, text: str, attachments: list[Path]) -> None:
    state.turns.append(
        Turn(
            role="examiner",
            text=text,
            attachments=[path.name for path in attachments],
        )
    )


def _record_candidate(state: ExamState, text: str) -> None:
    state.turns.append(
        Turn(role="candidate", text=text, four_state=four_state_in(text))
    )


def run_paper(paper_id: str, source_root: Path) -> dict:
    paper = load_paper(paper_id)
    state = make_sandbox(source_root, paper)
    previous = apply_clock(state)
    candidate = SkillCandidate(state)
    try:
        script = list((paper.env.get("examiner") or {}).get("script") or [])
        max_turns = int((paper.env.get("examiner") or {}).get("max_turns") or 8)
        for step in script:
            idle = 0
            while step.get("wait_until") and not wait_satisfied(step.get("wait_until"), state) and idle < 2:
                reply = candidate.continue_work()
                if reply and reply != state.last_candidate_text():
                    _record_candidate(state, reply)
                idle += 1
            say = choose_say(step, state)
            files = attachments_for(step, state)
            if not say and not files:
                continue
            _record_examiner(state, say, files)
            reply = candidate.handle(say, files)
            _record_candidate(state, reply)
            if should_stop(state, step):
                break
            if len([t for t in state.turns if t.role == "examiner"]) >= max_turns:
                break
        transcript = compact_transcript(state)
        scorecard = judge(paper, transcript)
        return {
            "paper_id": paper_id,
            "workflow_rev": paper.workflow_rev,
            "transcript": transcript,
            "scorecard": scorecard,
            "sandbox": str(state.paths.root),
        }
    finally:
        restore_env(previous)


def _write_run(out_dir: Path, results: list[dict]) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    for row in results:
        paper_dir = out_dir / row["paper_id"]
        paper_dir.mkdir(parents=True, exist_ok=True)
        write_text(paper_dir / "compact-transcript.json", json.dumps(row["transcript"], ensure_ascii=False, indent=2) + "\n")
        write_text(paper_dir / "scorecard.json", json.dumps(row["scorecard"], ensure_ascii=False, indent=2) + "\n")
    summary = {
        "workflow_rev": WORKFLOW_REV,
        "ran_at": datetime.now(timezone.utc).isoformat(),
        "papers": [
            {
                "id": row["paper_id"],
                "hard_pass": row["scorecard"]["hard_pass"],
                "quality": row["scorecard"]["quality"],
                "improvement": row["scorecard"]["improvement"],
            }
            for row in results
        ],
        "hard_pass_count": sum(1 for row in results if row["scorecard"]["hard_pass"]),
        "n": len(results),
    }
    target = out_dir / "summary.json"
    write_text(target, json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    return target


def run_exam(base: Paths, *, paper: str | None = None, keep: str | None = None) -> Result:
    """``ir news exam`` 入口。"""
    if paper == "list" or paper == "--list":
        papers = list_papers()
        return Result(
            status="success",
            summary="新闻精选考卷：" + "、".join(papers),
            domain="news-digest",
            data={"papers": papers},
        )
    wanted = [paper] if paper else list(PAPER_IDS)
    missing = [item for item in wanted if item not in list_papers()]
    if missing:
        return Result(
            status="blocked",
            summary="题目卷面不在仓库里：" + "、".join(missing),
            domain="news-digest",
            missing=missing,
        )
    results = []
    errors = []
    for paper_id in wanted:
        try:
            results.append(run_paper(paper_id, base.root))
        except PaperError as error:
            errors.append(str(error))
        except Exception as error:  # noqa: BLE001 — 单题失败不该吞掉其余三题
            errors.append(f"{paper_id}: {type(error).__name__}: {error}")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = Path(keep) if keep else (base.root / "modules" / "news_digest" / "exam" / "runs" / f"v1-{stamp}")
    summary_path = _write_run(out_dir, results) if results else out_dir / "summary.json"
    checks = []
    for row in results:
        card = row["scorecard"]
        checks.append({
            "name": row["paper_id"],
            "level": "ok" if card["hard_pass"] else "fail",
            "detail": f"硬性={'通过' if card['hard_pass'] else '失败'} 质量={card['quality']} {card['improvement']}",
        })
    for err in errors:
        checks.append({"name": "错误", "level": "fail", "detail": err})
    passed = sum(1 for row in results if row["scorecard"]["hard_pass"])
    status = "success" if results and passed == len(wanted) and not errors else (
        "partial" if passed else "failed"
    )
    return Result(
        status=status,
        summary=f"新闻精选考卷第一期：硬性通过 {passed}/{len(wanted)}。成绩单 {summary_path}",
        domain="news-digest",
        checks=checks,
        warnings=errors,
        data={
            "summary": str(summary_path),
            "out_dir": str(out_dir),
            "workflow_rev": WORKFLOW_REV,
            "papers": [
                {
                    "id": row["paper_id"],
                    "hard_pass": row["scorecard"]["hard_pass"],
                    "quality": row["scorecard"]["quality"],
                }
                for row in results
            ],
        },
        next_steps=[] if passed == len(wanted) else ["看各题 scorecard.json 的 hard_checks 与 improvement。"],
    )
