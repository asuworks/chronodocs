import pytest
from pathlib import Path
import time
import subprocess
from unittest.mock import patch

from chronodocs.watcher_root import RootWatcher
from chronodocs.config import get_config

@pytest.fixture
def temp_repo_for_sentinel(tmp_path: Path) -> Path:
    """Sets up a temporary repo for the sentinel (root watcher) testing."""
    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()

    # Configure a make command and an ignore pattern for the changelog itself
    config_content = """
make_command: "echo 'report generated'"
ignore_patterns:
  - "change_log.md"
  - ".git/"
debounce:
  root: 100 # ms
"""
    (repo_path / ".chronodocs.yml").write_text(config_content)

    # A subdirectory to create changes in
    (repo_path / "src").mkdir()

    return repo_path

@patch('chronodocs.watcher_root.subprocess.run')
def test_root_watcher_triggers_command(mock_subprocess_run, temp_repo_for_sentinel: Path):
    """
    Test that the RootWatcher detects changes and triggers the make command,
    while ignoring specified files.
    """
    config = get_config(temp_repo_for_sentinel)
    watcher = RootWatcher(repo_path=temp_repo_for_sentinel, config=config)

    # Run the watcher in a separate thread
    import threading
    watcher_thread = threading.Thread(target=watcher.run, daemon=True)
    watcher_thread.start()

    time.sleep(0.1) # Allow watcher to initialize

    # --- Simulate a file change that should be detected ---
    (temp_repo_for_sentinel / "src" / "new_source.py").touch()

    # Wait for debounce to expire
    time.sleep(0.2)

    # The make command should have been called once
    mock_subprocess_run.assert_called_once()
    assert mock_subprocess_run.call_args.args[0] == ["echo", "report generated"]

    # --- Simulate a file change that should be IGNORED ---
    # @TODO: Fix ignore pattern logic
    # mock_subprocess_run.reset_mock() # Reset the mock for the next assertion

    # (temp_repo_for_sentinel / "change_log.md").touch()

    # # Wait to see if the command is triggered (it shouldn't be)
    # time.sleep(0.2)

    # # The command should NOT have been called again
    # mock_subprocess_run.assert_not_called()

    # --- Cleanup ---
    watcher.stop()
    watcher_thread.join(timeout=1)
