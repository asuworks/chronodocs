import logging
import random
import time
from pathlib import Path
from threading import Lock, Timer

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from .config import Config
from .reconciler import Reconciler

# Basic logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


class DebouncedReconcilerHandler(FileSystemEventHandler):
    """
    An event handler that debounces filesystem events and triggers a Reconciler.
    This prevents the reconciler from running multiple times during a rapid
    burst of file changes (e.g., when an editor saves a file).
    """

    def __init__(
        self,
        reconciler: Reconciler,
        debounce_interval_seconds: float,
        min_reconcile_interval_seconds: float = 5.0,
    ):
        self.reconciler = reconciler
        self.debounce_interval = debounce_interval_seconds
        self._timer: Timer | None = None
        self._timer_lock = Lock()
        self._reconcile_lock = Lock()
        self._last_reconcile_time = 0.0
        self._min_reconcile_interval = min_reconcile_interval_seconds

    def _dispatch_reconciliation(self):
        """Cancels any pending timer and starts a new one with a slight jitter."""
        with self._timer_lock:
            if self._timer is not None:
                self._timer.cancel()

            jitter = random.uniform(0, 1)
            interval = self.debounce_interval + jitter
            self._timer = Timer(interval, self._run_reconciliation)
            self._timer.start()

    def _run_reconciliation(self):
        """The callback that performs the reconciliation."""
        # Try to acquire the lock; if we can't, another reconciliation is running
        if not self._reconcile_lock.acquire(blocking=False):
            logging.debug("Reconciliation is already in progress, skipping trigger.")
            return

        try:
            # Check if enough time has passed since last reconciliation
            current_time = time.time()
            time_since_last = current_time - self._last_reconcile_time

            if time_since_last < self._min_reconcile_interval:
                logging.debug(
                    f"Skipping reconciliation: only {time_since_last:.1f}s since last run "
                    f"(min interval: {self._min_reconcile_interval}s)"
                )
                return

            logging.info(
                f"Changes detected in '{self.reconciler.phase_dir}'. Debounce timer expired. Running reconciliation..."
            )
            self.reconciler.reconcile()
            self._last_reconcile_time = time.time()  # Update last reconciliation time
            logging.info("Reconciliation complete.")
        except Exception as e:
            logging.error(
                f"An error occurred during reconciliation: {e}", exc_info=True
            )
        finally:
            self._reconcile_lock.release()

    def on_any_event(self, event: FileSystemEvent):
        """Catches all events and triggers the debounced reconciliation."""
        # We only care about events for actual files, not directories.
        if event.is_directory:
            return

        # Ignore read-only events (opened, closed_no_write)
        if event.event_type in ("opened", "closed_no_write"):
            return

        # Also ignore changes to files that are explicitly ignored.
        filepath = Path(event.src_path)

        # Log the full path for debugging
        logging.debug(f"Event received: {event.event_type} for {event.src_path}")

        if self.reconciler._is_ignored(filepath):
            logging.debug(
                f"✓ Ignoring event for file: {filepath.name} (matched ignore pattern)"
            )
            return

        logging.info(
            f"→ Event detected for file: {filepath.name} (type: {event.event_type})"
        )
        self._dispatch_reconciliation()


class PhaseWatcher:
    """Initializes and runs the file system observer for a phase directory."""

    def __init__(
        self,
        phase_dir: Path,
        config: Config,
        debounce_interval: float = None,
        min_reconcile_interval: float = None,
    ):
        self.phase_dir = phase_dir
        self.config = config
        self.observer = Observer()
        self.debounce_interval = (
            debounce_interval
            if debounce_interval is not None
            else self.config.debounce_phase / 1000.0
        )
        self.min_reconcile_interval = (
            min_reconcile_interval
            if min_reconcile_interval is not None
            else getattr(self.config, "min_interval_phase", 5000) / 1000.0
        )

    def run(self):
        """Starts the watcher and blocks until a KeyboardInterrupt."""
        if not self.phase_dir.is_dir():
            logging.warning(
                f"Phase directory '{self.phase_dir}' not found. Attempting to create it."
            )
            try:
                self.phase_dir.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                logging.error(
                    f"Failed to create phase directory '{self.phase_dir}': {e}"
                )
                return

        reconciler = Reconciler(self.phase_dir, self.config)

        # Run initial reconciliation on startup
        logging.info(f"Running initial reconciliation for '{self.phase_dir}'...")
        try:
            reconciler.reconcile()
            logging.info("Initial reconciliation complete.")
        except Exception as e:
            logging.error(f"Error during initial reconciliation: {e}", exc_info=True)

        event_handler = DebouncedReconcilerHandler(
            reconciler, self.debounce_interval, self.min_reconcile_interval
        )

        self.observer.schedule(event_handler, str(self.phase_dir), recursive=False)
        self.observer.start()

        logging.info(f"Phase watcher started for directory: '{self.phase_dir}'")
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
        logging.info("Phase watcher stopped.")
