import datetime
import fnmatch
import os
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib.parse import quote

from .config import Config
from .git_helpers import GitInfoProvider
from .update_index import UpdateIndex


class Reporter:
    """Generates a Markdown change log for files in the project based on watch_paths and ignore_patterns."""

    def __init__(self, config: Config, repo_path: Path, phase: str = None):
        self.config = config
        self.repo_path = repo_path
        self.phase = phase

        # Calculate phase directory for relative link generation
        self.phase_dir = None
        if self.phase:
            phase_dir_template = (
                config.phase_dir_template or ".devcontext/progress/{phase}"
            )
            phase_dir_str = phase_dir_template.replace("{phase}", self.phase)
            self.phase_dir = self.repo_path / phase_dir_str

        # Initialize UpdateIndex in phase directory if phase is specified, otherwise repo root
        update_index_path = (
            self.phase_dir / ".update_index.json"
            if self.phase_dir
            else repo_path / ".update_index.json"
        )
        self.update_index = UpdateIndex(update_index_path)

        # Build ignore patterns, excluding the index files and change_log
        self._ignore_patterns = set(config.ignore_patterns) | {
            ".creation_index.json",
            ".update_index.json",
            "change_log.md",
        }

    def _is_ignored(self, filepath: Path) -> bool:
        """
        Check if a file should be ignored based on ignore patterns.
        Uses fnmatch for glob pattern matching on filenames and checks path components.
        """
        # Check filename match (for patterns like "*.tmp", ".creation_index.json")
        for pattern in self._ignore_patterns:
            if fnmatch.fnmatch(filepath.name, pattern.strip("/")):
                return True

            # Check if any path component matches (for directory patterns like ".git/", ".venv/")
            pattern_clean = pattern.strip("/")
            for part in filepath.parts:
                if part == pattern_clean or fnmatch.fnmatch(part, pattern_clean):
                    return True

        return False

    def _should_include(self, filepath: Path) -> bool:
        """Check if a file should be included in the report based on extension."""
        extensions = self.config.report_extensions
        if not extensions:
            return True
        return filepath.suffix in extensions

    def _collect_files(self) -> List[Path]:
        """
        Collect all files from watch_paths that should be included in the report.
        """
        collected_files = []

        for watch_path_str in self.config.watch_paths:
            watch_path = self.repo_path / watch_path_str

            if not watch_path.exists():
                continue

            if watch_path.is_file():
                if not self._is_ignored(watch_path) and self._should_include(
                    watch_path
                ):
                    collected_files.append(watch_path)
            elif watch_path.is_dir():
                # Recursively walk the directory
                for root, dirs, files in os.walk(watch_path):
                    root_path = Path(root)

                    # Filter out ignored directories
                    dirs[:] = [d for d in dirs if not self._is_ignored(root_path / d)]

                    # Collect files
                    for filename in files:
                        filepath = root_path / filename
                        if not self._is_ignored(filepath) and self._should_include(
                            filepath
                        ):
                            collected_files.append(filepath)

        return collected_files

    def _get_file_info(
        self, filepath: Path, git_info: GitInfoProvider
    ) -> Dict[str, Any]:
        """Gathers all necessary information for a single file."""
        try:
            relative_path_str = str(filepath.relative_to(self.repo_path))
        except ValueError:
            relative_path_str = str(filepath)

        status = git_info.get_status(filepath)
        created_ts = git_info.get_creation_time(filepath)
        if not created_ts:
            try:
                created_ts = os.path.getctime(filepath)
            except OSError:
                created_ts = os.path.getmtime(filepath)
        updated_ts = git_info.get_last_modified_time(filepath, self.update_index)
        if not updated_ts:
            try:
                updated_ts = os.path.getmtime(filepath)
            except OSError:
                updated_ts = created_ts
        return {
            "path": filepath,
            "relative_path": relative_path_str,
            "status": status,
            "created": datetime.datetime.fromtimestamp(created_ts),
            "updated": datetime.datetime.fromtimestamp(updated_ts),
        }

    def generate_report(self) -> str:
        """Generates the full Markdown report."""
        all_files = self._collect_files()
        if not all_files:
            return "# Change Log\n\nNo files found matching the watch paths and extensions."

        git_info = GitInfoProvider(self.repo_path)
        all_files_info = []
        for filepath in all_files:
            try:
                info = self._get_file_info(filepath, git_info)
                all_files_info.append(info)
            except Exception as e:
                print(f"Warning: Could not process {filepath}: {e}")
                continue

        # Grouping based on config (default: by updated day)
        group_by = self.config.report_group_by or "updated_day"
        grouped_files = self._group_files(all_files_info, group_by)

        # Sorting groups
        sort_by = self.config.report_sort_by or "updated_desc"
        sorted_groups = self._sort_groups(grouped_files, sort_by)

        return self._render_markdown(sorted_groups, len(all_files_info))

    def _group_files(
        self, files_info: List[Dict], group_by: str
    ) -> Dict[str, List[Dict]]:
        """Group files based on the grouping strategy."""
        grouped = defaultdict(list)

        for info in files_info:
            if group_by == "updated_day":
                key = info["updated"].strftime("%Y-%m-%d")
            elif group_by == "created_day":
                key = info["created"].strftime("%Y-%m-%d")
            elif group_by == "folder":
                key = str(info["path"].parent.relative_to(self.repo_path))
            elif group_by == "status":
                key = info["status"]
            else:
                key = info["updated"].strftime("%Y-%m-%d")

            grouped[key].append(info)

        return grouped

    def _sort_groups(
        self, grouped: Dict[str, List[Dict]], sort_by: str
    ) -> List[Tuple[str, List[Dict]]]:
        """Sort groups based on the sorting strategy."""
        if sort_by == "updated_desc":
            return sorted(grouped.items(), key=lambda item: item[0], reverse=True)
        elif sort_by == "updated_asc":
            return sorted(grouped.items(), key=lambda item: item[0])
        elif sort_by == "created_desc":
            return sorted(grouped.items(), key=lambda item: item[0], reverse=True)
        elif sort_by == "created_asc":
            return sorted(grouped.items(), key=lambda item: item[0])
        else:
            return sorted(grouped.items(), key=lambda item: item[0], reverse=True)

    def _get_relative_link(self, file_path: Path) -> str:
        """Calculate relative path from phase directory to the file for markdown links.
        Returns URL-encoded path to handle spaces and special characters."""
        if not self.phase_dir:
            # If no phase directory, use relative path from repo root
            try:
                relative = str(file_path.relative_to(self.repo_path))
            except ValueError:
                relative = str(file_path)
        else:
            try:
                # Calculate relative path from phase directory to the file
                relative = os.path.relpath(file_path, self.phase_dir)
            except (ValueError, OSError):
                # Fallback to relative from repo root
                try:
                    relative = str(file_path.relative_to(self.repo_path))
                except ValueError:
                    relative = str(file_path)

        # URL-encode the path to handle spaces and special characters
        # Use forward slashes for markdown links (works on all platforms)
        path_parts = relative.replace(os.sep, "/").split("/")
        encoded_parts = [quote(part) for part in path_parts]
        return "/".join(encoded_parts)

    def _render_markdown(
        self, sorted_groups: List[Tuple[str, List[Dict]]], total_files: int
    ) -> str:
        """Renders the collected file information into a Markdown string."""
        md = "# Project Change Log\n\n"
        md += f"**Generated:** {datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
        if self.phase:
            md += f"**Phase:** {self.phase}\n"
        md += f"**Total files:** {total_files}\n\n"

        status_map = {
            "new": "🟢 new",
            "modified": "🟡 modified",
            "staged": "🔵 staged",
            "committed": "⚪ committed",
            "deleted": "🔴 deleted",
        }

        for group_key, files in sorted_groups:
            md += f"## {group_key}\n\n"
            md += "| File | Status | Created | Updated |\n"
            md += "| ---- | ------ | --------: | --------: |\n"

            # Sort files within the group by updated time descending
            sorted_files = sorted(files, key=lambda f: f["updated"], reverse=True)

            for info in sorted_files:
                relative_path = info["relative_path"]
                link_path = self._get_relative_link(info["path"])
                status_text = status_map.get(info["status"], info["status"])
                created_str = info["created"].strftime("%Y-%m-%d %H:%M:%S")
                updated_str = info["updated"].strftime("%Y-%m-%d %H:%M:%S")
                md += f"| [`{relative_path}`]({link_path}) | {status_text} | {created_str} | {updated_str} |\n"
            md += "\n"

        md += "---\n\n"
        md += "### Definitions\n"
        md += "- **🟢 new**: Not yet staged/committed\n"
        md += "- **🟡 modified**: Unstaged changes\n"
        md += "- **🔵 staged**: Staged for commit\n"
        md += "- **⚪ committed**: In git history with no local changes\n"

        return md
