import pytest
from pathlib import Path
import subprocess
import time

from chronodocs.config import get_config
from chronodocs.reporter import Reporter
from chronodocs.creation_index import CreationIndex

@pytest.fixture
def temp_phase_dir_with_git(tmp_path: Path) -> Path:
    """Creates a temporary directory within a git repo for testing."""
    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()

    subprocess.run(["git", "init"], cwd=repo_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_path, check=True)

    # Create a config file for the repo
    (repo_path / ".chronodocs.yml").write_text("phase_dir_template: '.devcontext/{phase}'")

    phase_dir = repo_path / ".devcontext" / "test_phase"
    phase_dir.mkdir(parents=True)

    return phase_dir

def test_generate_report(temp_phase_dir_with_git: Path):
    """Test the full report generation process."""
    repo_root = temp_phase_dir_with_git.parents[1]
    phase_dir = temp_phase_dir_with_git

    # --- Setup ---
    # 1. Create some files
    file1 = phase_dir / "00-first-doc.md"
    file1.write_text("This is the first document.")
    time.sleep(0.1) # ensure ctime difference
    file2 = phase_dir / "01-second-doc.py"
    file2.write_text("# A python script")

    # 2. Populate creation index to simulate reconciler having run
    creation_idx_path = phase_dir / ".creation_index.json"
    creation_idx = CreationIndex(creation_idx_path)
    creation_idx.add_file(file1, recorded_ctime=time.time() - 100) # older
    creation_idx.add_file(file2, recorded_ctime=time.time() - 50) # newer
    creation_idx.save()

    # 3. Commit one file, leave the other modified
    subprocess.run(["git", "add", file1], cwd=repo_root, check=True)
    subprocess.run(["git", "commit", "-m", "add first doc"], cwd=repo_root, check=True)

    file2.write_text("# An updated python script") # This makes file2 modified

    # --- Test ---
    config = get_config(repo_root)
    reporter = Reporter(phase_dir=phase_dir, config=config, repo_path=repo_root)
    report = reporter.generate_report()

    # --- Assertions ---
    assert "# Phase Change Log" in report
    assert "**Phase:** test_phase" in report
    assert "**Total files:** 2" in report

    # Check for file1 (committed)
    assert "00-first-doc.md" in report
    assert "⚪ committed" in report

    # Check for file2 (modified)
    assert "01-second-doc.py" in report
    # The git status for a new, un-added file is '??', which our helper maps to 'new'.
    # If it were added and then modified, it would be 'modified'. Let's test for that.
    subprocess.run(["git", "add", file2], cwd=repo_root, check=True)
    file2.write_text("# now it is modified for real")

    # Re-run report generation after git status change
    reporter = Reporter(phase_dir=phase_dir, config=config, repo_path=repo_root)
    report = reporter.generate_report()

    assert "🟡 modified" in report
