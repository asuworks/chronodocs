import argparse
import sys
import threading
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

from .config import ConfigError, get_config
from .reconciler import Reconciler
from .reporter import Reporter
from .watcher_phase import PhaseWatcher
from .watcher_root import RootWatcher

console = Console()


class RichArgumentParser(argparse.ArgumentParser):
    """Custom ArgumentParser that uses rich for formatted error messages."""

    def error(self, message):
        """Override error method to use rich formatting."""
        # Check for common typos and provide suggestions
        if "unrecognized arguments:" in message:
            args_part = message.split("unrecognized arguments:")[1].strip()
            console.print(
                f"[bold red]✗ Error:[/bold red] Unrecognized argument: [yellow]{args_part}[/yellow]"
            )
            console.print()

            # Try to suggest correct argument
            if "--" in args_part:
                typo_arg = args_part.split()[0]
                # Common typos mapping
                suggestions = {
                    "--outptu": "--output",
                    "--ouput": "--output",
                    "--ouptut": "--output",
                    "--fase": "--phase",
                    "--phse": "--phase",
                    "--repo-rot": "--repo-root",
                    "--dry-ru": "--dry-run",
                }

                suggestion = suggestions.get(typo_arg)
                if suggestion:
                    console.print(
                        f"[bold]Did you mean:[/bold] [green]{suggestion}[/green]?"
                    )
                    console.print()
        else:
            console.print(f"[bold red]✗ Error:[/bold red] {message}")
            console.print()

        console.print("[dim]Use [cyan]--help[/cyan] to see available options[/dim]")
        self.exit(2)

    def print_help(self, file=None):
        """Override print_help to use rich formatting."""
        if file is None:
            console.print(self.format_help())
        else:
            super().print_help(file)


def print_error(message: str, details: str = None):
    """Print a styled error message."""
    console.print(f"[bold red]✗ Error:[/bold red] {message}")
    if details:
        console.print(f"  [dim]{details}[/dim]")


def print_success(message: str):
    """Print a styled success message."""
    console.print(f"[bold green]✓[/bold green] {message}")


def print_info(message: str):
    """Print a styled info message."""
    console.print(f"[bold cyan]ℹ[/bold cyan] {message}")


def print_warning(message: str):
    """Print a styled warning message."""
    console.print(f"[bold yellow]⚠[/bold yellow] {message}")


def handle_config_error(error: ConfigError, repo_root: Path):
    """Handle configuration errors gracefully with helpful suggestions."""
    error_msg = str(error)

    print_error("Configuration Error", error_msg)
    console.print()

    # Provide helpful suggestions based on the error
    if "not found" in error_msg.lower():
        console.print("[bold]Suggestions:[/bold]")
        console.print(
            "  1. Create a [cyan].chronodocs.yml[/cyan] file in your project root"
        )
        console.print(
            "  2. Use [cyan]--repo-root[/cyan] to specify a different project directory"
        )
        console.print()
        console.print("[bold]Example .chronodocs.yml:[/bold]")

        example_config = """phase_dir_template: ".devcontext/progress/{phase}"
watch_paths:
  - "."
ignore_patterns:
  - ".git/**"
  - "node_modules/**"
  - "__pycache__/**"
debounce:
  phase: 2000
  root: 3000
report:
  extensions: [".md", ".py", ".txt"]
  group_by: "updated_day_then_folder"
  sort_by: "updated_desc"
logging:
  level: "INFO"
  format: "text"
"""
        console.print(
            Panel(example_config, border_style="cyan", title=".chronodocs.yml")
        )
    elif "invalid yaml" in error_msg.lower():
        console.print("[bold]Suggestions:[/bold]")
        console.print("  1. Check your YAML syntax (indentation, colons, etc.)")
        console.print("  2. Use a YAML validator to identify the issue")
        console.print("  3. Compare with the example in the documentation")

    return 1


def main():
    """Main entry point for the ChronoDocs CLI."""
    parser = RichArgumentParser(
        description="ChronoDocs: A temporal custodian for your documentation."
    )
    subparsers = parser.add_subparsers(
        dest="command", required=True, help="Available commands"
    )

    # --- Report Command ---
    report_parser = subparsers.add_parser(
        "report", help="Generate a change log for all watched files."
    )
    report_parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="The file to write the report to. If not specified, outputs to stdout.",
    )
    report_parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path("."),
        help="The root of the repository. Defaults to the current directory.",
    )

    # --- Reconcile Command ---
    reconcile_parser = subparsers.add_parser(
        "reconcile", help="Manually reconcile a phase directory."
    )
    reconcile_parser.add_argument(
        "--phase", required=True, type=str, help="The name of the phase directory."
    )
    reconcile_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview the renames without applying them.",
    )
    reconcile_parser.add_argument(
        "--repo-root", type=Path, default=Path("."), help="The root of the repository."
    )

    # --- Watch Command ---
    watch_parser = subparsers.add_parser(
        "watch", help="Start the watcher for a phase directory."
    )
    watch_parser.add_argument(
        "--phase", required=True, type=str, help="The name of the phase directory."
    )
    watch_parser.add_argument(
        "--repo-root", type=Path, default=Path("."), help="The root of the repository."
    )

    # --- Sentinel Command ---
    sentinel_parser = subparsers.add_parser(
        "sentinel", help="Start the root (sentinel) watcher for the repository."
    )
    sentinel_parser.add_argument(
        "--phase",
        required=True,
        type=str,
        help="The phase name (determines where to save change_log.md).",
    )
    sentinel_parser.add_argument(
        "--repo-root", type=Path, default=Path("."), help="The root of the repository."
    )

    # --- Start Command ---
    start_parser = subparsers.add_parser(
        "start", help="Start both phase watcher and sentinel watcher together."
    )
    start_parser.add_argument(
        "--phase",
        required=True,
        type=str,
        help="The name of the phase directory to watch.",
    )
    start_parser.add_argument(
        "--repo-root", type=Path, default=Path("."), help="The root of the repository."
    )

    try:
        args = parser.parse_args()
    except SystemExit as e:
        # argparse calls sys.exit on error, catch it to return proper exit code
        return e.code if e.code is not None else 1

    # Load configuration with error handling
    try:
        config = get_config(args.repo_root)
    except ConfigError as e:
        return handle_config_error(e, args.repo_root)
    except Exception as e:
        print_error("Unexpected error loading configuration", str(e))
        return 1

    # All commands need to calculate the phase_dir, so we can do it once
    if hasattr(args, "phase") and args.phase:
        phase_dir_template = config.phase_dir_template
        phase_dir = args.repo_root / phase_dir_template.format(phase=args.phase)
    else:
        phase_dir = None

    try:
        if args.command == "report":
            with console.status("[bold cyan]Generating report...[/bold cyan]"):
                reporter = Reporter(config=config, repo_path=args.repo_root, phase=None)
                markdown_report = reporter.generate_report()

            if args.output:
                try:
                    args.output.parent.mkdir(parents=True, exist_ok=True)
                    args.output.write_text(markdown_report)
                    print_success(f"Report written to [cyan]{args.output}[/cyan]")
                except Exception as e:
                    print_error(f"Failed to write report to {args.output}", str(e))
                    return 1
            else:
                console.print(markdown_report)

        elif args.command == "reconcile":
            try:
                # Reconciler will create the directory if it doesn't exist
                reconciler = Reconciler(phase_dir=phase_dir, config=config)

                if args.dry_run:
                    print_info("Running in dry-run mode (no changes will be made)")

                reconciler.reconcile(dry_run=args.dry_run)

                if not args.dry_run:
                    print_success(
                        f"Reconciliation complete for phase '[cyan]{args.phase}[/cyan]'"
                    )
                else:
                    print_info(
                        "Dry-run complete. Use without --dry-run to apply changes."
                    )
            except Exception as e:
                print_error(f"Reconciliation failed for phase '{args.phase}'", str(e))
                return 1

        elif args.command == "watch":
            try:
                if not phase_dir.exists():
                    print_error(
                        f"Phase directory not found: {phase_dir}",
                        f"Make sure phase '{args.phase}' exists or check your phase_dir_template in .chronodocs.yml",
                    )
                    return 1

                print_info(f"Starting phase watcher for '[cyan]{args.phase}[/cyan]'...")
                print_info("Press [bold]Ctrl+C[/bold] to stop")

                watcher = PhaseWatcher(phase_dir=phase_dir, config=config)
                watcher.run()
            except KeyboardInterrupt:
                print_info("Stopping phase watcher...")
            except Exception as e:
                print_error("Phase watcher failed", str(e))
                return 1

        elif args.command == "sentinel":
            try:
                print_info(
                    f"Starting sentinel watcher for phase '[cyan]{args.phase}[/cyan]'..."
                )
                print_info("Press [bold]Ctrl+C[/bold] to stop")

                watcher = RootWatcher(
                    repo_path=args.repo_root, config=config, phase=args.phase
                )
                watcher.run()
            except KeyboardInterrupt:
                print_info("Stopping sentinel watcher...")
            except Exception as e:
                print_error("Sentinel watcher failed", str(e))
                return 1

        elif args.command == "start":
            try:
                if not phase_dir.exists():
                    print_warning(f"Phase directory does not exist: {phase_dir}")
                    console.print(f"  Creating directory: [cyan]{phase_dir}[/cyan]")
                    phase_dir.mkdir(parents=True, exist_ok=True)

                # Create both watchers
                phase_watcher = PhaseWatcher(phase_dir=phase_dir, config=config)
                sentinel_watcher = RootWatcher(
                    repo_path=args.repo_root, config=config, phase=args.phase
                )

                console.print()
                console.print(
                    Panel.fit(
                        f"[bold cyan]ChronoDocs Started[/bold cyan]\n\n"
                        f"Phase: [yellow]{args.phase}[/yellow]\n"
                        f"Phase Directory: [dim]{phase_dir}[/dim]\n"
                        f"Repository Root: [dim]{args.repo_root}[/dim]\n\n"
                        f"[dim]Press Ctrl+C to stop all watchers[/dim]",
                        border_style="cyan",
                    )
                )
                console.print()

                # Run phase watcher in a separate thread
                phase_thread = threading.Thread(target=phase_watcher.run, daemon=True)
                phase_thread.start()

                # Run sentinel watcher in the main thread (so Ctrl+C works properly)
                try:
                    sentinel_watcher.run()
                except KeyboardInterrupt:
                    console.print()
                    print_info("Stopping all watchers...")
                    phase_watcher.stop()
                    sentinel_watcher.stop()
                    phase_thread.join(timeout=2)
                    print_success("All watchers stopped")
            except Exception as e:
                print_error("Failed to start watchers", str(e))
                return 1

    except KeyboardInterrupt:
        print_info("Operation cancelled by user")
        return 0
    except Exception as e:
        print_error("Unexpected error", str(e))
        import traceback

        console.print("[dim]" + traceback.format_exc() + "[/dim]")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
