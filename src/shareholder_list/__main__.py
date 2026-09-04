"""CLI: python -m shareholder_list --peer ... --combined ..."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from shareholder_list.build import VALID_AS_OF, Paths, build, output_filename
from shareholder_list.discover import default_combined, default_peer, default_template
from shareholder_list.validate import validate


def repo_root() -> Path:
    """Prefer the cwd used by rebuild.ps1 so a worktree does not write the parent output/."""
    cwd = Path.cwd()
    if (cwd / "src" / "shareholder_list" / "build.py").exists() and (cwd / "scripts" / "rebuild.ps1").exists():
        return cwd
    return Path(__file__).resolve().parents[2]


def valid_as_date() -> date:
    y, m, d = VALID_AS_OF.replace("-", "/").split("/")
    return date(int(y), int(m), int(d))


def main(argv: list[str] | None = None) -> int:
    root = repo_root()
    p = argparse.ArgumentParser(
        description="Build Investor List xlsx from Peer Holdings + Combined Ownership extracts"
    )
    p.add_argument("--peer", type=Path, default=None, help="Peer Ownership-Holdings xlsx")
    p.add_argument("--combined", type=Path, default=None, help="Institution Combined Ownership xlsx")
    p.add_argument("--template", type=Path, default=None, help="Prior Investor List xlsx (skeleton)")
    p.add_argument("--output", type=Path, default=None, help="Defaults to output/Investor List_YYYYMMDD.xlsx from VALID_AS_OF")
    p.add_argument("--market", type=Path, default=root / "data" / "market_caps.json")
    p.add_argument(
        "--refresh-market",
        action="store_true",
        help="Fetch Yahoo market caps / USD/HKD / TCOM shares outstanding before building",
    )
    p.add_argument(
        "--audit",
        action="store_true",
        help="After a successful build, run scripts/adversarial_audit.py in the same process",
    )
    p.add_argument(
        "--force-refresh",
        action="store_true",
        help="Allow --refresh-market even when today != VALID_AS_OF (overwrites frozen quotes)",
    )
    args = p.parse_args(argv)

    peer = args.peer or default_peer()
    combined = args.combined or default_combined()
    template = args.template or default_template()
    if peer is None or not peer.exists():
        p.error("need --peer (or a Peer Ownership-Holdings-*.xlsx in Downloads)")
    if combined is None or not combined.exists():
        p.error("need --combined (or an Institution Combined Ownership-Public-*.xlsx in Downloads)")
    if template is None or not template.exists():
        p.error("need --template (prior Investor List xlsx)")

    if args.output is None:
        args.output = root / "output" / output_filename()

    if template.resolve() == args.output.resolve() or template.name == output_filename():
        p.error(
            f"template {template} is this cut's output ({output_filename()}). "
            "That snapshots current SH as prior (QoQ all zero). "
            "Pin discover.PRIOR_TEMPLATE to the previous holdings quarter's published list."
        )

    today = date.today()
    locked = valid_as_date()
    print(f"VALID_AS_OF={VALID_AS_OF} today={today.isoformat()}", file=sys.stderr)
    if today != locked:
        print(
            "path=locked-rebuild (calendar is after VALID_AS_OF; do not change dates, do not refresh)",
            file=sys.stderr,
        )
    else:
        print("path=valid-date-is-today (refresh allowed)", file=sys.stderr)

    if args.refresh_market:
        if today != locked and not args.force_refresh:
            p.error(
                f"--refresh-market refused: today={today.isoformat()} != VALID_AS_OF={VALID_AS_OF}. "
                "This is a locked rebuild: omit --refresh-market. "
                "A new cut: first set VALID_AS_OF in build.py to today, then --refresh-market. "
                "Override only with --force-refresh."
            )
        from shareholder_list.market import save_market

        print(f"refreshing market caps into {args.market}", file=sys.stderr)
        save_market(args.market)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    print(f"peer={peer}", file=sys.stderr)
    print(f"combined={combined}", file=sys.stderr)
    print(f"template={template}", file=sys.stderr)
    print(f"output={args.output}", file=sys.stderr)
    stats = build(
        Paths(
            template=template,
            peer=peer,
            combined=combined,
            output=args.output,
            market=args.market,
        )
    )
    report = validate(args.output, peer, combined, args.market)
    print(json.dumps({"build": stats, "validate": report}, indent=2, ensure_ascii=False, default=str))
    if not report["ok"]:
        return 1
    if args.audit:
        import importlib.util

        audit_path = root / "scripts" / "adversarial_audit.py"
        spec = importlib.util.spec_from_file_location("adversarial_audit", audit_path)
        mod = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(mod)
        audit_report = mod.run_audit(
            output=args.output,
            peer=peer,
            combined=combined,
            template=template,
            market_path=args.market,
            report_path=root / "output" / "adversarial_audit.json",
        )
        if audit_report["n_findings"]:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
