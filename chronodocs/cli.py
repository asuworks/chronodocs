import argparse
from pathlib import Path
import sys

from .config import get_config
from .reporter import Reporter
from .reconciler import Reconciler
from .watcher_phase import PhaseWatcher
from .watcher_root import RootWatcher

def main():
    """Main entry point for the ChronoDocs CLI."""
    parser = argparse.ArgumentParser(description="ChronoDocs: A temporal custodian for your documentation.")
    subparsers = parser.add_subparsers(dest="command", required=True, help="Available commands")

    # --- Report Command ---
    report_parser = subparsers.add_parser("report", help="Generate a change log for a phase.")
    report_parser.add_argument(
        "--phase",
        required=True,
        type=str,
        help="The name of the phase directory to generate the report for."
    )
    report_parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="The file to write the report to. Defaults to stdout."
    )
    report_parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path('.'),
        help="The root of the repository. Defaults to the current directory."
    )

    # --- Reconcile Command ---
    reconcile_parser = subparsers.add_parser("reconcile", help="Manually reconcile a phase directory.")
    reconcile_parser.add_argument("--phase", required=True, type=str, help="The name of the phase directory.")
    reconcile_parser.add_argument("--dry-run", action="store_true", help="Preview the renames without applying them.")
    reconcile_parser.add_argument("--repo-root", type=Path, default=Path('.'), help="The root of the repository.")

    # --- Watch Command ---
    watch_parser = subparsers.add_parser("watch", help="Start the watcher for a phase directory.")
    watch_parser.add_argument("--phase", required=True, type=str, help="The name of the phase directory.")
    watch_parser.add_argument("--repo-root", type=Path, default=Path('.'), help="The root of the repository.")

    # --- Sentinel Command ---
    sentinel_parser = subparsers.add_parser("sentinel", help="Start the root (sentinel) watcher for the repository.")
    sentinel_parser.add_argument("--repo-root", type=Path, default=Path('.'), help="The root of the repository.")


    args = parser.parse_args()

    config = get_config(args.repo_root)

    # All commands need to calculate the phase_dir, so we can do it once
    if hasattr(args, 'phase') and args.phase:
        phase_dir_template = config.phase_dir_template
        phase_dir = args.repo_root / phase_dir_template.format(phase=args.phase)
    else:
        phase_dir = None


    if args.command == "report":
        reporter = Reporter(phase_dir=phase_dir, config=config, repo_path=args.repo_root)
        markdown_report = reporter.generate_report()
        if args.output:
            args.output.write_text(markdown_report)
            print(f"Report written to {args.output}")
        else:
            sys.stdout.write(markdown_report)

    elif args.command == "reconcile":
        reconciler = Reconciler(phase_dir=phase_dir, config=config)
        reconciler.reconcile(dry_run=args.dry_run)
        if not args.dry_run:
            print(f"Reconciliation complete for phase '{args.phase}'.")

    elif args.command == "watch":
        watcher = PhaseWatcher(phase_dir=phase_dir, config=config)
        watcher.run()

    elif args.command == "sentinel":
        watcher = RootWatcher(repo_path=args.repo_root, config=config)
        watcher.run()

if __name__ == "__main__":
    main()
