import subprocess
import time
from pathlib import Path

import pytest

from chronodocs.git_helpers import GitInfoProvider
from chronodocs.update_index import UpdateIndex


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


@pytest.fixture
def update_index(temp_git_repo: Path) -> UpdateIndex:
    """Creates an UpdateIndex instance for testing."""
    return UpdateIndex(temp_git_repo / ".update_index.json")


def test_get_git_status_untracked(temp_git_repo: Path):
    """Test parsing of untracked files."""
    untracked_file = temp_git_repo / "untracked.md"
    untracked_file.write_text("untracked")
    git_info = GitInfoProvider(temp_git_repo)
    status = git_info.get_status(untracked_file)
    assert status == "new"


def test_get_git_status_staged(temp_git_repo: Path):
    """Test parsing of staged (new) files."""
    staged_file = temp_git_repo / "staged.md"
    staged_file.write_text("staged")
    subprocess.run(["git", "add", staged_file], cwd=temp_git_repo, check=True)
    git_info = GitInfoProvider(temp_git_repo)
    status = git_info.get_status(staged_file)
    assert status == "staged"


def test_get_git_status_committed(temp_git_repo: Path):
    """Test that committed files are not in the status list."""
    committed_file = temp_git_repo / "committed.md"
    committed_file.write_text("committed")
    subprocess.run(["git", "add", committed_file], cwd=temp_git_repo, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"], cwd=temp_git_repo, check=True
    )
    git_info = GitInfoProvider(temp_git_repo)
    status = git_info.get_status(committed_file)
    assert status == "committed"


def test_get_git_status_modified(temp_git_repo: Path):
    """Test parsing of modified files."""
    modified_file = temp_git_repo / "modified.md"
    modified_file.write_text("initial content")
    subprocess.run(["git", "add", modified_file], cwd=temp_git_repo, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"], cwd=temp_git_repo, check=True
    )

    modified_file.write_text("modified content")

    git_info = GitInfoProvider(temp_git_repo)
    status = git_info.get_status(modified_file)
    assert status == "modified"


def test_get_file_timestamps(temp_git_repo: Path, update_index: UpdateIndex):
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

    git_info = GitInfoProvider(temp_git_repo)
    creation_time = git_info.get_creation_time(file_path)
    modified_time = git_info.get_last_modified_time(file_path, update_index)

    assert creation_time is not None
    assert modified_time is not None

    # Timestamps from git are integers, so we check they are close to our recorded times
    assert abs(creation_time - first_commit_time) < 5  # Allow a generous margin
    assert abs(modified_time - second_commit_time) < 5
    # Git timestamps can sometimes be the same second, so use <= instead of <
    assert creation_time <= modified_time


def test_get_last_modified_time_no_content_change(
    temp_git_repo: Path, update_index: UpdateIndex
):
    """Test that mtime change without content change does not update timestamp."""
    file_path = temp_git_repo / "test.md"
    file_path.write_text("initial content")

    # Initial update
    git_info = GitInfoProvider(temp_git_repo)
    initial_time = git_info.get_last_modified_time(file_path, update_index)
    assert initial_time is not None

    # Wait and touch the file to change mtime without changing content
    time.sleep(2)
    file_path.touch()

    # Re-instantiate GitInfoProvider and get time again
    git_info = GitInfoProvider(temp_git_repo)
    new_time = git_info.get_last_modified_time(file_path, update_index)
    assert new_time is not None

    # The timestamp should NOT have changed
    assert (
        abs(new_time - initial_time) < 1
    ), "Timestamp should not change if content is the same"


def test_get_last_modified_time_with_content_change(
    temp_git_repo: Path, update_index: UpdateIndex
):
    """Test that content change updates the timestamp."""
    file_path = temp_git_repo / "test.md"
    file_path.write_text("initial content")

    # Initial update
    git_info = GitInfoProvider(temp_git_repo)
    initial_time = git_info.get_last_modified_time(file_path, update_index)
    assert initial_time is not None

    # Wait and change the file content
    time.sleep(2)
    file_path.write_text("new content")

    # Re-instantiate GitInfoProvider and get time again
    git_info = GitInfoProvider(temp_git_repo)
    new_time = git_info.get_last_modified_time(file_path, update_index)
    assert new_time is not None

    # The timestamp SHOULD have changed
    assert new_time > initial_time, "Timestamp should update when content changes"
