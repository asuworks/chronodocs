import json
import hashlib
import os
import time
from pathlib import Path
from typing import Dict, Any, Optional, List
import datetime
from datetime import timezone
class UpdateIndex:
    """
    Manages the .update_index.json file, which tracks content hashes
    and modification times for each document.
    """
    def __init__(self, index_path: Path):
        self.index_path = index_path
        self._entries: Dict[str, Dict[str, Any]] = self._load()

    def _load(self) -> Dict[str, Dict[str, Any]]:
        """Loads the index from the JSON file."""
        if not self.index_path.is_file():
            return {}
        try:
            with open(self.index_path, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}

    def save(self):
        """Saves the index to the JSON file atomically."""
        temp_path = self.index_path.with_suffix('.tmp')
        with open(temp_path, 'w') as f:
            json.dump(self._entries, f, indent=2)
        os.replace(temp_path, self.index_path)

    @staticmethod
    def _calculate_hash(filepath: Path) -> str:
        """Calculates the SHA256 hash of a file's content."""
        hasher = hashlib.sha256()
        with open(filepath, 'rb') as f:
            while chunk := f.read(8192):
                hasher.update(chunk)
        return hasher.hexdigest()

    def update_file(self, filepath: Path, old_path: Optional[Path] = None):
        """
        Updates the index for a file, tracking content changes.
        If old_path is provided, it indicates a rename.
        """
        path_key = str(filepath)
        new_hash = self._calculate_hash(filepath)

        entry = self._entries.get(path_key)
        if old_path and str(old_path) in self._entries:
            # Handle rename
            entry = self._entries.pop(str(old_path))
            self._entries[path_key] = entry

        if entry is None:
            entry = {
                "hash": new_hash,
                "last_content_update": datetime.datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                "path_history": [path_key]
            }
            self._entries[path_key] = entry
        elif entry['hash'] != new_hash:
            entry['hash'] = new_hash
            entry['last_content_update'] = datetime.datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
            if path_key not in entry['path_history']:
                entry['path_history'].append(path_key)

    def remove_file(self, filepath: Path):
        """Removes a file from the index."""
        path_key = str(filepath)
        if path_key in self._entries:
            del self._entries[path_key]

    def get_hash(self, filepath: Path) -> Optional[str]:
        """Gets the stored content hash for a file."""
        entry = self._entries.get(str(filepath))
        return entry['hash'] if entry else None

    def has_changed(self, filepath: Path) -> bool:
        """Checks if a file's content has changed since the last update."""
        current_hash = self._calculate_hash(filepath)
        stored_hash = self.get_hash(filepath)
        return current_hash != stored_hash

    def get_all_entries(self) -> Dict[str, Dict[str, Any]]:
        """Returns all entries in the index."""
        return self._entries.copy()
