import subprocess
import time
from pathlib import Path

import pytest

from chronodocs.git_helpers import (
    get_file_creation_time,
    get_file_last_modified_time,
    get_git_status,
)


@pytest.fixture
def temp_git_repo(tmp_path: Path) -> Path:
    """Creates a temporary Git repository for testing."""
    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()

    subprocess.run(["git", "init"], cwd=repo_path, check=True)
    subprocess.run(
        ["git", "config", "user.name", "Test User"], cwd=repo_path, check=True
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"], cwd=repo_path, check=True
    )

    return repo_path


def test_get_git_status_untracked(temp_git_repo: Path):
    """Test parsing of untracked files."""
    untracked_file = temp_git_repo / "untracked.md"
    untracked_file.write_text("untracked")
    statuses = get_git_status(temp_git_repo)
    assert statuses.get("untracked.md") == "new"


def test_get_git_status_staged(temp_git_repo: Path):
    """Test parsing of staged (new) files."""
    staged_file = temp_git_repo / "staged.md"
    staged_file.write_text("staged")
    subprocess.run(["git", "add", staged_file], cwd=temp_git_repo, check=True)
    statuses = get_git_status(temp_git_repo)
    assert statuses.get("staged.md") == "new"


def test_get_git_status_committed(temp_git_repo: Path):
    """Test that committed files are not in the status list."""
    committed_file = temp_git_repo / "committed.md"
    committed_file.write_text("committed")
    subprocess.run(["git", "add", committed_file], cwd=temp_git_repo, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"], cwd=temp_git_repo, check=True
    )
    statuses = get_git_status(temp_git_repo)
    assert "committed.md" not in statuses


def test_get_git_status_modified(temp_git_repo: Path):
    """Test parsing of modified files."""
    modified_file = temp_git_repo / "modified.md"
    modified_file.write_text("initial content")
    subprocess.run(["git", "add", modified_file], cwd=temp_git_repo, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"], cwd=temp_git_repo, check=True
    )

    modified_file.write_text("modified content")

    statuses = get_git_status(temp_git_repo)
    assert statuses.get("modified.md") == "modified"


def test_get_file_timestamps(temp_git_repo: Path):
    """Test retrieving file creation and last modified times from git."""

    file_path = temp_git_repo / "test.md"

    # First commit
    file_path.write_text("first version")
    subprocess.run(["git", "add", file_path], cwd=temp_git_repo, check=True)
    first_commit_time = time.time()
    subprocess.run(["git", "commit", "-m", "first"], cwd=temp_git_repo, check=True)

    time.sleep(2)  # Ensure timestamps are different

    # Second commit
    file_path.write_text("second version")
    subprocess.run(["git", "add", file_path], cwd=temp_git_repo, check=True)
    second_commit_time = time.time()
    subprocess.run(["git", "commit", "-m", "second"], cwd=temp_git_repo, check=True)

    creation_time = get_file_creation_time(file_path, temp_git_repo)
    modified_time = get_file_last_modified_time(file_path, temp_git_repo)

    assert creation_time is not None
    assert modified_time is not None

    # Timestamps from git are integers, so we check they are close to our recorded times
    assert abs(creation_time - first_commit_time) < 5  # Allow a generous margin
    assert abs(modified_time - second_commit_time) < 5
    # Git timestamps can sometimes be the same second, so use <= instead of <
    assert creation_time <= modified_time


def test_get_file_last_modified_time_uses_filesystem_for_modified_files(
    temp_git_repo: Path,
):
    """
    Test that modified files use filesystem timestamp instead of git commit timestamp.
    This verifies the fix for the bug where modified files were showing old commit timestamps.
    """
    file_path = temp_git_repo / "test.md"

    # Create and commit a file
    file_path.write_text("initial version")
    subprocess.run(["git", "add", file_path], cwd=temp_git_repo, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=temp_git_repo, check=True)

    # Get the commit timestamp
    commit_time = get_file_last_modified_time(file_path, temp_git_repo)
    assert commit_time is not None

    # Wait to ensure filesystem timestamp will be different
    time.sleep(2)

    # Modify the file without committing
    file_path.write_text("modified version")

    # Get the modified time - should now use filesystem timestamp
    modified_time = get_file_last_modified_time(file_path, temp_git_repo)
    assert modified_time is not None

    # The key test: modified_time should be different from commit_time
    # This proves we're using filesystem time, not the old git commit time
    assert (
        modified_time != commit_time
    ), f"Modified file timestamp ({modified_time}) should differ from commit time ({commit_time})"

    # The modified time should be reasonably recent (within last few seconds)
    # Allow for some clock skew, but it should be close to when we modified it
    time_diff_from_now = abs(time.time() - modified_time)
    assert time_diff_from_now < 5, (
        f"Modified timestamp ({modified_time}) should be recent, "
        f"but differs from current time by {time_diff_from_now} seconds"
    )

    # Typically it should be newer than commit time (but allow for clock skew)
    # The important thing is that it's DIFFERENT, proving we're using filesystem time
    time_diff = modified_time - commit_time
    # We expect it to be > 2 seconds newer (due to our sleep), but allow for clock variations
    assert abs(time_diff) > 1, (
        f"Modified time should be significantly different from commit time. "
        f"Difference: {time_diff} seconds"
    )

    # Also verify it's not significantly in the future (allow small clock skew)
    assert (
        modified_time <= time.time() + 1
    ), f"Modified time {modified_time} should not be significantly in the future"

    # Verify the file is actually marked as modified
    statuses = get_git_status(temp_git_repo)
    assert statuses.get("test.md") == "modified"
