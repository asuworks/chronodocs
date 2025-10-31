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
        # Handle cases where git is not installed or the command fails
        return ""


def get_git_status(repo_path: Path) -> Dict[str, str]:
    """
    Gets the git status for all files in the repository.
    Uses `git status --porcelain -z` for reliable parsing.

    Returns a dictionary mapping file paths (relative to repo root) to a status string.
    Status strings can be: 'new', 'modified', 'staged', 'untracked', 'deleted'.
    """
    output = _run_git_command(["status", "--porcelain", "-z"], cwd=repo_path)
    if not output:
        return {}

    statuses = {}
    # Entries are NUL-terminated
    for line in output.strip("\0").split("\0"):
        if not line:
            continue

        status_codes = line[:2]
        filepath = line[3:]

        # Handle renamed files (e.g., "R  old -> new")
        if " -> " in filepath:
            filepath = filepath.split(" -> ")[1]

        # Determine a single status string based on the porcelain codes
        index_status = status_codes[0]
        worktree_status = status_codes[1]

        status = "committed"  # Default
        if index_status == "A" or worktree_status == "?":
            status = "new"
        elif worktree_status == "M":
            status = "modified"
        elif index_status == "M":
            status = "staged"
        elif index_status == "D":
            status = "deleted"
        elif index_status == "R":  # Renamed in index
            status = "staged"  # Treat as staged change

        statuses[filepath] = status

    return statuses


def get_file_creation_time(filepath: Path, repo_path: Path) -> Optional[float]:
    """
    Gets the creation time of a file from its first git commit.
    Returns a Unix timestamp.
    """
    output = _run_git_command(
        ["log", "--diff-filter=A", "--follow", "--format=%at", "--", str(filepath)],
        cwd=repo_path,
    )
    if output:
        return float(output.strip().split("\n")[0])
    return None


def get_file_last_modified_time(filepath: Path, repo_path: Path) -> Optional[float]:
    """
    Gets the last modification time of a file.
    For modified/untracked files, uses filesystem timestamp.
    For committed files, uses the most recent git commit timestamp.
    Returns a Unix timestamp.
    """
    # First check if file is modified or untracked
    git_statuses = get_git_status(repo_path)
    try:
        relative_path = str(filepath.relative_to(repo_path))
        status = git_statuses.get(relative_path, "committed")

        # If file is modified or new, use filesystem timestamp
        if status in ("modified", "new", "untracked"):
            import os

            try:
                return os.path.getmtime(filepath)
            except OSError:
                pass
    except ValueError:
        # filepath is not relative to repo_path
        pass

    # Otherwise, use git commit timestamp
    output = _run_git_command(
        ["log", "-1", "--format=%at", "--", str(filepath)], cwd=repo_path
    )
    if output:
        return float(output.strip())
    return None
