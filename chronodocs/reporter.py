from .config import Config
from .creation_index import CreationIndex
from .update_index import UpdateIndex
from .git_helpers import get_git_status, get_file_creation_time, get_file_last_modified_time

import datetime
from pathlib import Path
from typing import List, Dict, Any, Tuple
from collections import defaultdict
import os

class Reporter:
    """Generates a Markdown change log for a phase directory."""

    def __init__(self, phase_dir: Path, config: Config, repo_path: Path):
        self.phase_dir = phase_dir
        self.config = config
        self.repo_path = repo_path
        self.creation_index = CreationIndex(phase_dir / ".creation_index.json")
        self.update_index = UpdateIndex(phase_dir / ".update_index.json")
        self._ignore_patterns = set(config.ignore_patterns) | {".creation_index.json", ".update_index.json", "change_log.md"}
        self.git_statuses = get_git_status(self.repo_path)

    def _is_ignored(self, filepath: Path) -> bool:
        """Check if a file should be ignored."""
        return filepath.name in self._ignore_patterns or any(part in self._ignore_patterns for part in filepath.parts)

    def _get_file_info(self, filepath: Path) -> Dict[str, Any]:
        """Gathers all necessary information for a single file."""
        relative_path_str = str(filepath.relative_to(self.repo_path))

        # 1. Get status
        status = self.git_statuses.get(relative_path_str, "committed")

        # 2. Get creation time
        created_ts = self.creation_index.get_ctime_for_file(filepath)
        if not created_ts:
            created_ts = get_file_creation_time(filepath, self.repo_path)
        if not created_ts:
            created_ts = os.path.getctime(filepath)

        # 3. Get update time
        update_index_entry = self.update_index.get_all_entries().get(str(filepath))
        if update_index_entry:
            updated_ts = datetime.datetime.fromisoformat(update_index_entry['last_content_update'].replace('Z', '+00:00')).timestamp()
        else:
            updated_ts = get_file_last_modified_time(filepath, self.repo_path)
        if not updated_ts:
            updated_ts = os.path.getmtime(filepath)

        return {
            "path": filepath,
            "status": status,
            "created": datetime.datetime.fromtimestamp(created_ts),
            "updated": datetime.datetime.fromtimestamp(updated_ts),
        }

    def generate_report(self) -> str:
        """Generates the full Markdown report."""
        if not self.phase_dir.is_dir():
            return "# Change Log\n\nPhase directory not found."

        all_files_info = [
            self._get_file_info(p)
            for p in self.phase_dir.iterdir()
            if p.is_file() and not self._is_ignored(p)
        ]

        # Grouping (example: by updated day)
        grouped_files = defaultdict(list)
        for info in all_files_info:
            date_str = info['updated'].strftime("%Y-%m-%d")
            grouped_files[date_str].append(info)

        # Sorting groups by date descending
        sorted_groups = sorted(grouped_files.items(), key=lambda item: item[0], reverse=True)

        return self._render_markdown(sorted_groups, len(all_files_info))

    def _render_markdown(self, sorted_groups: List[Tuple[str, List[Dict]]], total_files: int) -> str:
        """Renders the collected file information into a Markdown string."""
        md = f"# Phase Change Log\n\n"
        md += f"**Generated:** {datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
        md += f"**Phase:** {self.phase_dir.name}\n"
        md += f"**Total files:** {total_files}\n\n"

        status_map = {
            "new": "🟢 new",
            "modified": "🟡 modified",
            "staged": "🔵 staged",
            "committed": "⚪ committed",
            "deleted": "🔴 deleted",
        }

        for date, files in sorted_groups:
            md += f"## {date}\n\n"
            md += "| File | Status | Created | Updated |\n"
            md += "| ---- | ------ | --------: | --------: |\n"

            # Sort files within the group by updated time descending
            sorted_files = sorted(files, key=lambda f: f['updated'], reverse=True)

            for info in sorted_files:
                filename = info['path'].name
                status_text = status_map.get(info['status'], info['status'])
                created_str = info['created'].strftime('%Y-%m-%d %H:%M:%S')
                updated_str = info['updated'].strftime('%Y-%m-%d %H:%M:%S')
                md += f"| [`{filename}`](./{filename}) | {status_text} | {created_str} | {updated_str} |\n"
            md += "\n"

        md += "---\n\n"
        md += "### Definitions\n"
        md += "- **🟢 new**: Not yet staged/committed\n"
        md += "- **🟡 modified**: Unstaged changes\n"
        md += "- **🔵 staged**: Staged for commit\n"
        md += "- **⚪ committed**: In git history with no local changes\n"

        return md
