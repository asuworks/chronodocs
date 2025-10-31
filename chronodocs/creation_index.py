import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

# A unique identifier for a file, combining inode and device ID.
FileKey = str


class CreationIndex:
    """
    Manages the .creation_index.json file, which stores the creation
    time for each document to maintain a stable chronological order.
    """

    def __init__(self, index_path: Path):
        self.index_path = index_path
        self._entries: Dict[FileKey, Dict[str, Any]] = self._load()

    def _load(self) -> Dict[FileKey, Dict[str, Any]]:
        """Loads the index from the JSON file."""
        if not self.index_path.is_file():
            return {}
        try:
            with open(self.index_path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            # If the file is corrupted or unreadable, start fresh.
            return {}

    def save(self):
        """Saves the index to the JSON file atomically."""
        # Ensure parent directory exists
        self.index_path.parent.mkdir(parents=True, exist_ok=True)

        temp_path = self.index_path.with_suffix(".tmp")
        with open(temp_path, "w") as f:
            json.dump(self._entries, f, indent=2)
        os.replace(temp_path, self.index_path)

    @staticmethod
    def get_file_key(filepath: Path) -> FileKey:
        """
        Generates a stable key for a file.
        Uses inode/device on POSIX systems for stability across renames.
        Falls back to the filename on other systems (like Windows).
        """
        if os.name == "posix":
            stat = filepath.stat()
            return f"ino:{stat.st_ino}-dev:{stat.st_dev}"
        else:
            return f"name:{filepath.name}"

    def add_file(self, filepath: Path, recorded_ctime: Optional[float] = None):
        """Adds a new file to the index."""
        key = self.get_file_key(filepath)
        if key in self._entries:
            return  # Already indexed

        if recorded_ctime is None:
            recorded_ctime = time.time()

        entry = {
            "key": key,
            "filename": filepath.name,
            "recorded_ctime": recorded_ctime,
        }
        if os.name == "posix":
            stat = filepath.stat()
            entry["inode"] = stat.st_ino
            entry["device"] = stat.st_dev

        self._entries[key] = entry

    def remove_file(self, filepath: Path):
        """Removes a file from the index."""
        key = self.get_file_key(filepath)
        if key in self._entries:
            del self._entries[key]

    def get_ctime_for_file(self, filepath: Path) -> Optional[float]:
        """Gets the recorded creation time for a file."""
        key = self.get_file_key(filepath)
        entry = self._entries.get(key)
        return entry["recorded_ctime"] if entry else None

    def get_all_entries(self) -> Dict[FileKey, Dict[str, Any]]:
        """Returns all entries in the index."""
        return self._entries.copy()
