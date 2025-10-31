import fnmatch
import logging
import os
import random
import time
from pathlib import Path
from threading import Event, Lock, Timer

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from .config import Config
from .reporter import Reporter

# Basic logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


class RootEventHandler(FileSystemEventHandler):
    """A simple event handler that delegates to the main watcher class."""

    def __init__(self, watcher: "RootWatcher"):
        super().__init__()
        self.watcher = watcher

    def on_any_event(self, event: FileSystemEvent):
        """Catches all non-ignored events and triggers the debounced command."""
        # Ignore read-only events (opened, closed_no_write)
        if event.event_type in ("opened", "closed_no_write"):
            return

        if self.watcher._is_ignored(event):
            return

        filepath = Path(event.src_path)
        logging.info(
            f"→ Root event detected: {filepath.name} (type: {event.event_type})"
        )
        self.watcher._request_reconcile()


class RootWatcher:
    """Initializes and runs the file system observer for the root directory."""

    def __init__(
        self,
        repo_path: Path,
        config: Config,
        phase: str,
        debounce_interval: float = None,
        min_reconcile_interval: float = None,
        reconcile_done_event: Event = None,
    ):
        self.repo_path = repo_path
        self.config = config
        self.phase = phase
        self.observer = Observer()
        self.reconcile_done_event = reconcile_done_event

        self.debounce_interval = (
            debounce_interval
            if debounce_interval is not None
            else self.config.debounce_root / 1000.0
        )
        self.min_reconcile_interval = (
            min_reconcile_interval
            if min_reconcile_interval is not None
            else getattr(self.config, "min_interval_root", 5000) / 1000.0
        )

        self._timer: Timer | None = None
        self._timer_lock = Lock()
        self._report_lock = Lock()
        self._last_report_time = 0.0

    def _is_ignored(self, event: FileSystemEvent) -> bool:
        """
        Checks if the event should be ignored based on ignore patterns.
        Uses fnmatch for glob pattern matching on filenames and checks path components for directories.
        """
        filepath = Path(event.src_path)

        # Check if it's a directory event
        if event.is_directory:
            return True

        for pattern in self.config.ignore_patterns:
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

    def _request_reconcile(self):
        """Cancels any pending timer and starts a new one with a slight jitter."""
        with self._timer_lock:
            if self._timer is not None:
                self._timer.cancel()

            jitter = random.uniform(0, 0.1)  # Reduced jitter
            interval = self.debounce_interval + jitter
            self._timer = Timer(interval, self._reconcile_and_report)
            self._timer.start()

    def _reconcile_and_report(self):
        """The callback that generates the report."""
        if not self._report_lock.acquire(blocking=False):
            logging.debug("Report generation is already running, skipping trigger.")
            return

        try:
            current_time = time.time()
            time_since_last = current_time - self._last_report_time

            if time_since_last < self.min_reconcile_interval:
                logging.debug(
                    f"Skipping report: {time_since_last:.1f}s < {self.min_reconcile_interval}s"
                )
                # Reschedule for later if an event came in during the cooldown
                with self._timer_lock:
                    if self._timer:
                        self._timer.cancel()
                    # Reschedule to run after the cooldown period has passed
                    delay = self.min_reconcile_interval - time_since_last
                    self._timer = Timer(delay, self._reconcile_and_report)
                    self._timer.start()
                # Do not signal completion, as the work is deferred
                return

            phase_dir = self.repo_path / self.config.phase_dir_template.format(
                phase=self.phase
            )
            output_path = phase_dir / "change_log.md"
            logging.info(f"Generating report to '{output_path}'")

            reporter = Reporter(
                config=self.config, repo_path=self.repo_path, phase=self.phase
            )
            markdown_report = reporter.generate_report()

            output_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = output_path.with_suffix(".md.tmp")
            temp_path.write_text(markdown_report, encoding="utf-8")
            os.replace(temp_path, output_path)

            self._last_report_time = time.time()
            logging.info(f"Report generated successfully to '{output_path}'")

            # Signal that work is done
            if self.reconcile_done_event:
                self.reconcile_done_event.set()

        except Exception as e:
            logging.error(f"Error generating report: {e}", exc_info=True)
            # Also signal on error so the test doesn't hang
            if self.reconcile_done_event:
                self.reconcile_done_event.set()
        finally:
            self._report_lock.release()

    def run(self):
        """Starts the watcher and blocks until a KeyboardInterrupt."""
        if not self.phase:
            logging.error(
                "No phase specified for sentinel watcher. Use 'chronodocs start --phase <name>' instead."
            )
            return

        # Generate initial change log on startup
        logging.info("Running initial reconciliation and report...")
        self._reconcile_and_report()

        event_handler = RootEventHandler(self)
        self.observer.schedule(event_handler, str(self.repo_path), recursive=True)
        self.observer.start()

        logging.info(
            f"Root (sentinel) watcher started for directory: '{self.repo_path}'"
        )
        logging.info(f"Ignoring patterns: {self.config.ignore_patterns}")
        logging.info("Press Ctrl+C to stop.")

        try:
            while self.observer.is_alive():
                self.observer.join(1)
        except KeyboardInterrupt:
            logging.info("Shutdown signal received.")
        finally:
            self.stop()

    def stop(self):
        """Stops the file system observer."""
        with self._timer_lock:
            if self._timer:
                self._timer.cancel()
        if self.observer.is_alive():
            self.observer.stop()
            self.observer.join()
        logging.info("Root watcher stopped.")
