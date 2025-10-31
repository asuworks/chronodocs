import subprocess
from pathlib import Path
from typing import Dict, Optional


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
        self._modification_times: Dict[str, float] = self._fetch_all_modification_times()

    def _fetch_all_statuses(self) -> Dict[str, str]:
        """Gets the git status for all files in the repository."""
        output = _run_git_command(["status", "--porcelain", "-z"], cwd=self.repo_path)
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
            if index_status == "A" or worktree_status == "?":
                status = "new"
            elif worktree_status == "M":
                status = "modified"
            elif index_status == "M":
                status = "staged"
            elif index_status == "D":
                status = "deleted"
            elif index_status == "R":
                status = "staged"
            statuses[filepath] = status
        return statuses

    def _parse_git_log_output(self, output: str) -> Dict[str, float]:
        times = {}
        commits = output.strip().split("---")[1:]  # Split by --- and remove first empty string
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
            ["log", "--reverse", "--diff-filter=A", "--pretty=format:---\n%at", "--name-only"],
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

    def get_last_modified_time(self, filepath: Path) -> Optional[float]:
        """
        Gets the last modification time, preferring filesystem for new/modified files.
        """
        try:
            relative_path = str(filepath.relative_to(self.repo_path))
            status = self._statuses.get(relative_path)

            if status in ("modified", "new"):
                import os
                try:
                    return os.path.getmtime(filepath)
                except OSError:
                    pass  # Fallback to git time

            return self._modification_times.get(relative_path)
        except ValueError:
            return None
