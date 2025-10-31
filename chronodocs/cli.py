import argparse
from pathlib import Path
import sys

from .config import get_config
from .reporter import Reporter

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

    args = parser.parse_args()

    config = get_config(args.repo_root)

    if args.command == "report":
        phase_dir_template = config.phase_dir_template
        phase_dir = args.repo_root / phase_dir_template.format(phase=args.phase)

        reporter = Reporter(phase_dir=phase_dir, config=config, repo_path=args.repo_root)
        markdown_report = reporter.generate_report()

        if args.output:
            args.output.write_text(markdown_report)
            print(f"Report written to {args.output}")
        else:
            sys.stdout.write(markdown_report)

if __name__ == "__main__":
    main()
