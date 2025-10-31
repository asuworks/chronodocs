import threading
import time
from pathlib import Path

import pytest

from chronodocs.config import get_config
from chronodocs.watcher_phase import PhaseWatcher


@pytest.fixture
def temp_phase_dir_for_watcher(tmp_path: Path) -> Path:
    """Sets up a temporary phase directory for watcher testing."""
    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()

    (repo_path / ".chronodocs.yml").write_text(
        """
        phase_dir_template: 'docs/{phase}'
        ignore_patterns:
          - ".git/"
          - ".chronodocs.yml"
          - ".creation_index.json"
          - ".update_index.json"
        """
    )

    phase_dir = repo_path / "docs" / "watch_phase"
    phase_dir.mkdir(parents=True)

    return phase_dir


def test_start_and_stop_observer(temp_phase_dir_for_watcher: Path):
    """Verify that the observer starts and stops correctly."""
    repo_root = temp_phase_dir_for_watcher.parents[1]
    config = get_config(repo_root)

    watcher = PhaseWatcher(
        phase_dir=temp_phase_dir_for_watcher,
        config=config,
        debounce_interval=0.01,
        min_reconcile_interval=0.01,
    )

    thread = threading.Thread(target=watcher.run, daemon=True)
    thread.start()
    time.sleep(0.1)  # Give it a moment to start the observer
    assert watcher.observer.is_alive()

    watcher.stop()
    thread.join(timeout=2)
    assert not watcher.observer.is_alive()
    assert not thread.is_alive()


def test_reconcile_on_startup(temp_phase_dir_for_watcher: Path):
    """Test that existing files are reconciled on startup."""
    repo_root = temp_phase_dir_for_watcher.parents[1]
    config = get_config(repo_root)
    reconcile_done_event = threading.Event()

    # Create a file before starting the watcher
    (temp_phase_dir_for_watcher / "unprefixed_file.md").write_text("hello")

    watcher = PhaseWatcher(
        phase_dir=temp_phase_dir_for_watcher,
        config=config,
        debounce_interval=0.01,
        min_reconcile_interval=0.01,
        reconcile_done_event=reconcile_done_event,
    )

    thread = threading.Thread(target=watcher.run, daemon=True)
    thread.start()

    # Wait for the initial reconcile to complete
    event_was_set = reconcile_done_event.wait(timeout=2)
    assert event_was_set, "Reconcile event was not set on startup"

    # Check that the file was prefixed
    assert not (
        temp_phase_dir_for_watcher / "unprefixed_file.md"
    ).exists()
    assert (
        temp_phase_dir_for_watcher / "00-unprefixed_file.md"
    ).exists()

    watcher.stop()
    thread.join(timeout=2)


def test_event_handling_and_renaming(temp_phase_dir_for_watcher: Path):
    """Test that new files are detected and renamed."""
    repo_root = temp_phase_dir_for_watcher.parents[1]
    config = get_config(repo_root)
    reconcile_done_event = threading.Event()
    min_interval = 0.05

    watcher = PhaseWatcher(
        phase_dir=temp_phase_dir_for_watcher,
        config=config,
        debounce_interval=0.01,
        min_reconcile_interval=min_interval,
        reconcile_done_event=reconcile_done_event,
    )

    thread = threading.Thread(target=watcher.run, daemon=True)
    thread.start()

    # Wait for startup reconcile
    assert reconcile_done_event.wait(timeout=2)
    reconcile_done_event.clear()

    # Wait for cooldown
    time.sleep(min_interval)

    # Create a new file
    (temp_phase_dir_for_watcher / "new_file.md").write_text("new")

    # Wait for the event-triggered reconcile
    assert reconcile_done_event.wait(timeout=2)

    # Check that the new file was prefixed
    assert not (temp_phase_dir_for_watcher / "new_file.md").exists()
    assert (temp_phase_dir_for_watcher / "00-new_file.md").exists()

    watcher.stop()
    thread.join(timeout=2)


def test_throttling_of_reconcile_calls(temp_phase_dir_for_watcher: Path):
    """Test that rapid events are debounced and throttled correctly."""
    repo_root = temp_phase_dir_for_watcher.parents[1]
    config = get_config(repo_root)
    reconcile_done_event = threading.Event()
    min_interval = 0.2
    debounce_interval = 0.05

    watcher = PhaseWatcher(
        phase_dir=temp_phase_dir_for_watcher,
        config=config,
        debounce_interval=debounce_interval,
        min_reconcile_interval=min_interval,
        reconcile_done_event=reconcile_done_event,
    )

    thread = threading.Thread(target=watcher.run, daemon=True)
    thread.start()

    # 1. Wait for startup reconcile
    assert reconcile_done_event.wait(timeout=2)
    reconcile_done_event.clear()

    # 2. Trigger a successful event after cooldown
    time.sleep(min_interval)
    (temp_phase_dir_for_watcher / "file1.md").write_text("1")
    assert reconcile_done_event.wait(timeout=2)
    assert (temp_phase_dir_for_watcher / "00-file1.md").exists()
    reconcile_done_event.clear()

    # 3. Trigger an immediate event that should be throttled
    (temp_phase_dir_for_watcher / "file2.md").write_text("2")

    # Wait for the debounce timer to fire the throttled call
    time.sleep(debounce_interval + 0.05)
    # Assert that the event is NOT set, because the call was throttled
    assert not reconcile_done_event.is_set()
    # And the file has not been renamed
    assert (temp_phase_dir_for_watcher / "file2.md").exists()
    assert not (temp_phase_dir_for_watcher / "01-file2.md").exists()

    # 4. Wait for the rescheduled call to complete
    assert reconcile_done_event.wait(timeout=2)
    # Check that the file from the throttled event has now been processed
    assert not (temp_phase_dir_for_watcher / "file2.md").exists()
    assert (temp_phase_dir_for_watcher / "01-file2.md").exists()

    watcher.stop()
    thread.join(timeout=2)
