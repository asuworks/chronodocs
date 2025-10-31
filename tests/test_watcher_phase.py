import pytest
from pathlib import Path
import time
from unittest.mock import MagicMock, patch

from chronodocs.watcher_phase import PhaseWatcher
from chronodocs.config import get_config

@pytest.fixture
def temp_phase_dir_for_watcher(tmp_path: Path) -> Path:
    """Sets up a temporary phase directory for watcher testing."""
    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()

    (repo_path / ".chronodocs.yml").write_text("phase_dir_template: 'docs/{phase}'\ndebounce:\n  phase: 100 # ms")

    phase_dir = repo_path / "docs" / "watch_phase"
    phase_dir.mkdir(parents=True)

    return phase_dir

@patch('chronodocs.watcher_phase.Reconciler')
def test_phase_watcher_triggers_reconciliation(MockReconciler, temp_phase_dir_for_watcher: Path):
    """
    Test that the PhaseWatcher correctly detects file changes and triggers
    the debounced reconciler.
    """
    repo_root = temp_phase_dir_for_watcher.parents[1]
    config = get_config(repo_root)

    # Instantiate the mock reconciler
    mock_reconciler_instance = MockReconciler.return_value
    mock_reconciler_instance._is_ignored.return_value = False # Ensure no files are ignored

    watcher = PhaseWatcher(phase_dir=temp_phase_dir_for_watcher, config=config)

    # Run the watcher in a separate thread so we don't block
    import threading
    watcher_thread = threading.Thread(target=watcher.run, daemon=True)
    watcher_thread.start()

    time.sleep(0.1) # Give the watcher a moment to start up

    # --- Simulate file changes ---
    (temp_phase_dir_for_watcher / "new_file.md").touch()
    time.sleep(0.05)
    (temp_phase_dir_for_watcher / "another_file.txt").touch()

    # --- Assertions ---
    # The debounce interval is 100ms. We wait for it to expire.
    time.sleep(0.2)

    # The reconcile method should have been called exactly once.
    mock_reconciler_instance.reconcile.assert_called_once()

    # --- Test another event ---
    (temp_phase_dir_for_watcher / "a_third_file.md").touch()
    time.sleep(0.2)

    assert mock_reconciler_instance.reconcile.call_count == 2

    # --- Cleanup ---
    watcher.stop()
    watcher_thread.join(timeout=1)
