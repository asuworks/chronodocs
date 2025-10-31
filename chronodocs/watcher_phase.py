import time
import logging
from pathlib import Path
from threading import Timer

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent

from .reconciler import Reconciler
from .config import Config

# Basic logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

class DebouncedReconcilerHandler(FileSystemEventHandler):
    """
    An event handler that debounces filesystem events and triggers a Reconciler.
    This prevents the reconciler from running multiple times during a rapid
    burst of file changes (e.g., when an editor saves a file).
    """

    def __init__(self, reconciler: Reconciler, debounce_interval_seconds: float):
        self.reconciler = reconciler
        self.debounce_interval = debounce_interval_seconds
        self._timer: Timer | None = None
        self._is_reconciling = False # Re-entrancy guard

    def _dispatch_reconciliation(self):
        """Cancels any pending timer and starts a new one."""
        if self._timer is not None:
            self._timer.cancel()

        self._timer = Timer(self.debounce_interval, self._run_reconciliation)
        self._timer.start()

    def _run_reconciliation(self):
        """The callback that performs the reconciliation."""
        if self._is_reconciling:
            logging.warning("Reconciliation is already in progress, skipping trigger.")
            return

        logging.info(f"Changes detected in '{self.reconciler.phase_dir}'. Debounce timer expired. Running reconciliation...")
        self._is_reconciling = True
        try:
            self.reconciler.reconcile()
            logging.info("Reconciliation complete.")
        except Exception as e:
            logging.error(f"An error occurred during reconciliation: {e}", exc_info=True)
        finally:
            self._is_reconciling = False

    def on_any_event(self, event: FileSystemEvent):
        """Catches all events and triggers the debounced reconciliation."""
        # We only care about events for actual files, not directories.
        if event.is_directory:
            return

        # Also ignore changes to files that are explicitly ignored.
        if self.reconciler._is_ignored(Path(event.src_path)):
             logging.debug(f"Ignoring event for file: {event.src_path}")
             return

        self._dispatch_reconciliation()


class PhaseWatcher:
    """Initializes and runs the file system observer for a phase directory."""

    def __init__(self, phase_dir: Path, config: Config):
        self.phase_dir = phase_dir
        self.config = config
        self.observer = Observer()

    def run(self):
        """Starts the watcher and blocks until a KeyboardInterrupt."""
        if not self.phase_dir.is_dir():
            logging.warning(f"Phase directory '{self.phase_dir}' not found. Attempting to create it.")
            try:
                self.phase_dir.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                logging.error(f"Failed to create phase directory '{self.phase_dir}': {e}")
                return

        reconciler = Reconciler(self.phase_dir, self.config)
        debounce_seconds = self.config.debounce_phase / 1000.0  # Convert ms to seconds

        event_handler = DebouncedReconcilerHandler(reconciler, debounce_seconds)

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
