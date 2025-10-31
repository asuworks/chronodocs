import fnmatch
import logging
import time
from pathlib import Path
from threading import Lock, Timer

from watchdog.events import (
    FileSystemEvent,
    FileSystemEventHandler,
)
from watchdog.observers import Observer

from .config import Config
from .reporter import Reporter

# Basic logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


class DebouncedReportHandler(FileSystemEventHandler):
    """
    An event handler that debounces filesystem events and triggers report generation.
    It uses pattern matching to ignore irrelevant files and prevent feedback loops.
    """

    def __init__(
        self,
        config: Config,
        repo_root: Path,
        phase: str,
        debounce_interval_seconds: float,
        ignore_patterns: list[str],
    ):
        super().__init__()
        self.config = config
        self.repo_root = repo_root
        self.phase = phase
        self.debounce_interval = debounce_interval_seconds
        self.ignore_patterns = ignore_patterns
        self._timer: Timer | None = None
        self._timer_lock = Lock()  # Protects timer state
        self._report_lock = Lock()  # Prevents concurrent report generation
        self._last_report_time = 0.0  # Track last report generation time
        self._min_report_interval = 5.0  # Minimum seconds between report generations

    def _dispatch_report(self):
        """Cancels any pending timer and starts a new one."""
        with self._timer_lock:
            if self._timer is not None:
                self._timer.cancel()

            self._timer = Timer(self.debounce_interval, self._run_report)
            self._timer.start()

    def _run_report(self):
        """The callback that generates the report."""
        # Try to acquire the lock; if we can't, another report is running
        if not self._report_lock.acquire(blocking=False):
            logging.debug("Report generation is already running, skipping trigger.")
            return

        try:
            # Check if enough time has passed since last report generation
            current_time = time.time()
            time_since_last = current_time - self._last_report_time

            if time_since_last < self._min_report_interval:
                logging.debug(
                    f"Skipping report generation: only {time_since_last:.1f}s since last run "
                    f"(min interval: {self._min_report_interval}s)"
                )
                return

            # Determine output path
            phase_dir = self.repo_root / self.config.phase_dir_template.format(
                phase=self.phase
            )
            output_path = phase_dir / "change_log.md"

            logging.info(
                f"Root watcher detected changes. Generating report to '{output_path}'"
            )

            # Generate report
            reporter = Reporter(
                config=self.config, repo_path=self.repo_root, phase=self.phase
            )
            markdown_report = reporter.generate_report()

            # Write report
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(markdown_report)

            self._last_report_time = time.time()  # Update last report time
            logging.info(f"Report generated successfully to '{output_path}'")
        except Exception as e:
            logging.error(f"Error generating report: {e}", exc_info=True)
        finally:
            self._report_lock.release()

    def _is_ignored(self, event: FileSystemEvent) -> bool:
        """
        Checks if the event should be ignored based on ignore patterns.
        Uses fnmatch for glob pattern matching on filenames and checks path components for directories.
        """
        filepath = Path(event.src_path)

        # Check if it's a directory event
        if event.is_directory:
            return True

        for pattern in self.ignore_patterns:
            # Check filename match (for patterns like "*.tmp", ".creation_index.json")
            if fnmatch.fnmatch(filepath.name, pattern.strip("/")):
                logging.debug(
                    f"Ignoring event for file {filepath.name} (matched pattern '{pattern}')"
                )
                return True

            # Check if any path component matches (for directory patterns like ".git/", ".venv/")
            pattern_clean = pattern.strip("/")
            for part in filepath.parts:
                if part == pattern_clean or fnmatch.fnmatch(part, pattern_clean):
                    logging.debug(
                        f"Ignoring event for path {filepath} (matched directory pattern '{pattern}')"
                    )
                    return True

        return False

    def on_any_event(self, event: FileSystemEvent):
        """Catches all non-ignored events and triggers the debounced command."""
        # Ignore read-only events (opened, closed_no_write)
        if event.event_type in ("opened", "closed_no_write"):
            return

        if self._is_ignored(event):
            return

        filepath = Path(event.src_path)
        logging.info(
            f"→ Root event detected: {filepath.name} (type: {event.event_type})"
        )
        self._dispatch_report()


class RootWatcher:
    """Initializes and runs the file system observer for the root directory."""

    def __init__(self, repo_path: Path, config: Config, phase: str):
        self.repo_path = repo_path
        self.config = config
        self.phase = phase
        self.observer = Observer()

    def run(self):
        """Starts the watcher and blocks until a KeyboardInterrupt."""
        if not self.phase:
            logging.error(
                "No phase specified for sentinel watcher. Use 'chronodocs start --phase <name>' instead."
            )
            return

        # Generate initial change log on startup to catch changes made while watcher was stopped
        logging.info("Generating initial change log...")
        try:
            phase_dir = self.repo_path / self.config.phase_dir_template.format(
                phase=self.phase
            )
            output_path = phase_dir / "change_log.md"

            reporter = Reporter(
                config=self.config, repo_path=self.repo_path, phase=self.phase
            )
            markdown_report = reporter.generate_report()

            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(markdown_report)

            logging.info(f"Initial change log generated at '{output_path}'")
        except Exception as e:
            logging.error(f"Error generating initial change log: {e}", exc_info=True)

        debounce_seconds = self.config.debounce_root / 1000.0  # Convert ms to seconds

        event_handler = DebouncedReportHandler(
            self.config,
            self.repo_path,
            self.phase,
            debounce_seconds,
            ignore_patterns=self.config.ignore_patterns,
        )

        self.observer.schedule(event_handler, str(self.repo_path), recursive=True)
        self.observer.start()

        logging.info(
            f"Root (sentinel) watcher started for directory: '{self.repo_path}'"
        )
        logging.info(f"Ignoring patterns: {self.config.ignore_patterns}")
        logging.info("Press Ctrl+C to stop.")

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logging.info("Shutdown signal received.")
        finally:
            self.stop()

    def stop(self):
        """Stops the file system observer."""
        if self.observer.is_alive():
            self.observer.stop()
            self.observer.join()
        logging.info("Root watcher stopped.")
