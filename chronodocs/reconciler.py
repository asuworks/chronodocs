import os
import fnmatch
from pathlib import Path
from typing import List, Tuple

from .creation_index import CreationIndex
from .update_index import UpdateIndex
from .config import Config

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
        self._ignore_patterns = set(config.ignore_patterns) | {".creation_index.json", ".update_index.json", "change_log.md"}

    def _is_ignored(self, filepath: Path) -> bool:
        """
        Check if a file should be ignored based on the config, supporting glob patterns.
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
            # In case the phase directory doesn't exist yet.
            return

        # 1. Scan the directory and update indices with new/existing files.
        files_on_disk = {p for p in self.phase_dir.iterdir() if p.is_file() and not self._is_ignored(p)}
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
        current_files_map = {self.creation_index.get_file_key(f): f for f in files_on_disk}

        sorted_files = sorted(
            [
                (entry['recorded_ctime'], current_files_map[entry['key']])
                for entry in all_indexed_files
                if entry['key'] in current_files_map
            ],
            key=lambda x: x[0]
        )

        rename_plan: List[Tuple[Path, Path]] = []
        for i, (_, old_path) in enumerate(sorted_files):
            prefix = f"{i:02d}-"
            current_name = old_path.name

            if current_name.startswith(prefix):
                continue

            # Strip existing numerical prefix if it exists
            if len(current_name) > 3 and current_name[:2].isdigit() and current_name[2] == '-':
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
                print(f"[DRY RUN] Would rename {old_path.name} to {new_path.name}")
            return

        for old_path, new_path in rename_plan:
            try:
                # Use os.rename for atomicity on most platforms
                os.rename(old_path, new_path)
                # Important: update index to reflect the rename
                self.update_index.update_file(new_path, old_path=old_path)
            except OSError as e:
                # Basic error logging
                print(f"Error renaming file {old_path} to {new_path}: {e}")

        # 5. Save the updated indices to disk.
        self.creation_index.save()
        self.update_index.save()
