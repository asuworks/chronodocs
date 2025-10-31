import time
import logging
import subprocess
import shlex
from pathlib import Path
from threading import Timer

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent, PatternMatchingEventHandler

from .config import Config

# Basic logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

class DebouncedMakeCommandHandler(FileSystemEventHandler):
    """
    An event handler that debounces filesystem events and triggers a make command.
    It uses pattern matching to ignore irrelevant files and prevent feedback loops.
    """

    def __init__(self, make_command: str, repo_root: Path, debounce_interval_seconds: float, ignore_patterns: list[str]):
        super().__init__()
        self.make_command = make_command
        self.repo_root = repo_root
        self.debounce_interval = debounce_interval_seconds
        self.ignore_patterns = ignore_patterns
        self._timer: Timer | None = None
        self._is_running_command = False

    def _dispatch_command(self):
        """Cancels any pending timer and starts a new one."""
        if self._timer is not None:
            self._timer.cancel()

        self._timer = Timer(self.debounce_interval, self._run_command)
        self._timer.start()

    def _run_command(self):
        """The callback that runs the configured make command."""
        if self._is_running_command:
            logging.warning("Make command is already running, skipping trigger.")
            return

        logging.info(f"Root watcher detected changes. Triggering command: '{self.make_command}'")
        self._is_running_command = True
        try:
            # Use shlex.split for robust command parsing
            command_args = shlex.split(self.make_command)
            subprocess.run(
                command_args,
                cwd=self.repo_root,
                check=True,
                capture_output=True,
                text=True
            )
            logging.info(f"Command '{self.make_command}' executed successfully.")
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            error_output = e.stderr if hasattr(e, 'stderr') else 'Command not found or failed to execute.'
            logging.error(f"Error executing '{self.make_command}': {error_output}", exc_info=True)
        finally:
            self._is_running_command = False

    def _is_ignored(self, event: FileSystemEvent) -> bool:
        """
        Checks if the event's source path ends with any of the ignore patterns.
        This is a simple but effective way to ignore files like 'change_log.md'
        or directories like '.git/'.
        """
        src_path_str = event.src_path
        for pattern in self.ignore_patterns:
            if src_path_str.endswith(pattern.strip('/')):
                logging.debug(f"Ignoring event for path {src_path_str} due to pattern '{pattern}'")
                return True
        return False

    def on_any_event(self, event: FileSystemEvent):
        """Catches all non-ignored events and triggers the debounced command."""
        if self._is_ignored(event):
            return
        self._dispatch_command()


class RootWatcher:
    """Initializes and runs the file system observer for the repository root."""

    def __init__(self, repo_path: Path, config: Config):
        self.repo_path = repo_path
        self.config = config
        self.observer = Observer()

    def run(self):
        """Starts the sentinel watcher."""
        make_command = self.config.make_command
        if not make_command:
            logging.error("No 'make_command' specified in the configuration. Sentinel watcher cannot run.")
            return

        debounce_seconds = self.config.debounce_root / 1000.0

        event_handler = DebouncedMakeCommandHandler(
            make_command,
            self.repo_path,
            debounce_seconds,
            ignore_patterns=self.config.ignore_patterns
        )

        self.observer.schedule(event_handler, str(self.repo_path), recursive=True)
        self.observer.start()

        logging.info(f"Root (sentinel) watcher started for directory: '{self.repo_path}'")
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
