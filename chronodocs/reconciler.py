import fnmatch
import logging
import os
from pathlib import Path
from typing import List, Tuple

from filelock import FileLock, Timeout

from .config import Config
from .creation_index import CreationIndex
from .update_index import UpdateIndex


class Reconciler:
    """
    Orchestrates the reconciliation process for a phase directory.
    It ensures that files are prefixed with a chronological number
    based on their creation time.
    """

    def __init__(self, phase_dir: Path, config: Config):
        self.phase_dir = phase_dir
        self.config = config
        self.creation_index = CreationIndex(phase_dir / ".creation_index.json")
        self.update_index = UpdateIndex(phase_dir / ".update_index.json")

        # Combine config ignore patterns with mandatory ones for reconciler
        default_ignores = {"*.tmp", "*.lock", "~*", ".*.swp"}
        mandatory_ignores = {
            ".creation_index.json",
            ".update_index.json",
            "change_log.md",
        }
        self._ignore_patterns = (
            set(config.ignore_patterns) | mandatory_ignores | default_ignores
        )

    def _is_ignored(self, filepath: Path) -> bool:
        """
        Check if a file should be ignored based on the config, supporting glob patterns.
        This is a simplified version for the reconciler, which only operates on file names.
        """
        for pattern in self._ignore_patterns:
            if fnmatch.fnmatch(filepath.name, pattern):
                return True
        return False

    def reconcile(self, dry_run: bool = False):
        """
        Performs the full reconciliation process:
        1. Scans the directory for changes.
        2. Updates the creation and update indices.
        3. Determines the correct chronological filenames.
        4. Renames files as needed.
        5. Saves the updated indices.
        """
        if not self.phase_dir.is_dir():
            # Create the phase directory if it doesn't exist yet.
            self.phase_dir.mkdir(parents=True, exist_ok=True)

        # 1. Scan the directory and update indices with new/existing files.
        files_on_disk = {
            p
            for p in self.phase_dir.iterdir()
            if p.is_file() and not self._is_ignored(p)
        }
        for filepath in files_on_disk:
            self.creation_index.add_file(filepath)
            self.update_index.update_file(filepath)

        # 2. Remove stale entries from indices (for deleted files).
        indexed_files_by_key = self.creation_index.get_all_entries()
        disk_file_keys = {self.creation_index.get_file_key(f) for f in files_on_disk}
        stale_keys = set(indexed_files_by_key.keys()) - disk_file_keys

        for key in stale_keys:
            stale_entry = indexed_files_by_key.get(key, {})
            filename = stale_entry.get("filename")
            if filename:
                self.update_index.remove_file(self.phase_dir / filename)
            # Directly manipulate the dictionary; a cleaner API would be better.
            if key in self.creation_index._entries:
                del self.creation_index._entries[key]

        # 3. Determine correct ordering and plan renames.
        all_indexed_files = self.creation_index.get_all_entries().values()
        current_files_map = {
            self.creation_index.get_file_key(f): f for f in files_on_disk
        }

        sorted_files = sorted(
            [
                (
                    entry["recorded_ctime"],
                    entry["inode"],
                    current_files_map[entry["key"]],
                )
                for entry in all_indexed_files
                if entry["key"] in current_files_map
            ],
            key=lambda x: (x[0], x[1]),
        )

        rename_plan: List[Tuple[Path, Path]] = []
        for i, (_, _, old_path) in enumerate(sorted_files):
            prefix = f"{i:02d}-"
            current_name = old_path.name

            if current_name.startswith(prefix):
                continue

            # Strip existing numerical prefix if it exists
            if (
                len(current_name) > 3
                and current_name[:2].isdigit()
                and current_name[2] == "-"
            ):
                new_name_base = current_name[3:]
            else:
                new_name_base = current_name

            new_name = f"{prefix}{new_name_base}"
            new_path = old_path.with_name(new_name)

            if old_path != new_path:
                rename_plan.append((old_path, new_path))

        # 4. Execute the rename plan.
        if dry_run:
            for old_path, new_path in rename_plan:
                logging.info(
                    f"[DRY RUN] Would rename {old_path.name} to {new_path.name}"
                )
        else:
            for old_path, new_path in rename_plan:
                lock_path = old_path.with_suffix(f"{old_path.suffix}.lock")
                try:
                    # Lock the file to prevent other processes from modifying it
                    # Timeout after a short period to avoid getting stuck.
                    with FileLock(lock_path, timeout=0.5):
                        logging.debug(f"Acquired lock for {old_path.name}")

                        # Re-check existence to handle cases where the file was
                        # deleted after scanning.
                        if not old_path.exists():
                            logging.warning(
                                f"File {old_path.name} was deleted before renaming, skipping."
                            )
                            continue

                        os.rename(old_path, new_path)
                        logging.info(f"Renamed {old_path.name} to {new_path.name}")

                        # Update index to reflect the rename
                        self.update_index.update_file(new_path, old_path=old_path)

                except Timeout:
                    logging.warning(
                        f"Could not acquire lock for {old_path.name}, another process may be using it. Skipping rename."
                    )
                except OSError as e:
                    logging.error(
                        f"Error renaming file {old_path} to {new_path}: {e}",
                        exc_info=True,
                    )
                finally:
                    # Ensure the lock file is cleaned up
                    if lock_path.exists():
                        lock_path.unlink()

        # 5. Save the updated indices to disk.
        self.creation_index.save()
        self.update_index.save()
