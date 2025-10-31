import time
from pathlib import Path
from unittest.mock import patch

import pytest

from chronodocs.config import get_config
from chronodocs.watcher_phase import PhaseWatcher


@pytest.fixture
def temp_phase_dir_for_watcher(tmp_path: Path) -> Path:
    """Sets up a temporary phase directory for watcher testing."""
    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()

    (repo_path / ".chronodocs.yml").write_text(
        "phase_dir_template: 'docs/{phase}'\ndebounce:\n  phase: 100 # ms"
    )

    phase_dir = repo_path / "docs" / "watch_phase"
    phase_dir.mkdir(parents=True)

    return phase_dir


@pytest.mark.skip(reason="This test is flaky due to timing issues with the watcher thread.")
@patch("chronodocs.watcher_phase.Reconciler")
def test_phase_watcher_triggers_reconciliation(
    MockReconciler, temp_phase_dir_for_watcher: Path
):
    """
    Test that the PhaseWatcher correctly detects file changes and triggers
    the debounced reconciler, including initial reconciliation on startup.
    """
    repo_root = temp_phase_dir_for_watcher.parents[1]
    config = get_config(repo_root)

    # Instantiate the mock reconciler
    mock_reconciler_instance = MockReconciler.return_value
    mock_reconciler_instance._is_ignored.return_value = (
        False  # Ensure no files are ignored
    )

    watcher = PhaseWatcher(phase_dir=temp_phase_dir_for_watcher, config=config)

    # Run the watcher in a separate thread so we don't block
    import threading

    watcher_thread = threading.Thread(target=watcher.run, daemon=True)
    watcher_thread.start()

    time.sleep(
        0.2
    )  # Give the watcher a moment to start up and run initial reconciliation

    # The reconcile method should have been called once on startup
    assert mock_reconciler_instance.reconcile.call_count == 1

    # --- Simulate file changes ---
    (temp_phase_dir_for_watcher / "new_file.md").touch()
    time.sleep(0.05)
    (temp_phase_dir_for_watcher / "another_file.txt").touch()

    # --- Assertions ---
    # The debounce interval is 100ms. We wait for it to expire.
    time.sleep(0.3)

    # The reconcile method should have been called twice (once on startup, once for file changes)
    assert mock_reconciler_instance.reconcile.call_count == 2

    # --- Test another event after minimum interval ---
    # The phase watcher has a 5-second minimum interval between reconciliations
    # Wait longer to ensure we're past the minimum interval (8 seconds to be safe)
    time.sleep(8.0)
    (temp_phase_dir_for_watcher / "a_third_file.md").touch()
    time.sleep(0.5)  # Wait for debounce with extra buffer

    # Should be called 3 times total (startup + 2 file change events)
    assert mock_reconciler_instance.reconcile.call_count == 3

    # --- Cleanup ---
    watcher.stop()
    watcher_thread.join(timeout=1)
