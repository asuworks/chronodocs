import subprocess
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

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

debounce:
    root: 100  # ms

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


def test_root_watcher_requires_phase(temp_repo_for_sentinel: Path):
    """Test that RootWatcher requires a phase to be specified."""
    config = get_config(temp_repo_for_sentinel)

    # Create watcher without phase - should fail when run
    watcher = RootWatcher(repo_path=temp_repo_for_sentinel, config=config, phase=None)

    # Run should exit with error
    watcher.run()
    # The watcher logs an error and returns early, so this should complete quickly


def test_root_watcher_generates_report_on_file_change(temp_repo_for_sentinel: Path):
    """Test that the RootWatcher detects changes and generates a report."""
    config = get_config(temp_repo_for_sentinel)
    phase_dir = temp_repo_for_sentinel / ".devcontext" / "progress" / "test_phase"
    output_file = phase_dir / "change_log.md"

    watcher = RootWatcher(
        repo_path=temp_repo_for_sentinel, config=config, phase="test_phase"
    )

    # Create a test file before starting watcher
    test_file = temp_repo_for_sentinel / "src" / "test_source.py"
    test_file.write_text("# Test source")

    # Run the watcher in a separate thread
    import threading

    watcher_thread = threading.Thread(target=watcher.run, daemon=True)
    watcher_thread.start()

    time.sleep(0.2)  # Allow watcher to initialize

    # --- Simulate a file change that should be detected ---
    new_file = temp_repo_for_sentinel / "src" / "new_source.py"
    new_file.write_text("# New source")

    # Wait for debounce to expire and report to generate
    time.sleep(0.5)

    # The report should have been generated
    assert output_file.exists()
    content = output_file.read_text()
    assert "# Project Change Log" in content
    assert "new_source.py" in content or "test_source.py" in content

    # --- Cleanup ---
    watcher.stop()
    watcher_thread.join(timeout=1)


def test_root_watcher_ignores_change_log(temp_repo_for_sentinel: Path):
    """Test that the RootWatcher ignores its own change_log.md file."""
    config = get_config(temp_repo_for_sentinel)
    phase_dir = temp_repo_for_sentinel / ".devcontext" / "progress" / "test_phase"
    output_file = phase_dir / "change_log.md"

    watcher = RootWatcher(
        repo_path=temp_repo_for_sentinel, config=config, phase="test_phase"
    )

    # Mock the reporter to track calls
    with patch("chronodocs.watcher_root.Reporter") as MockReporter:
        mock_reporter_instance = MagicMock()
        MockReporter.return_value = mock_reporter_instance
        mock_reporter_instance.generate_report.return_value = "# Test Report"

        # Run the watcher in a separate thread
        import threading

        watcher_thread = threading.Thread(target=watcher.run, daemon=True)
        watcher_thread.start()

        time.sleep(0.2)  # Allow watcher to initialize

        # Reset mock to ignore initialization
        MockReporter.reset_mock()
        mock_reporter_instance.reset_mock()

        # Create change_log.md (should be ignored)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text("# Should be ignored")

        # Wait
        time.sleep(0.3)

        # Reporter should NOT have been called
        assert MockReporter.call_count == 0

        # Now create a regular file (should trigger)
        regular_file = temp_repo_for_sentinel / "regular.md"
        regular_file.write_text("# Regular file")

        # Wait for debounce and processing
        time.sleep(0.5)

        # Reporter should have been called now
        assert MockReporter.call_count >= 1

        # --- Cleanup ---
        watcher.stop()
        watcher_thread.join(timeout=1)


def test_root_watcher_ignores_git_directory(temp_repo_for_sentinel: Path):
    """Test that the RootWatcher ignores files in .git directory."""
    config = get_config(temp_repo_for_sentinel)

    watcher = RootWatcher(
        repo_path=temp_repo_for_sentinel, config=config, phase="test_phase"
    )

    # Mock the reporter to track calls
    with patch("chronodocs.watcher_root.Reporter") as MockReporter:
        mock_reporter_instance = MagicMock()
        MockReporter.return_value = mock_reporter_instance
        mock_reporter_instance.generate_report.return_value = "# Test Report"

        # Run the watcher in a separate thread
        import threading

        watcher_thread = threading.Thread(target=watcher.run, daemon=True)
        watcher_thread.start()

        time.sleep(0.2)  # Allow watcher to initialize

        # Reset mock to ignore initialization
        MockReporter.reset_mock()

        # Create file in .git directory (should be ignored)
        git_file = temp_repo_for_sentinel / ".git" / "test_file"
        git_file.write_text("Git file")

        # Wait
        time.sleep(0.3)

        # Reporter should NOT have been called
        assert MockReporter.call_count == 0

        # --- Cleanup ---
        watcher.stop()
        watcher_thread.join(timeout=1)


def test_root_watcher_respects_minimum_interval(temp_repo_for_sentinel: Path):
    """Test that the RootWatcher respects the minimum interval between reports."""
    config = get_config(temp_repo_for_sentinel)

    watcher = RootWatcher(
        repo_path=temp_repo_for_sentinel, config=config, phase="test_phase"
    )

    # Mock the reporter to track calls
    with patch("chronodocs.watcher_root.Reporter") as MockReporter:
        mock_reporter_instance = MagicMock()
        MockReporter.return_value = mock_reporter_instance
        mock_reporter_instance.generate_report.return_value = "# Test Report"

        # Run the watcher in a separate thread
        import threading

        watcher_thread = threading.Thread(target=watcher.run, daemon=True)
        watcher_thread.start()

        time.sleep(0.2)  # Allow watcher to initialize

        # Reset mock
        MockReporter.reset_mock()

        # Create first file
        file1 = temp_repo_for_sentinel / "file1.md"
        file1.write_text("First file")

        # Wait for debounce and processing
        time.sleep(0.5)

        # Should have been called once
        first_call_count = MockReporter.call_count
        assert first_call_count >= 1

        # Immediately create second file (should be throttled by 5-second minimum)
        file2 = temp_repo_for_sentinel / "file2.md"
        file2.write_text("Second file")

        # Wait for debounce but not full 5 seconds
        time.sleep(0.5)

        # Should NOT have been called again (minimum interval not passed)
        assert MockReporter.call_count == first_call_count

        # --- Cleanup ---
        watcher.stop()
        watcher_thread.join(timeout=1)


def test_root_watcher_includes_files_from_all_watch_paths(temp_repo_for_sentinel: Path):
    """Test that the generated report includes files from all watch paths."""
    config = get_config(temp_repo_for_sentinel)
    phase_dir = temp_repo_for_sentinel / ".devcontext" / "progress" / "test_phase"
    output_file = phase_dir / "change_log.md"

    # Create files in different locations
    (temp_repo_for_sentinel / "root_file.md").write_text("Root file")
    (temp_repo_for_sentinel / "src" / "code.py").write_text("# Code")
    phase_file = phase_dir / "phase_file.md"
    phase_file.write_text("Phase file")

    watcher = RootWatcher(
        repo_path=temp_repo_for_sentinel, config=config, phase="test_phase"
    )

    # Run the watcher in a separate thread
    import threading

    watcher_thread = threading.Thread(target=watcher.run, daemon=True)
    watcher_thread.start()

    time.sleep(0.2)  # Allow watcher to initialize

    # Trigger a change
    trigger_file = temp_repo_for_sentinel / "trigger.md"
    trigger_file.write_text("Trigger change")

    # Wait for report generation
    time.sleep(0.5)

    # Check report includes all files
    assert output_file.exists()
    content = output_file.read_text()
    assert "root_file.md" in content
    assert "code.py" in content
    assert "phase_file.md" in content

    # --- Cleanup ---
    watcher.stop()
    watcher_thread.join(timeout=1)
