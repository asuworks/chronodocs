import datetime
import subprocess
from datetime import timezone
from pathlib import Path
from typing import TYPE_CHECKING, Dict, Optional

if TYPE_CHECKING:
    from .update_index import UpdateIndex


def _run_git_command(command: list[str], cwd: Path) -> str:
    """Runs a Git command and returns its stdout."""
    try:
        result = subprocess.run(
            ["git"] + command,
            capture_output=True,
            text=True,
            check=True,
            cwd=cwd,
        )
        return result.stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


class GitInfoProvider:
    """
    A class to efficiently fetch and cache Git information for a repository.
    """

    def __init__(self, repo_path: Path):
        self.repo_path = repo_path
        self._statuses: Dict[str, str] = self._fetch_all_statuses()
        self._creation_times: Dict[str, float] = self._fetch_all_creation_times()
        self._modification_times: Dict[str, float] = (
            self._fetch_all_modification_times()
        )

    def _fetch_all_statuses(self) -> Dict[str, str]:
        """Gets the git status for all files in the repository."""
        output = _run_git_command(
            ["status", "--porcelain", "-z", "--untracked-files=all"], cwd=self.repo_path
        )
        if not output:
            return {}

        statuses = {}
        for line in output.strip("\0").split("\0"):
            if not line:
                continue

            status_codes = line[:2]
            filepath = line[3:]

            if " -> " in filepath:
                filepath = filepath.split(" -> ")[1]

            index_status, worktree_status = status_codes[0], status_codes[1]
            status = "committed"

            if worktree_status == "?":
                status = "new"
            elif worktree_status == "M":
                status = "modified"
            elif index_status in ("A", "M", "R"):
                status = "staged"
            elif index_status == "D":
                status = "deleted"
            statuses[filepath] = status
        return statuses

    def _parse_git_log_output(self, output: str) -> Dict[str, float]:
        times = {}
        commits = output.strip().split("---")[
            1:
        ]  # Split by --- and remove first empty string
        for commit in commits:
            lines = commit.strip().split("\n")
            if not lines:
                continue

            timestamp_str = lines[0]
            if not timestamp_str.isdigit():
                continue

            timestamp = float(timestamp_str)
            files = lines[1:]
            for file in files:
                if file and file not in times:
                    times[file] = timestamp
        return times

    def _fetch_all_creation_times(self) -> Dict[str, float]:
        """Gets the creation time for all files from their first git commit."""
        output = _run_git_command(
            [
                "log",
                "--reverse",
                "--diff-filter=A",
                "--pretty=format:---\n%at",
                "--name-only",
            ],
            cwd=self.repo_path,
        )
        return self._parse_git_log_output(output)

    def _fetch_all_modification_times(self) -> Dict[str, float]:
        """Gets the last modification time for all committed files."""
        output = _run_git_command(
            ["log", "--pretty=format:---\n%at", "--name-only"], cwd=self.repo_path
        )
        return self._parse_git_log_output(output)

    def get_status(self, filepath: Path) -> str:
        """Returns the cached git status for a file."""
        try:
            relative_path = str(filepath.relative_to(self.repo_path))
            return self._statuses.get(relative_path, "committed")
        except ValueError:
            return "committed"

    def get_creation_time(self, filepath: Path) -> Optional[float]:
        """Returns the cached creation time for a file."""
        try:
            relative_path = str(filepath.relative_to(self.repo_path))
            return self._creation_times.get(relative_path)
        except ValueError:
            return None

    def get_last_modified_time(
        self, filepath: Path, update_index: "UpdateIndex"
    ) -> Optional[float]:
        """
        Gets the last modification time. If the file is new or modified,
        it checks if the content has actually changed before updating the timestamp.
        """
        try:
            relative_path = str(filepath.relative_to(self.repo_path))
            status = self.get_status(filepath)

            # For new or modified files, check if content has changed
            if status in ("modified", "new"):
                if update_index.has_changed(filepath):
                    # Content has changed, so update the index and return current time
                    update_index.update_file(filepath)
                    update_index.save()
                    return datetime.datetime.now(timezone.utc).timestamp()
                else:
                    # Content is the same, return the last known update time
                    entry = update_index.get_all_entries().get(str(filepath))
                    if entry and "last_content_update" in entry:
                        return datetime.datetime.fromisoformat(
                            entry["last_content_update"].replace("Z", "+00:00")
                        ).timestamp()

            # For committed files, return the git modification time
            git_time = self._modification_times.get(relative_path)
            if git_time:
                return git_time

            # Fallback for untracked but unchanged files
            entry = update_index.get_all_entries().get(str(filepath))
            if entry and "last_content_update" in entry:
                return datetime.datetime.fromisoformat(
                    entry["last_content_update"].replace("Z", "+00:00")
                ).timestamp()

            # Final fallback to filesystem mtime
            import os

            return os.path.getmtime(filepath)

        except (ValueError, OSError):
            return None
