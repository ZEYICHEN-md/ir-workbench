"""内部生成器。工作台入口只有 `ir shareholder-list rebuild`。"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from workbench.paths import Paths, find_root

from . import DOMAIN, adversarial_audit
from .build import VALID_AS_OF, Paths as BuildPaths, build, output_filename, period_key
from .discover import MARKET_CAPS, default_combined, default_peer, default_template
from .validate import validate


def valid_as_date() -> date:
    y, m, d = VALID_AS_OF.replace("-", "/").split("/")
    return date(int(y), int(m), int(d))


def default_output(root: Path | None = None) -> Path:
    paths = Paths(root or find_root())
    return paths.outputs(DOMAIN, period_key()) / output_filename()


def main(argv: list[str] | None = None) -> int:
    root = find_root()
    p = argparse.ArgumentParser(
        description="Build Investor List xlsx from Peer Holdings + Combined Ownership extracts"
    )
    p.add_argument("--peer", type=Path, default=None, help="Peer Ownership-Holdings xlsx")
    p.add_argument("--combined", type=Path, default=None, help="Institution Combined Ownership xlsx")
    p.add_argument("--template", type=Path, default=None, help="Prior Investor List xlsx (skeleton)")
    p.add_argument("--output", type=Path, default=None, help="Defaults to outputs/shareholder-list/<period>/")
    p.add_argument("--market", type=Path, default=MARKET_CAPS)
    p.add_argument(
        "--refresh-market",
        action="store_true",
        help="Fetch Yahoo market caps / USD/HKD / TCOM shares outstanding before building",
    )
    p.add_argument(
        "--audit",
        action="store_true",
        help="After a successful build, run the adversarial audit in the same process",
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
        args.output = default_output(root)

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
        from .market import save_market

        print(f"refreshing market caps into {args.market}", file=sys.stderr)
        save_market(args.market)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    print(f"peer={peer}", file=sys.stderr)
    print(f"combined={combined}", file=sys.stderr)
    print(f"template={template}", file=sys.stderr)
    print(f"output={args.output}", file=sys.stderr)
    stats = build(
        BuildPaths(
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
        audit_report = adversarial_audit.run_audit(
            output=args.output,
            peer=peer,
            combined=combined,
            template=template,
            market_path=args.market,
            report_path=args.output.parent / "adversarial_audit.json",
        )
        if audit_report["n_findings"]:
            return 1
    return 0
