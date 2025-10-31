import logging
import random
import time
from pathlib import Path
from threading import Event, Lock, Timer

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


class PhaseEventHandler(FileSystemEventHandler):
    """A simple event handler that delegates to the main watcher class."""

    def __init__(self, watcher: "PhaseWatcher"):
        super().__init__()
        self.watcher = watcher

    def on_any_event(self, event: FileSystemEvent):
        """Catches all non-ignored events and triggers the debounced reconciliation."""
        if event.is_directory:
            return

        if event.event_type in ("opened", "closed_no_write"):
            return

        filepath = Path(event.src_path)
        if self.watcher.reconciler._is_ignored(filepath):
            logging.debug(f"Ignoring event for ignored file: {filepath.name}")
            return

        logging.info(
            f"→ Phase event detected for file: {filepath.name} (type: {event.event_type})"
        )
        self.watcher._request_reconcile()


class PhaseWatcher:
    """Initializes and runs the file system observer for a phase directory."""

    def __init__(
        self,
        phase_dir: Path,
        config: Config,
        debounce_interval: float = None,
        min_reconcile_interval: float = None,
        reconcile_done_event: Event = None,
    ):
        self.phase_dir = phase_dir
        self.config = config
        self.reconciler = Reconciler(phase_dir, config)
        self.observer = Observer()
        self.reconcile_done_event = reconcile_done_event

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

        self._timer: Timer | None = None
        self._timer_lock = Lock()
        self._reconcile_lock = Lock()
        self._last_reconcile_time = 0.0

    def _request_reconcile(self):
        """Cancels any pending timer and starts a new one with a slight jitter."""
        with self._timer_lock:
            if self._timer is not None:
                self._timer.cancel()

            jitter = random.uniform(0, 0.1)
            interval = self.debounce_interval + jitter
            self._timer = Timer(interval, self._reconcile)
            self._timer.start()

    def _reconcile(self):
        """The callback that performs the reconciliation."""
        if not self._reconcile_lock.acquire(blocking=False):
            logging.debug("Reconciliation is already in progress, skipping trigger.")
            return

        try:
            current_time = time.time()
            time_since_last = current_time - self._last_reconcile_time

            if time_since_last < self.min_reconcile_interval:
                logging.debug(
                    f"Skipping reconcile: {time_since_last:.1f}s < {self.min_reconcile_interval}s"
                )
                # Reschedule for later if an event came in during the cooldown
                with self._timer_lock:
                    if self._timer:
                        self._timer.cancel()
                    # Reschedule to run after the cooldown period has passed
                    delay = self.min_reconcile_interval - time_since_last
                    self._timer = Timer(delay, self._reconcile)
                    self._timer.start()
                # Do not signal completion, as the work is deferred
                return

            logging.info(
                f"Reconciling changes in '{self.reconciler.phase_dir}'..."
            )
            self.reconciler.reconcile()
            self._last_reconcile_time = time.time()
            logging.info("Reconciliation complete.")

            # Signal that work is done
            if self.reconcile_done_event:
                self.reconcile_done_event.set()

        except Exception as e:
            logging.error(f"Error during reconciliation: {e}", exc_info=True)
            # Also signal on error so the test doesn't hang
            if self.reconcile_done_event:
                self.reconcile_done_event.set()
        finally:
            self._reconcile_lock.release()

    def run(self):
        """Starts the watcher and blocks until a KeyboardInterrupt."""
        if not self.phase_dir.is_dir():
            logging.warning(
                f"Phase directory '{self.phase_dir}' not found. Creating it."
            )
            self.phase_dir.mkdir(parents=True, exist_ok=True)

        logging.info(f"Running initial reconciliation for '{self.phase_dir}'...")
        self._reconcile()

        event_handler = PhaseEventHandler(self)
        self.observer.schedule(event_handler, str(self.phase_dir), recursive=False)
        self.observer.start()

        logging.info(f"Phase watcher started for directory: '{self.phase_dir}'")
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
        logging.info("Phase watcher stopped.")
