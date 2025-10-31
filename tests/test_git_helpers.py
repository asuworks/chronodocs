import pytest
from pathlib import Path
import subprocess
import time

from chronodocs.git_helpers import get_git_status, get_file_creation_time, get_file_last_modified_time

@pytest.fixture
def temp_git_repo(tmp_path: Path) -> Path:
    """Creates a temporary Git repository for testing."""
    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()

    subprocess.run(["git", "init"], cwd=repo_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_path, check=True)

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
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=temp_git_repo, check=True)
    statuses = get_git_status(temp_git_repo)
    assert "committed.md" not in statuses

def test_get_git_status_modified(temp_git_repo: Path):
    """Test parsing of modified files."""
    modified_file = temp_git_repo / "modified.md"
    modified_file.write_text("initial content")
    subprocess.run(["git", "add", modified_file], cwd=temp_git_repo, check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=temp_git_repo, check=True)

    modified_file.write_text("modified content")

    statuses = get_git_status(temp_git_repo)
    assert statuses.get("modified.md") == "modified"

def test_get_file_timestamps(temp_git_repo: Path):
    """Test retrieving file creation and last modified times from git."""

    file_path = temp_git_repo / "test.md"

    # First commit
    file_path.write_text("first version")
    subprocess.run(["git", "add", file_path], cwd=temp_git_repo, check=True)
    subprocess.run(["git", "commit", "-m", "first"], cwd=temp_git_repo, check=True)
    first_commit_time = time.time()

    time.sleep(1) # Ensure timestamps are different

    # Second commit
    file_path.write_text("second version")
    subprocess.run(["git", "add", file_path], cwd=temp_git_repo, check=True)
    subprocess.run(["git", "commit", "-m", "second"], cwd=temp_git_repo, check=True)
    second_commit_time = time.time()

    creation_time = get_file_creation_time(file_path, temp_git_repo)
    modified_time = get_file_last_modified_time(file_path, temp_git_repo)

    assert creation_time is not None
    assert modified_time is not None

    # Timestamps from git are integers, so we check they are close to our recorded times
    assert abs(creation_time - first_commit_time) < 5 # Allow a generous margin
    assert abs(modified_time - second_commit_time) < 5
    assert creation_time < modified_time
