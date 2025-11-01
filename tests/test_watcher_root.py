import subprocess
import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from chronodocs.config import get_config
from chronodocs.watcher_root import RootWatcher


@pytest.fixture
def temp_repo_for_sentinel(tmp_path: Path) -> Path:
    """Sets up a temporary repo for the sentinel (root watcher) testing."""
    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.name", "Test User"], cwd=repo_path, check=True
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"], cwd=repo_path, check=True
    )

    # Configure the repo
    config_content = """
phase_dir_template: '.devcontext/progress/{phase}'

watch_paths:
    - "."

ignore_patterns:
    - "change_log.md"
    - ".git/"
    - ".creation_index.json"
    - ".update_index.json"


report:
    extensions:
        - ".md"
        - ".py"
    group_by: "updated_day"
    sort_by: "updated_desc"
"""
    (repo_path / ".chronodocs.yml").write_text(config_content)

    # Create phase directory
    phase_dir = repo_path / ".devcontext" / "progress" / "test_phase"
    phase_dir.mkdir(parents=True)

    # A subdirectory to create changes in
    (repo_path / "src").mkdir()

    return repo_path


def test_start_and_stop_observer(temp_repo_for_sentinel: Path):
    """Verify that the observer starts and stops correctly."""
    config = get_config(temp_repo_for_sentinel)
    watcher = RootWatcher(
        repo_path=temp_repo_for_sentinel,
        config=config,
        phase="test_phase",
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


def test_reconcile_on_startup(temp_repo_for_sentinel: Path):
    """Test that reconcile is called on startup."""
    config = get_config(temp_repo_for_sentinel)
    reconcile_done_event = threading.Event()

    # Create a file before starting the watcher
    (temp_repo_for_sentinel / "existing_file.md").write_text("hello")

    watcher = RootWatcher(
        repo_path=temp_repo_for_sentinel,
        config=config,
        phase="test_phase",
        debounce_interval=0.01,
        min_reconcile_interval=0.01,
        reconcile_done_event=reconcile_done_event,
    )

    with patch.object(
        watcher, "_reconcile_and_report", wraps=watcher._reconcile_and_report
    ) as mock_reconcile:
        thread = threading.Thread(target=watcher.run, daemon=True)
        thread.start()

        # Wait for the initial reconcile to complete
        event_was_set = reconcile_done_event.wait(timeout=2)
        assert event_was_set, "Reconcile event was not set on startup"

        mock_reconcile.assert_called_once()

        watcher.stop()
        thread.join(timeout=2)


def test_report_generation_on_startup(temp_repo_for_sentinel: Path):
    """Test that a report is generated on startup if files exist."""
    config = get_config(temp_repo_for_sentinel)
    reconcile_done_event = threading.Event()
    phase_dir = temp_repo_for_sentinel / ".devcontext/progress/test_phase"
    report_file = phase_dir / "change_log.md"

    # Create a file before starting the watcher
    (temp_repo_for_sentinel / "existing_file.md").write_text("hello")

    assert not report_file.exists()

    watcher = RootWatcher(
        repo_path=temp_repo_for_sentinel,
        config=config,
        phase="test_phase",
        debounce_interval=0.01,
        min_reconcile_interval=0.01,
        reconcile_done_event=reconcile_done_event,
    )

    thread = threading.Thread(target=watcher.run, daemon=True)
    thread.start()

    event_was_set = reconcile_done_event.wait(timeout=2)
    assert event_was_set, "Reconcile event was not set on startup"

    assert report_file.exists()
    content = report_file.read_text()
    assert "existing_file.md" in content

    watcher.stop()
    thread.join(timeout=2)


def test_event_handling_and_report_generation(temp_repo_for_sentinel: Path):
    """Test that file events trigger reconcile and report generation."""
    config = get_config(temp_repo_for_sentinel)
    reconcile_done_event = threading.Event()
    phase_dir = temp_repo_for_sentinel / ".devcontext/progress/test_phase"
    report_file = phase_dir / "change_log.md"
    min_interval = 0.05  # Use a slightly larger, more realistic interval

    watcher = RootWatcher(
        repo_path=temp_repo_for_sentinel,
        config=config,
        phase="test_phase",
        debounce_interval=0.01,
        min_reconcile_interval=min_interval,
        reconcile_done_event=reconcile_done_event,
    )

    thread = threading.Thread(target=watcher.run, daemon=True)
    thread.start()

    # Wait for the initial startup reconcile to finish
    event_was_set = reconcile_done_event.wait(timeout=2)
    assert event_was_set, "Initial reconcile event was not set"
    reconcile_done_event.clear()  # Reset for the next event

    # Wait for the cooldown period to pass to avoid throttling
    time.sleep(min_interval)

    # Now, create a new file
    (temp_repo_for_sentinel / "new_file.md").write_text("new content")

    # Wait for the event-triggered reconcile to finish
    event_was_set = reconcile_done_event.wait(timeout=2)
    assert event_was_set, "Event-triggered reconcile event was not set"

    assert report_file.exists()
    content = report_file.read_text()
    assert "new_file.md" in content

    watcher.stop()
    thread.join(timeout=2)


def test_throttling_of_reconcile_calls(temp_repo_for_sentinel: Path):
    """Test that rapid events are debounced and throttled."""
    config = get_config(temp_repo_for_sentinel)
    reconcile_done_event = threading.Event()
    min_interval = 0.2
    debounce_interval = 0.05
    report_file = (
        temp_repo_for_sentinel
        / ".devcontext/progress/test_phase"
        / "change_log.md"
    )

    watcher = RootWatcher(
        repo_path=temp_repo_for_sentinel,
        config=config,
        phase="test_phase",
        debounce_interval=debounce_interval,
        min_reconcile_interval=min_interval,
        reconcile_done_event=reconcile_done_event,
    )

    thread = threading.Thread(target=watcher.run, daemon=True)
    thread.start()

    # 1. Wait for startup reconcile
    assert reconcile_done_event.wait(timeout=2)
    reconcile_done_event.clear()
    initial_content = report_file.read_text() if report_file.exists() else ""

    # 2. Trigger a successful event after cooldown
    time.sleep(min_interval)
    (temp_repo_for_sentinel / "file1.md").write_text("1")
    assert reconcile_done_event.wait(timeout=2)
    content_after_first_event = report_file.read_text()
    assert "file1.md" in content_after_first_event
    assert content_after_first_event != initial_content
    reconcile_done_event.clear()

    # 3. Trigger an immediate event that should be throttled
    (temp_repo_for_sentinel / "file2.md").write_text("2")

    # Wait for the debounce timer to fire the throttled call
    time.sleep(debounce_interval + 0.05)
    # Assert that the event is NOT set, because the call was throttled
    assert not reconcile_done_event.is_set()
    # And the report has not been updated
    assert report_file.read_text() == content_after_first_event

    # 4. Wait for the rescheduled call to complete
    assert reconcile_done_event.wait(timeout=2)
    # Check that the report from the throttled event has now been generated
    content_after_throttled_event = report_file.read_text()
    assert "file2.md" in content_after_throttled_event
    assert content_after_throttled_event != content_after_first_event

    watcher.stop()
    thread.join(timeout=2)


def test_ignore_patterns_are_respected(temp_repo_for_sentinel: Path):
    """Test that ignored files do not trigger a reconcile."""
    config = get_config(temp_repo_for_sentinel)
    reconcile_done_event = threading.Event()

    watcher = RootWatcher(
        repo_path=temp_repo_for_sentinel,
        config=config,
        phase="test_phase",
        debounce_interval=0.01,
        min_reconcile_interval=0.01,
        reconcile_done_event=reconcile_done_event,
    )

    with patch.object(
        watcher, "_reconcile_and_report", wraps=watcher._reconcile_and_report
    ) as mock_reconcile:
        thread = threading.Thread(target=watcher.run, daemon=True)
        thread.start()

        # Wait for startup reconcile
        assert reconcile_done_event.wait(timeout=2)
        mock_reconcile.assert_called_once()
        reconcile_done_event.clear()

        # Create an ignored file
        (temp_repo_for_sentinel / ".git" / "some_git_file").write_text("ignored")

        # Wait a bit to see if it triggers
        event_was_set = reconcile_done_event.wait(timeout=0.2)
        assert not event_was_set, "Reconcile was triggered for an ignored file"
        assert mock_reconcile.call_count == 1

        # Now create a file that is NOT ignored
        (temp_repo_for_sentinel / "not_ignored.md").write_text("triggers")

        event_was_set = reconcile_done_event.wait(timeout=2)
        assert event_was_set
        assert mock_reconcile.call_count == 2

        watcher.stop()
        thread.join(timeout=2)
